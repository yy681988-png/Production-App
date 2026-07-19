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

with tab1:
    st.header("Gestion des Produits")
    ref = st.text_input("Référence")
    name = st.text_input("Nom")
    if st.button("Ajouter Produit"):
        df = get_df("products")
        df = pd.concat([df, pd.DataFrame({'ref': [ref], 'name': [name]})], ignore_index=True).drop_duplicates(subset='ref', keep='last')
        save_to_sheet("products", df)
        st.rerun()
    st.dataframe(get_df("products"))

with tab2:
    st.header("Plan Mensuel")
    df_plan = get_df("monthly_plan")
    selected_row = st.selectbox("Choisir ligne à supprimer", df_plan.index)
    if st.button("Supprimer Plan"):
        save_to_sheet("monthly_plan", df_plan.drop(selected_row))
        st.rerun()
    st.dataframe(df_plan)

with tab3:
    st.header("Saisie de Production")
    df_logs = get_df("production_logs")
    selected_log = st.selectbox("Choisir ligne à supprimer", df_logs.index)
    if st.button("Supprimer Log"):
        save_to_sheet("production_logs", df_logs.drop(selected_log))
        st.rerun()
    st.dataframe(df_logs)

with tab4:
    st.header("Tableau de Bord")
    df = get_df("production_logs")
    if not df.empty:
        # البحث
        search = st.text_input("Rechercher (Référence)")
        if search: df = df[df['ref'].str.contains(search)]
        
        # مؤشرات
        col1, col2 = st.columns(2)
        col1.metric("Production Totale", df['qty'].sum())
        col2.metric("Nombre de lots", len(df))
        
        # رسوم بيانية
        c1, c2 = st.columns(2)
        fig_bar = px.bar(df, x='ref', y='qty', title="Production par Référence")
        c1.plotly_chart(fig_bar, use_container_width=True)
        
        fig_pie = px.pie(df, values='qty', names='ref', title="Répartition (%)")
        c2.plotly_chart(fig_pie, use_container_width=True)