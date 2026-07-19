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

# 1. المنتجات
with tab1:
    st.header("Gestion des Produits")
    c1, c2 = st.columns(2)
    ref_p = c1.text_input("Référence")
    name_p = c2.text_input("Nom")
    if st.button("Ajouter Produit"):
        df = get_df("products")
        new_row = pd.DataFrame({'ref': [ref_p], 'name': [name_p]})
        save_to_sheet("products", pd.concat([df, new_row], ignore_index=True).drop_duplicates(subset='ref', keep='last'))
        st.rerun()
    df_prod = get_df("products")
    st.dataframe(df_prod)
    del_p = st.selectbox("Sélectionner produit à supprimer", df_prod['ref'].tolist() if not df_prod.empty else [])
    if st.button("Supprimer Produit"):
        save_to_sheet("products", df_prod[df_prod['ref'] != del_p])
        st.rerun()

# 2. الخطة (مع زر الحذف)
with tab2:
    st.header("Plan Mensuel")
    df_plan = get_df("monthly_plan")
    # التعديل: إدخال يدوي للكمية والسعر
    with st.expander("Ajouter/Modifier Plan"):
        m, r, t, p = st.columns(4)
        sel_date = m.date_input("Mois", value=datetime.date.today())
        ref = r.selectbox("Ref", options=get_df("products")['ref'].tolist())
        target = t.number_input("Target", value=0, min_value=0)
        price = p.number_input("Price", value=0.0, min_value=0.0)
        if st.button("Valider Plan"):
            df = get_df("monthly_plan")
            new_row = pd.DataFrame({'month':[sel_date.strftime("%Y-%m")], 'ref':[ref], 'target':[float(target)], 'price':[float(price)]})
            save_to_sheet("monthly_plan", pd.concat([df, new_row], ignore_index=True))
            st.rerun()
    st.dataframe(df_plan)
    if not df_plan.empty:
        idx_del = st.selectbox("Sélectionner ligne à supprimer", df_plan.index)
        if st.button("Supprimer Ligne Plan"):
            save_to_sheet("monthly_plan", df_plan.drop(idx_del))
            st.rerun()

# 3. السجلات (تحديد السطر للحذف)
with tab3:
    st.header("Saisie de Production")
    d, r, q = st.columns(3)
    date = d.date_input("Date")
    ref = r.selectbox("Ref", options=get_df("products")['ref'].tolist())
    qty = q.number_input("Qty", value=0)
    if st.button("Ajouter Log"):
        df = get_df("production_logs")
        save_to_sheet("production_logs", pd.concat([df, pd.DataFrame({'date':[str(date)], 'ref':[ref], 'qty':[float(qty)]})], ignore_index=True))
        st.rerun()
    df_logs = get_df("production_logs")
    st.dataframe(df_logs)
    if not df_logs.empty:
        idx_del_log = st.selectbox("Sélectionner Log à supprimer", df_logs.index)
        if st.button("Supprimer ce Log"):
            save_to_sheet("production_logs", df_logs.drop(idx_del_log))
            st.rerun()

# 4. الداشبورد (التقدم الإجمالي)
with tab4:
    st.header("Tableau de Bord")
    df_logs = get_df("production_logs")
    df_plan = get_df("monthly_plan")
    
    # فلتر حسب التاريخ أو الـ Ref
    filter_val = st.text_input("Recherche (Date ou Ref)")
    
    df_compare = pd.merge(df_plan.groupby('ref')['target'].sum().reset_index(), df_logs.groupby('ref')['qty'].sum().reset_index(), on='ref', how='outer').fillna(0)
    
    # التقدم الإجمالي
    total_target = df_compare['target'].sum()
    total_qty = df_compare['qty'].sum()
    progress = (total_qty / total_target * 100) if total_target > 0 else 0
    st.metric("Progression Globale", f"{progress:.2f}%")
    st.progress(min(progress/100, 1.0))

    st.dataframe(df_compare)