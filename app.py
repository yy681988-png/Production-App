import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import io
import google.generativeai as genai

# --- إعداد الاتصال ---
def get_client():
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

# 1. المنتجات + الحذف
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
    
    df_prod = get_df("products")
    st.dataframe(df_prod)
    del_ref = st.selectbox("Sélectionner la référence à supprimer", df_prod['ref'].tolist() if not df_prod.empty else [])
    if st.button("Supprimer Produit"):
        df = df_prod[df_prod['ref'] != del_ref]
        save_to_sheet("products", df)
        st.rerun()

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

# 3. السجلات + الحذف
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
    
    df_logs = get_df("production_logs")
    st.dataframe(df_logs)
    if st.button("Supprimer la dernière ligne"):
        df = df_logs.iloc[:-1]
        save_to_sheet("production_logs", df)
        st.rerun()

# 4. الداشبورد + التحليل الذكي
with tab4:
    st.header("Tableau de Bord")
    df_logs = get_df("production_logs")
    df_plan = get_df("monthly_plan")
    
    # تحويل آمن للأرقام لتفادي ArrowTypeError
    if not df_logs.empty: df_logs['qty'] = pd.to_numeric(df_logs['qty'], errors='coerce').fillna(0)
    if not df_plan.empty: df_plan['target'] = pd.to_numeric(df_plan['target'], errors='coerce').fillna(0)

    all_months = sorted(df_plan['month'].unique()) if not df_plan.empty else []
    filter_dash = st.selectbox("Mois pour le rapport", ["Tous"] + all_months, key="dash_filter")
    if filter_dash != "Tous":
        df_plan = df_plan[df_plan['month'] == filter_dash]
        df_logs = df_logs[df_logs['date'].str.contains(filter_dash)]

    df_compare = pd.merge(df_plan.groupby('ref')['target'].sum().reset_index(), df_logs.groupby('ref')['qty'].sum().reset_index(), on='ref', how='outer').fillna(0)
    df_compare['Taux (%)'] = (df_compare['qty'] / df_compare['target'].replace(0, 1) * 100)
    df_compare.loc[df_compare['target'] == 0, 'Taux (%)'] = 0

    st.dataframe(df_compare.style.background_gradient(subset=['Taux (%)'], cmap='RdYlGn'), use_container_width=True)
    
    # تصدير Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer: df_compare.to_excel(writer, index=False)
    st.download_button("📥 Télécharger Rapport (Excel)", data=output.getvalue(), file_name="Rapport.xlsx")

    # تحليل AI آمن
    st.subheader("🤖 Analyse AI")
    if st.button("Analyser avec AI"):
        api_key = st.secrets.get("gemini_api_key") # استخدام الحروف الصغيرة كما اتفقتما
        if api_key:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(f"Analyse ces données de production : {df_compare.to_string()}")
            st.write(response.text)
        else:
            st.warning("⚠️ المفتاح 'gemini_api_key' غير موجود في الـ Secrets. تأكد من إضافته في إعدادات التطبيق.")