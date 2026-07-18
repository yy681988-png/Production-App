import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# إعداد الاتصال بـ Google Sheets
def get_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

client = get_client()

# فتح الملف باستخدام الـ ID الخاص بك مباشرة
sheet = client.open_by_key("17y_KBs5xQqTY_63UtMC22Sxru7X9jxhg86LvM1WL9us")

def get_df(sheet_name):
    worksheet = sheet.worksheet(sheet_name)
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

def save_to_sheet(sheet_name, df):
    worksheet = sheet.worksheet(sheet_name)
    worksheet.clear()
    # إضافة العناوين ثم البيانات
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

st.set_page_config(layout="wide")
st.title("Gestion de Production (Cloud)")

tab1, tab2, tab3 = st.tabs(["Produits", "Plan", "Saisie"])

with tab1:
    st.header("Gestion des Produits")
    ref = st.text_input("Reference", key="ref_prod")
    name = st.text_input("Nom du produit", key="name_prod")
    if st.button("Ajouter Produit"):
        df = get_df("products")
        new_row = pd.DataFrame({'ref': [ref], 'name': [name]})
        df = pd.concat([df, new_row], ignore_index=True).drop_duplicates(subset='ref', keep='last')
        save_to_sheet("products", df)
        st.success("Produit ajouté!")
    st.dataframe(get_df("products"))

with tab2:
    st.header("Plan Mensuel")
    df_prod = get_df("products")
    month = st.text_input("Mois (ex: 2026-07)")
    # استخدام قائمة المراجع الموجودة في ورقة المنتجات
    ref_list = df_prod['ref'].tolist() if not df_prod.empty else []
    selected_ref = st.selectbox("Choisir le produit", ref_list)
    target = st.number_input("Quantite prevue", min_value=0)
    price = st.number_input("Prix total", min_value=0.0)
    if st.button("Valider le Plan"):
        df = get_df("monthly_plan")
        new_row = pd.DataFrame({'month': [month], 'ref': [selected_ref], 'target': [target], 'price': [price]})
        df = pd.concat([df, new_row], ignore_index=True)
        save_to_sheet("monthly_plan", df)
        st.success("Plan mis à jour!")
    st.dataframe(get_df("monthly_plan"))

with tab3:
    st.header("Saisie de Production")
    date = st.date_input("Date")
    ref_prod = st.selectbox("Reference", ref_list)
    qty = st.number_input("Quantite produite", min_value=0)
    if st.button("Enregistrer"):
        df = get_df("production_logs")
        new_row = pd.DataFrame({'date': [str(date)], 'ref': [ref_prod], 'qty': [qty]})
        df = pd.concat([df, new_row], ignore_index=True)
        save_to_sheet("production_logs", df)
        st.success("Enregistré!")
    st.dataframe(get_df("production_logs"))