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
    return pd.DataFrame(sheet.worksheet(sheet_name).get_all_records())

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
    ref_p = st.text_input("Référence", key="p_ref")
    name_p = st.text_input("Nom", key="p_name")
    if st.button("Ajouter"):
        df = get_df("products")
        df = pd.concat([df, pd.DataFrame({'ref': [ref_p], 'name': [name_p]})], ignore_index=True).drop_duplicates(subset='ref', keep='last')
        save_to_sheet("products", df)
        st.rerun()
    
    df_p = get_df("products")
    st.dataframe(df_p)
    del_p = st.selectbox("Choisir Ref à supprimer", df_p['ref'].tolist() if not df_p.empty else [])
    if st.button("Supprimer Produit"):
        save_to_sheet("products", df_p[df_p['ref'] != del_p])
        st.rerun()

# 2. الخطة
with tab2:
    # (نفس منطق الإضافة السابق...)
    df_plan = get_df("monthly_plan")
    st.dataframe(df_plan)
    idx = st.number_input("Indice ligne à supprimer", min_value=0, step=1, key="del_plan")
    if st.button("Supprimer Plan"):
        save_to_sheet("monthly_plan", df_plan.drop(idx))
        st.rerun()

# 3. السجلات
with tab3:
    # (نفس منطق الإضافة السابق...)
    df_log = get_df("production_logs")
    st.dataframe(df_log)
    idx_l = st.number_input("Indice ligne à supprimer", min_value=0, step=1, key="del_log")
    if st.button("Supprimer Log"):
        save_to_sheet("production_logs", df_log.drop(idx_l))
        st.rerun()

# 4. الداشبورد المتقدم
with tab4:
    df_logs = get_df("production_logs")
    df_plan = get_df("monthly_plan")
    
    # فلاتر
    col_f1, col_f2 = st.columns(2)
    ref_search = col_f1.multiselect("Filtrer par Ref", df_logs['ref'].unique())
    
    if ref_search:
        df_logs = df_logs[df_logs['ref'].isin(ref_search)]
        df_plan = df_plan[df_plan['ref'].isin(ref_search)]

    # حسابات
    total_prod = df_logs['qty'].sum()
    total_target = df_plan['target'].sum() if not df_plan.empty else 0
    completion = (total_prod / total_target * 100) if total_target > 0 else 0
    
    # عرض المؤشرات
    c1, c2, c3 = st.columns(3)
    c1.metric("Production Totale", total_prod)
    c2.metric("Objectif Total", total_target)
    c3.metric("Taux d'accomplissement", f"{completion:.1f}%")
    
    st.plotly_chart(px.bar(df_logs, x='ref', y='qty', color='ref', title="Production par Ref"))