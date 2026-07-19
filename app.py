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

# تبويب المنتجات
with tab1:
    st.header("Gestion des Produits")
    c1, c2 = st.columns(2)
    ref = c1.text_input("Référence")
    name = c2.text_input("Nom")
    if st.button("Ajouter Produit"):
        df = get_df("products")
        df = pd.concat([df, pd.DataFrame({'ref': [ref], 'name': [name]})], ignore_index=True).drop_duplicates(subset='ref', keep='last')
        save_to_sheet("products", df)
        st.rerun()
    st.dataframe(get_df("products"))
    if st.button("Supprimer Produit"):
        df = get_df("products")
        save_to_sheet("products", df[df['ref'] != ref])
        st.rerun()

# تبويب الخطة
with tab2:
    st.header("Plan Mensuel")
    m, r, t, p = st.columns(4)
    month = m.text_input("Mois")
    ref = r.text_input("Ref")
    target = t.number_input("Target", value=0)
    price = p.number_input("Price", value=0)
    if st.button("Ajouter Plan"):
        df = get_df("monthly_plan")
        df = pd.concat([df, pd.DataFrame({'month':[month], 'ref':[ref], 'target':[target], 'price':[price]})], ignore_index=True)
        save_to_sheet("monthly_plan", df)
        st.rerun()
    st.dataframe(get_df("monthly_plan"))
    idx = st.number_input("Indice ligne à supprimer (Plan)", min_value=0, step=1)
    if st.button("Supprimer ligne Plan"):
        save_to_sheet("monthly_plan", get_df("monthly_plan").drop(idx))
        st.rerun()

# تبويب السجلات
with tab3:
    st.header("Saisie de Production")
    d, r, q = st.columns(3)
    date = d.date_input("Date")
    ref = r.text_input("Ref")
    qty = q.number_input("Qty", value=0)
    if st.button("Ajouter Log"):
        df = get_df("production_logs")
        df = pd.concat([df, pd.DataFrame({'date':[str(date)], 'ref':[ref], 'qty':[qty]})], ignore_index=True)
        save_to_sheet("production_logs", df)
        st.rerun()
    st.dataframe(get_df("production_logs"))
    idx_log = st.number_input("Indice ligne à supprimer (Log)", min_value=0, step=1)
    if st.button("Supprimer ligne Log"):
        save_to_sheet("production_logs", get_df("production_logs").drop(idx_log))
        st.rerun()

# تبويب الداشبورد
with tab4:
    st.header("Tableau de Bord")
    df = get_df("production_logs")
    if not df.empty:
        search = st.text_input("Rechercher par Ref")
        if search: df = df[df['ref'].str.contains(search)]
        
        col1, col2 = st.columns(2)
        col1.metric("Production Totale", df['qty'].sum())
        col2.plotly_chart(px.pie(df, values='qty', names='ref', title="Répartition (%)"))