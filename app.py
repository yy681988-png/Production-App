import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px

# إعداد الاتصال
def get_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

client = get_client()
sheet = client.open_by_key("17y_KBs5xQqTY_63UtMC22Sxru7X9jxhg86LvM1WL9us")

def get_df(sheet_name):
    worksheet = sheet.worksheet(sheet_name)
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

def save_to_sheet(sheet_name, df):
    worksheet = sheet.worksheet(sheet_name)
    worksheet.clear()
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

# وظيفة تحميل البيانات إكسل
def download_excel(df, filename):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False)
    writer.close()
    return output.getvalue()

st.set_page_config(layout="wide")
st.title("Gestion de Production (Cloud Version)")

tab1, tab2, tab3, tab4 = st.tabs(["Produits", "Plan", "Saisie", "Dashboard"])

# 1. المنتجات مع الحذف
with tab1:
    st.header("Gestion des Produits")
    ref = st.text_input("Reference")
    name = st.text_input("Nom du produit")
    if st.button("Ajouter Produit"):
        df = get_df("products")
        new_row = pd.DataFrame({'ref': [ref], 'name': [name]})
        df = pd.concat([df, new_row], ignore_index=True).drop_duplicates(subset='ref', keep='last')
        save_to_sheet("products", df)
    
    df_prod = get_df("products")
    st.dataframe(df_prod)
    if st.button("Supprimer Produit"):
        df_prod = df_prod[df_prod['ref'] != ref]
        save_to_sheet("products", df_prod)

# 2. الخطة مع الحذف
with tab2:
    st.header("Plan Mensuel")
    df_plan = get_df("monthly_plan")
    st.dataframe(df_plan)
    if st.button("Supprimer Plan"):
        save_to_sheet("monthly_plan", pd.DataFrame(columns=['month', 'ref', 'target', 'price']))

# 3. السجلات مع التحميل وإكسل
with tab3:
    st.header("Saisie de Production")
    df_logs = get_df("production_logs")
    st.dataframe(df_logs)
    
    # زر تحميل إكسل
    import io
    st.download_button("Télécharger Excel", download_excel(df_logs, "logs.xlsx"), "logs.xlsx", "application/vnd.ms-excel")

# 4. الداشبورد
with tab4:
    st.header("Tableau de Bord")
    df_logs = get_df("production_logs")
    if not df_logs.empty:
        df_logs['qty'] = pd.to_numeric(df_logs['qty'])
        fig = px.bar(df_logs, x='ref', y='qty', title="Production par produit")
        st.plotly_chart(fig)