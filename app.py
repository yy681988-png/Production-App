import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px

# إعداد الاتصال
def get_client():
    creds_dict = st.secrets["gcp_service_account"]
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

client = get_client()
sheet = client.open_by_key("17y_KBs5xQqTY_63UtMC22Sxru7X9jxhg86LvM1WL9us")

@st.cache_data(ttl=60)
def get_df(sheet_name):
    df = pd.DataFrame(sheet.worksheet(sheet_name).get_all_records())
    # تعديل لقراءة الـ ref كنص دائمًا للحفاظ على الأصفار
    if 'ref' in df.columns:
        df['ref'] = df['ref'].astype(str)
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
        df = pd.concat([df, pd.DataFrame({'ref': [ref_p], 'name': [name_p]})], ignore_index=True).drop_duplicates(subset='ref', keep='last')
        save_to_sheet("products", df)
        st.rerun()
    st.dataframe(get_df("products"))
    del_p = st.selectbox("Choisir Ref à supprimer", get_df("products")['ref'].tolist() if not get_df("products").empty else [], key="del_prod")
    if st.button("Supprimer Produit"):
        save_to_sheet("products", get_df("products")[get_df("products")['ref'] != del_p])
        st.rerun()

# 2. الخطة الشهرية
with tab2:
    st.header("Plan Mensuel")
    m, r, t, p = st.columns(4)
    month = m.text_input("Mois", key="plan_m")
    ref = r.text_input("Ref", key="plan_r")
    target = t.number_input("Target", value=0, key="plan_t")
    price = p.number_input("Price", value=0, key="plan_p")
    if st.button("Ajouter Plan"):
        df = get_df("monthly_plan")
        df = pd.concat([df, pd.DataFrame({'month':[month], 'ref':[ref], 'target':[target], 'price':[price]})], ignore_index=True)
        save_to_sheet("monthly_plan", df)
        st.rerun()
    st.dataframe(get_df("monthly_plan"))
    idx = st.number_input("Indice ligne à supprimer (Plan)", min_value=0, step=1, key="plan_del")
    if st.button("Supprimer ligne Plan"):
        save_to_sheet("monthly_plan", get_df("monthly_plan").drop(idx))
        st.rerun()

# 3. السجلات
with tab3:
    st.header("Saisie de Production")
    d, r, q = st.columns(3)
    date = d.date_input("Date", key="log_d")
    ref = r.text_input("Ref", key="log_r")
    qty = q.number_input("Qty", value=0, key="log_q")
    if st.button("Ajouter Log"):
        df = get_df("production_logs")
        df = pd.concat([df, pd.DataFrame({'date':[str(date)], 'ref':[ref], 'qty':[qty]})], ignore_index=True)
        save_to_sheet("production_logs", df)
        st.rerun()
    st.dataframe(get_df("production_logs"))
    idx_l = st.number_input("Indice ligne à supprimer (Log)", min_value=0, step=1, key="log_del")
    if st.button("Supprimer ligne Log"):
        save_to_sheet("production_logs", get_df("production_logs").drop(idx_l))
        st.rerun()

# 4. الداشبورد
with tab4:
    st.header("Tableau de Bord")
    df_logs = get_df("production_logs")
    df_plan = get_df("monthly_plan")
    
    if not df_logs.empty and 'ref' in df_logs.columns:
        ref_search = st.multiselect("Filtrer par Ref", df_logs['ref'].unique(), key="dash_search")
        if ref_search:
            df_logs = df_logs[df_logs['ref'].isin(ref_search)]
            df_plan = df_plan[df_plan['ref'].isin(ref_search)]
        
        total_prod = df_logs['qty'].sum()
        total_target = df_plan['target'].sum() if not df_plan.empty and 'target' in df_plan.columns else 0
        completion = (total_prod / total_target * 100) if total_target > 0 else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Production Totale", total_prod)
        c2.metric("Objectif Total", total_target)
        c3.metric("Taux d'accomplissement", f"{completion:.1f}%")
        st.plotly_chart(px.bar(df_logs, x='ref', y='qty', title="Production par Ref"))
    else:
        st.warning("Aucune donnée disponible pour le dashboard.")