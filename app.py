import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
import datetime

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

if st.sidebar.button("Actualiser les données (Refresh)"):
    st.cache_data.clear()
    st.rerun()

tab1, tab2, tab3, tab4 = st.tabs(["Produits", "Plan", "Saisie", "Dashboard"])

# 1. المنتجات
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
    st.dataframe(get_df("products"))
    del_p = st.selectbox("Choisir Ref à supprimer", get_df("products")['ref'].tolist() if not get_df("products").empty else [], key="del_prod")
    if st.button("Supprimer Produit"):
        save_to_sheet("products", get_df("products")[get_df("products")['ref'] != del_p])
        st.rerun()

# 2. الخطة الشهرية
with tab2:
    st.header("Plan Mensuel")
    df_prods = get_df("products")
    product_list = df_prods['ref'].tolist() if not df_prods.empty else []
    
    m, r, t, p = st.columns(4)
    sel_date = m.date_input("Mois", value=datetime.date.today())
    month_val = sel_date.strftime("%Y-%m")
    ref = r.selectbox("Ref", options=product_list, key="plan_r")
    target = t.number_input("Target", value=0, key="plan_t")
    price = p.number_input("Price", value=0, key="plan_p")
    
    if st.button("Ajouter Plan"):
        df = get_df("monthly_plan")
        new_row = pd.DataFrame({'month':[month_val], 'ref':[ref], 'target':[float(target)], 'price':[float(price)]})
        df = pd.concat([df, new_row], ignore_index=True)
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
    df_prods = get_df("products")
    product_list = df_prods['ref'].tolist() if not df_prods.empty else []
    
    d, r, q = st.columns(3)
    date = d.date_input("Date", key="log_d")
    ref = r.selectbox("Ref", options=product_list, key="log_r")
    qty = q.number_input("Qty", value=0, key="log_q")
    
    if st.button("Ajouter Log"):
        df = get_df("production_logs")
        new_row = pd.DataFrame({'date':[str(date)], 'ref':[ref], 'qty':[float(qty)]})
        df = pd.concat([df, new_row], ignore_index=True)
        save_to_sheet("production_logs", df)
        st.rerun()
    st.dataframe(get_df("production_logs"))
    idx_l = st.number_input("Indice ligne à supprimer (Log)", min_value=0, step=1, key="log_del")
    if st.button("Supprimer ligne Log"):
        save_to_sheet("production_logs", get_df("production_logs").drop(idx_l))
        st.rerun()

# 4. الداشبورد الاحترافي
with tab4:
    st.header("Tableau de Bord Comparatif")
    df_logs = get_df("production_logs")
    df_plan = get_df("monthly_plan")
    
    if not df_logs.empty: df_logs['qty'] = pd.to_numeric(df_logs['qty'])
    if not df_plan.empty: df_plan['target'] = pd.to_numeric(df_plan['target'])

    prod_grouped = df_logs.groupby('ref')['qty'].sum().reset_index()
    plan_grouped = df_plan.groupby('ref')['target'].sum().reset_index()
    
    df_compare = pd.merge(plan_grouped, prod_grouped, on='ref', how='outer').fillna(0)
    df_compare['Taux (%)'] = (df_compare['qty'] / df_compare['target'] * 100).replace([float('inf'), -float('inf')], 0)

    ref_search = st.multiselect("Filtrer par Ref", df_compare['ref'].unique(), key="dash_search")
    if ref_search:
        df_compare = df_compare[df_compare['ref'].isin(ref_search)]

    c1, c2, c3 = st.columns(3)
    c1.metric("Objectif Total", int(df_compare['target'].sum()))
    c2.metric("Production Totale", int(df_compare['qty'].sum()))
    total_perc = (df_compare['qty'].sum() / df_compare['target'].sum() * 100) if df_compare['target'].sum() > 0 else 0
    c3.metric("Performance Globale", f"{total_perc:.1f}%")

    st.divider()
    st.subheader("Détail par Produit")
    st.dataframe(
        df_compare.style.background_gradient(subset=['Taux (%)'], cmap='RdYlGn'),
        column_config={
            "target": st.column_config.NumberColumn("Target", format="%d"),
            "qty": st.column_config.NumberColumn("Qty", format="%d"),
            "Taux (%)": st.column_config.NumberColumn("Taux (%)", format="%.2f")
        },
        use_container_width=True
    )
    
    # الرسم البياني الاحترافي
    fig = px.bar(
        df_compare, 
        x='ref', 
        y=['target', 'qty'], 
        barmode='group',
        title="Performance par Référence",
        text_auto='.2s',
        color_discrete_map={"target": "#3498db", "qty": "#2ecc71"}
    )
    fig.update_xaxes(type='category')
    fig.update_layout(template="plotly_dark", legend_title="Indicateur")
    st.plotly_chart(fig, use_container_width=True)