import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# إعداد الاتصال بـ Google Sheets
def get_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

client = get_client()
sheet = client.open("Production_DB")

def get_df(sheet_name):
    worksheet = sheet.worksheet(sheet_name)
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

def save_to_sheet(sheet_name, df):
    worksheet = sheet.worksheet(sheet_name)
    worksheet.clear()
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

st.set_page_config(layout="wide")
st.title("Gestion de Production (Cloud)")

tab1, tab2, tab3 = st.tabs(["Produits", "Plan", "Saisie"])

with tab1:
    st.header("Gestion des Produits")
    ref = st.text_input("Reference")
    name = st.text_input("Nom du produit")
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
    selected_ref = st.selectbox("Choisir le produit", df_prod['ref'].tolist() if not df_prod.empty else [])
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
    ref_prod = st.selectbox("Reference", df_prod['ref'].tolist() if not df_prod.empty else [])
    qty = st.number_input("Quantite produite", min_value=0)
    if st.button("Enregistrer"):
        df = get_df("production_logs")
        new_row = pd.DataFrame({'date': [str(date)], 'ref': [ref_prod], 'qty': [qty]})
        df = pd.concat([df, new_row], ignore_index=True)
        save_to_sheet("production_logs", df)
        st.success("Enregistré!")
    st.dataframe(get_df("production_logs"))