import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
import io

# إعداد الاتصال
def get_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

client = get_client()
sheet = client.open_by_key("17y_KBs5xQqTY_63UtMC22Sxru7X9jxhg86LvM1WL9us")

# دالة قراءة البيانات مع التخزين المؤقت لتسريع التطبيق
@st.cache_data(ttl=60)
def get_df(sheet_name):
    worksheet = sheet.worksheet(sheet_name)
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

def save_to_sheet(sheet_name, df):
    worksheet = sheet.worksheet(sheet_name)
    worksheet.clear()
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())
    st.cache_data.clear() # مسح التخزين لتحديث البيانات فورياً

def download_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

st.set_page_config(layout="wide")
st.title("Gestion de Production (Cloud)")

tab1, tab2, tab3, tab4 = st.tabs(["Produits", "Plan", "Saisie", "Dashboard"])

with tab1:
    st.header("Gestion des Produits")
    ref = st.text_input("Référence à supprimer ou ajouter")
    name = st.text_input("Nom du produit")
    col1, col2 = st.columns(2)
    if col1.button("Ajouter Produit"):
        df = get_df("products")
        new_row = pd.DataFrame({'ref': [ref], 'name': [name]})
        df = pd.concat([df, new_row], ignore_index=True).drop_duplicates(subset='ref', keep='last')
        save_to_sheet("products", df)
        st.rerun()
    if col2.button("Supprimer Produit"):
        df = get_df("products")
        df = df[df['ref'] != ref]
        save_to_sheet("products", df)
        st.rerun()
    st.dataframe(get_df("products"))

with tab2:
    st.header("Plan Mensuel")
    month = st.text_input("Mois (ex: 2026-07)")
    df_prod = get_df("products")
    ref_list = df_prod['ref'].tolist() if not df_prod.empty else []
    selected_ref = st.selectbox("Choisir le produit", ref_list)
    target = st.number_input("Quantite prevue", min_value=0)
    price = st.number_input("Prix total", min_value=0.0)
    if st.button("Valider le Plan"):
        df = get_df("monthly_plan")
        new_row = pd.DataFrame({'month': [month], 'ref': [selected_ref], 'target': [target], 'price': [price]})
        df = pd.concat([df, new_row], ignore_index=True)
        save_to_sheet("monthly_plan", df)
        st.rerun()
    st.dataframe(get_df("monthly_plan"))

with tab3:
    st.header("Saisie de Production")
    date = st.date_input("Date")
    ref_prod = st.selectbox("Référence", ref_list)
    qty = st.number_input("Quantité produite", min_value=0)
    if st.button("Enregistrer"):
        df = get_df("production_logs")
        new_row = pd.DataFrame({'date': [str(date)], 'ref': [ref_prod], 'qty': [qty]})
        df = pd.concat([df, new_row], ignore_index=True)
        save_to_sheet("production_logs", df)
        st.rerun()
    df_logs = get_df("production_logs")
    st.download_button("Télécharger Excel", download_excel(df_logs), "production.xlsx", "application/vnd.ms-excel")
    st.dataframe(df_logs)

with tab4:
    st.header("Tableau de Bord")
    df_logs = get_df("production_logs")
    if not df_logs.empty:
        fig = px.bar(df_logs, x='ref', y='qty', color='ref', title="Production totale par produit")
        st.plotly_chart(fig, use_container_width=True)