import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
import datetime
import io
import google.generativeai as genai

# --- إعداد الاتصال ---
def get_client():
    # هذا السطر يقرأ البيانات من الخزنة التي أعددتها في Secrets
    creds_dict = st.secrets["gcp_service_account"]
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

client = get_client()
sheet = client.open_by_key("17y_KBs5xQqTY_63UtMC22Sxru7X9jxhg86LvM1WL9us")

@st.cache_data(ttl=60)
def get_df(sheet_name):
    worksheet = sheet.worksheet(sheet_name)
    data = worksheet.get_all_values()
    if not data: return pd.DataFrame()
    df = pd.DataFrame(data[1:], columns=data[0])
    if 'ref' in df.columns:
        df['ref'] = df['ref'].astype(str).str.replace("'", "", regex=False)
    return df

def save_to_sheet(sheet_name, df):
    worksheet = sheet.worksheet(sheet_name)
    worksheet.clear()
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())
    st.cache_data.clear()

st.set_page_config(layout="wide")
st.title("Gestion de Production Pro")

tab1, tab2, tab3, tab4 = st.tabs(["Produits", "Plan", "Saisie", "Dashboard"])

# 1. المنتجات
with tab1:
    st.header("Gestion des Produits")
    c1, c2 = st.columns(2)
    ref_p = c1.text_input("Référence", key="p_ref")
    name_p = c2.text_input("Nom", key="p_name")
    if st.button("Ajouter Produit"):
        df = get_df("products")
        new_row = pd.DataFrame({'ref': [ref_p], 'name': [name_p]})
        df = pd.concat([df, new_row], ignore_index=True).drop_duplicates(subset='ref', keep='last')
        save_to_sheet("products", df)
        st.rerun()
    st.dataframe(get_df("products"))

# 2. الخطة الشهرية
with tab2:
    st.header("Plan Mensuel")
    df_plan = get_df("monthly_plan")
    all_months = sorted(df_plan['month'].unique()) if not df_plan.empty else []
    filter_m = st.selectbox("Filtrer par Mois", ["Tous"] + all_months, key="plan_filter")
    if filter_m != "Tous": df_plan = df_plan[df_plan['month'] == filter_m]
    st.dataframe(df_plan)
    with st.expander("Ajouter un nouveau plan"):
        m, r, t, p = st.columns(4)
        sel_date = m.date_input("Mois", value=datetime.date.today())
        ref = r.selectbox("Ref", options=get_df("products")['ref'].tolist(), key="plan_r")
        if st.button("Ajouter Plan"):
            df = get_df("monthly_plan")
            new_row = pd.DataFrame({'month':[sel_date.strftime("%Y-%m")], 'ref':[ref], 'target':[float(t.number_input("Target", value=0))], 'price':[float(p.number_input("Price", value=0))]})
            save_to_sheet("monthly_plan", pd.concat([df, new_row], ignore_index=True))
            st.rerun()

# 3. السجلات
with tab3:
    st.header("Saisie de Production")
    d, r, q = st.columns(3)
    date = d.date_input("Date", key="log_d")
    ref = r.selectbox("Ref", options=get_df("products")['ref'].tolist(), key="log_r")
    qty = q.number_input("Qty", value=0, key="log_q")
    if st.button("Ajouter Log"):
        df = get_df("production_logs")
        save_to_sheet("production_logs", pd.concat([df, pd.DataFrame({'date':[str(date)], 'ref':[ref], 'qty':[float(qty)]})], ignore_index=True))
        st.rerun()
    st.dataframe(get_df("production_logs"))

# 4. الداشبورد + تحليل AI
with tab4:
    st.header("Tableau de Bord Comparatif")
    df_logs = get_df("production_logs")
    df_plan = get_df("monthly_plan")
    
    all_months = sorted(df_plan['month'].unique()) if not df_plan.empty else []
    filter_dash = st.selectbox("Mois pour le rapport", ["Tous"] + all_months, key="dash_filter")
    if filter_dash != "Tous":
        df_plan = df_plan[df_plan['month'] == filter_dash]
        df_logs = df_logs[df_logs['date'].str.contains(filter_dash)]

    df_compare = pd.merge(df_plan.groupby('ref')['target'].sum().reset_index(), df_logs.groupby('ref')['qty'].sum().reset_index(), on='ref', how='outer').fillna(0)
    df_compare['Taux (%)'] = (df_compare['qty'] / df_compare['target'] * 100).replace([float('inf'), -float('inf')], 0)

    st.dataframe(df_compare.style.background_gradient(subset=['Taux (%)'], cmap='RdYlGn'), column_config={"Taux (%)": st.column_config.NumberColumn(format="%.2f")}, use_container_width=True)
    
    # تصدير Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer: df_compare.to_excel(writer, index=False)
    st.download_button("📥 Télécharger Rapport (Excel)", data=output.getvalue(), file_name="Rapport.xlsx")

    # تحليل الذكاء الاصطناعي
    st.subheader("🤖 Analyse AI")
    if st.button("Analyser avec AI"):
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(f"Analyse ces données de production : {df_compare.to_string()}")
        st.write(response.text)