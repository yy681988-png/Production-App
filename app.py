import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
import io

# ربط قاعدة البيانات
conn = sqlite3.connect('factory.db', check_same_thread=False)
c = conn.cursor()

# إنشاء الجداول
c.execute('CREATE TABLE IF NOT EXISTS products (ref TEXT PRIMARY KEY, name TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS monthly_plan (month TEXT, ref TEXT, target INTEGER, price REAL, PRIMARY KEY(month, ref))')
c.execute('CREATE TABLE IF NOT EXISTS production_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, ref TEXT, qty INTEGER)')
conn.commit()

# إعداد الصفحة
st.set_page_config(layout="wide")
st.title("Gestion de Production Pro")

tab1, tab2, tab3, tab4 = st.tabs(["Produits", "Plan", "Saisie", "Dashboard"])

# --- دالة التصدير ---
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    return output.getvalue()

with tab1:
    st.header("Gestion des Produits")
    ref = st.text_input("Reference")
    name = st.text_input("Nom du produit")
    if st.button("Ajouter Produit"):
        c.execute("INSERT OR REPLACE INTO products VALUES (?, ?)", (ref, name))
        conn.commit()
        st.success("Produit ajoute!")

with tab2:
    st.header("Plan Mensuel")
    month = st.text_input("Mois (ex: 2026-07)")
    refs = [r[0] for r in c.execute("SELECT ref FROM products").fetchall()]
    selected_ref = st.selectbox("Choisir le produit", refs)
    target = st.number_input("Quantite prevue", min_value=0)
    price = st.number_input("Prix total estime", min_value=0.0)
    if st.button("Valider le Plan"):
        c.execute("INSERT OR REPLACE INTO monthly_plan VALUES (?, ?, ?, ?)", (month, selected_ref, target, price))
        conn.commit()
        st.success("Plan mis a jour!")
    
    st.subheader("Plan Complet & Suppression")
    df_plan = pd.read_sql("SELECT * FROM monthly_plan", conn)
    st.dataframe(df_plan, use_container_width=True)
    
    # ميزة حذف سطر من الخطة
    to_del = st.selectbox("Choisir l'entree a supprimer", [f"{r[0]} | {r[1]}" for r in c.execute("SELECT month, ref FROM monthly_plan").fetchall()])
    if st.button("Supprimer cette ligne"):
        m, r = to_del.split(" | ")
        c.execute("DELETE FROM monthly_plan WHERE month=? AND ref=?", (m, r))
        conn.commit()
        st.rerun()

with tab3:
    st.header("Saisie de Production")
    date = st.date_input("Date")
    ref_prod = st.selectbox("Reference", [r[0] for r in c.execute("SELECT ref FROM products").fetchall()])
    qty = st.number_input("Quantite produite", min_value=0)
    if st.button("Enregistrer"):
        c.execute("INSERT INTO production_logs (date, ref, qty) VALUES (?, ?, ?)", (str(date), ref_prod, qty))
        conn.commit()
        st.success("Enregistre!")
    
    with st.expander("📂 Historique et Suppression"):
        df_logs = pd.read_sql("SELECT * FROM production_logs", conn)
        gb = GridOptionsBuilder.from_dataframe(df_logs)
        gb.configure_selection(selection_mode="single", use_checkbox=True)
        grid_options = gb.build()
        response = AgGrid(df_logs, gridOptions=grid_options, update_mode=GridUpdateMode.SELECTION_CHANGED)
        if response['selected_rows'] is not None and not response['selected_rows'].empty:
            log_id = int(response['selected_rows'].iloc[0, 0])
            if st.button("Supprimer la selection"):
                c.execute("DELETE FROM production_logs WHERE id=?", (log_id,))
                conn.commit()
                st.rerun()

with tab4:
    st.header("Analyse Globale")
    target_month = st.text_input("Mois a analyser (ex: 2026-07)")
    if st.button("Afficher Analyse"):
        df_plan = pd.read_sql(f"SELECT * FROM monthly_plan WHERE month='{target_month}'", conn)
        df_prod = pd.read_sql("SELECT ref, SUM(qty) as total FROM production_logs GROUP BY ref", conn)
        if not df_plan.empty:
            df = pd.merge(df_plan, df_prod, on="ref", how="left").fillna(0)
            global_prog = (df['total'].sum() / df['target'].sum()) * 100 if df['target'].sum() > 0 else 0
            col1, col2, col3 = st.columns(3)
            col3.metric("Avancement Global", f"{global_prog:.1f}%")
            st.progress(min(global_prog/100, 1.0))
            st.dataframe(df, use_container_width=True)
            st.download_button("📥 Exporter vers Excel", to_excel(df), f'Rapport_{target_month}.xlsx', 'application/vnd.ms-excel')
        else:
            st.error("Aucune donnee pour ce mois.")