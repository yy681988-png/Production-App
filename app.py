import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
import datetime

SHEET_KEY = "17y_KBs5xQqTY_63UtMC22Sxru7X9jxhg86LvM1WL9us"

# ---------------------------------------------------------------------------
# Connexion (mise en cache avec cache_resource pour éviter de se reconnecter
# à Google à chaque interaction / rerun de Streamlit)
# ---------------------------------------------------------------------------
@st.cache_resource
def get_client():
    creds_dict = st.secrets["gcp_service_account"]
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)


@st.cache_resource
def get_sheet():
    try:
        return get_client().open_by_key(SHEET_KEY)
    except Exception as e:
        st.error(f"Impossible de se connecter à Google Sheets : {e}")
        st.stop()


sheet = get_sheet()


@st.cache_data(ttl=60)
def get_df(sheet_name):
    try:
        worksheet = sheet.worksheet(sheet_name)
        data = worksheet.get_all_values()
    except Exception as e:
        st.error(f"Erreur de lecture de la feuille '{sheet_name}' : {e}")
        return pd.DataFrame()

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data[1:], columns=data[0])
    if 'ref' in df.columns:
        df['ref'] = df['ref'].astype(str).str.replace("'", "", regex=False)
    return df


def ensure_columns(df, columns):
    """Garantit que les colonnes attendues existent, même si la feuille est vide."""
    if df.empty:
        return pd.DataFrame(columns=columns)
    for col in columns:
        if col not in df.columns:
            df[col] = None
    return df


def save_to_sheet(sheet_name, df):
    try:
        worksheet = sheet.worksheet(sheet_name)
        worksheet.clear()
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Erreur lors de l'enregistrement dans '{sheet_name}' : {e}")


def safe_drop(df, idx, sheet_name):
    """Supprime une ligne par index seulement si l'index existe réellement."""
    if idx in df.index:
        save_to_sheet(sheet_name, df.drop(idx).reset_index(drop=True))
        st.rerun()
    else:
        st.error("Index invalide : aucune ligne correspondante trouvée.")


st.set_page_config(layout="wide")
st.title("Gestion de Production Pro")

if st.sidebar.button("Actualiser les données (Refresh)"):
    st.cache_data.clear()
    st.rerun()

tab1, tab2, tab3, tab4 = st.tabs(["Produits", "Plan", "Saisie", "Dashboard"])

# ---------------------------------------------------------------------------
# 1. Produits
# ---------------------------------------------------------------------------
with tab1:
    st.header("Gestion des Produits")
    c1, c2 = st.columns(2)
    ref_p = c1.text_input("Référence", key="p_ref")
    name_p = c2.text_input("Nom", key="p_name")

    if st.button("Ajouter Produit"):
        if not ref_p.strip():
            st.error("La référence ne peut pas être vide.")
        else:
            df = ensure_columns(get_df("products"), ['ref', 'name'])
            new_row = pd.DataFrame({'ref': [ref_p], 'name': [name_p]})
            df = pd.concat([df, new_row], ignore_index=True).drop_duplicates(subset='ref', keep='last')
            save_to_sheet("products", df)
            st.rerun()

    df_products = get_df("products")
    st.dataframe(df_products)

    product_refs = df_products['ref'].tolist() if not df_products.empty and 'ref' in df_products.columns else []
    del_p = st.selectbox("Choisir Ref à supprimer", product_refs, key="del_prod")
    if st.button("Supprimer Produit"):
        if del_p:
            save_to_sheet("products", df_products[df_products['ref'] != del_p])
            st.rerun()
        else:
            st.warning("Aucun produit à supprimer.")

# ---------------------------------------------------------------------------
# 2. Plan mensuel
# ---------------------------------------------------------------------------
with tab2:
    st.header("Plan Mensuel")
    df_prods = get_df("products")
    product_list = df_prods['ref'].tolist() if not df_prods.empty and 'ref' in df_prods.columns else []

    m, r, t, p = st.columns(4)
    sel_date = m.date_input("Mois", value=datetime.date.today())
    month_val = sel_date.strftime("%Y-%m")
    ref = r.selectbox("Ref", options=product_list, key="plan_r")
    target = t.number_input("Target", value=0, key="plan_t")
    price = p.number_input("Price", value=0, key="plan_p")

    if st.button("Ajouter Plan"):
        if not ref:
            st.error("Veuillez choisir une référence.")
        else:
            df = ensure_columns(get_df("monthly_plan"), ['month', 'ref', 'target', 'price'])
            # Empêche les doublons pour le même mois + la même référence :
            # si une ligne existe déjà, on la met à jour au lieu de l'additionner.
            mask = (df['month'] == month_val) & (df['ref'] == ref)
            if mask.any():
                df.loc[mask, ['target', 'price']] = [float(target), float(price)]
                st.info("Une entrée existait déjà pour ce mois/référence : elle a été mise à jour.")
            else:
                new_row = pd.DataFrame({'month': [month_val], 'ref': [ref], 'target': [float(target)], 'price': [float(price)]})
                df = pd.concat([df, new_row], ignore_index=True)
            save_to_sheet("monthly_plan", df)
            st.rerun()

    df_plan = get_df("monthly_plan")
    st.dataframe(df_plan)

    idx = st.number_input("Indice ligne à supprimer (Plan)", min_value=0, step=1, key="plan_del")
    if st.button("Supprimer ligne Plan"):
        safe_drop(df_plan, idx, "monthly_plan")

# ---------------------------------------------------------------------------
# 3. Saisie de production
# ---------------------------------------------------------------------------
with tab3:
    st.header("Saisie de Production")
    df_prods = get_df("products")
    product_list = df_prods['ref'].tolist() if not df_prods.empty and 'ref' in df_prods.columns else []

    d, r, q = st.columns(3)
    date = d.date_input("Date", key="log_d")
    ref = r.selectbox("Ref", options=product_list, key="log_r")
    qty = q.number_input("Qty", value=0, key="log_q")

    if st.button("Ajouter Log"):
        if not ref:
            st.error("Veuillez choisir une référence.")
        else:
            df = ensure_columns(get_df("production_logs"), ['date', 'ref', 'qty'])
            new_row = pd.DataFrame({'date': [str(date)], 'ref': [ref], 'qty': [float(qty)]})
            df = pd.concat([df, new_row], ignore_index=True)
            save_to_sheet("production_logs", df)
            st.rerun()

    df_logs = get_df("production_logs")
    st.dataframe(df_logs)

    idx_l = st.number_input("Indice ligne à supprimer (Log)", min_value=0, step=1, key="log_del")
    if st.button("Supprimer ligne Log"):
        safe_drop(df_logs, idx_l, "production_logs")

# ---------------------------------------------------------------------------
# 4. Dashboard
# ---------------------------------------------------------------------------
with tab4:
    st.header("Tableau de Bord Comparatif")
    df_logs = ensure_columns(get_df("production_logs"), ['date', 'ref', 'qty'])
    df_plan = ensure_columns(get_df("monthly_plan"), ['month', 'ref', 'target', 'price'])

    df_logs['qty'] = pd.to_numeric(df_logs['qty'], errors='coerce').fillna(0)
    df_plan['target'] = pd.to_numeric(df_plan['target'], errors='coerce').fillna(0)
    df_plan['price'] = pd.to_numeric(df_plan['price'], errors='coerce').fillna(0)

    prod_grouped = df_logs.groupby('ref')['qty'].sum().reset_index() if not df_logs.empty else pd.DataFrame(columns=['ref', 'qty'])
    plan_grouped = df_plan.groupby('ref').agg(target=('target', 'sum'), price=('price', 'mean')).reset_index() if not df_plan.empty else pd.DataFrame(columns=['ref', 'target', 'price'])

    df_compare = pd.merge(plan_grouped, prod_grouped, on='ref', how='outer').fillna(0)

    if df_compare.empty:
        st.info("Aucune donnée disponible pour le moment.")
    else:
        # Taux de réalisation, en évitant la division par zéro
        df_compare['Taux (%)'] = (df_compare['qty'] / df_compare['target'].replace(0, 1) * 100)
        df_compare.loc[df_compare['target'] == 0, 'Taux (%)'] = 0

        # Chiffre d'affaires réalisé (qty x price), maintenant que 'price' est exploité
        df_compare['CA réalisé'] = df_compare['qty'] * df_compare['price']

        ref_search = st.multiselect("Filtrer par Ref", df_compare['ref'].unique(), key="dash_search")
        if ref_search:
            df_compare = df_compare[df_compare['ref'].isin(ref_search)]

        c1, c2, c3 = st.columns(3)
        c1.metric("Objectif Total", int(df_compare['target'].sum()))
        c2.metric("Production Totale", int(df_compare['qty'].sum()))

        total_target = df_compare['target'].sum()
        total_qty = df_compare['qty'].sum()
        total_perc = (total_qty / total_target * 100) if total_target > 0 else 0
        c3.metric("Performance Globale", f"{total_perc:.1f}%")

        st.divider()
        st.subheader("Détail par Produit")
        st.dataframe(
            df_compare.style.background_gradient(subset=['Taux (%)'], cmap='RdYlGn'),
            column_config={
                "target": st.column_config.NumberColumn("Target", format="%d"),
                "qty": st.column_config.NumberColumn("Qty", format="%d"),
                "Taux (%)": st.column_config.NumberColumn("Taux (%)", format="%.2f"),
                "CA réalisé": st.column_config.NumberColumn("CA réalisé", format="%.2f"),
            },
            use_container_width=True
        )

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