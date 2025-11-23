import streamlit as st
import pandas as pd
import folium
import gspread
from folium.plugins import HeatMap, MarkerCluster
from streamlit_folium import st_folium
from streamlit.components.v1 import html
from google.oauth2.service_account import Credentials
from datetime import datetime
import uuid


# ==========================================
# 1. Função para detectar se o usuário é REAL
# ==========================================
def usuario_real():
    js_code = """
    <script>
        window.parent.postMessage({isUser: true}, "*");
    </script>
    """
    html(js_code, height=0)

    msg = st.experimental_get_query_params().get("user", [None])[0]
    return msg == "1"


# Listener que atualiza a URL com user=1 quando um navegador REAL carrega a página
st.markdown("""
<script>
window.addEventListener("message", (event) => {
    if (event.data.isUser === true) {
        const url = new URL(window.location.href);
        url.searchParams.set("user", "1");
        window.history.replaceState({}, "", url);
    }
});
</script>
""", unsafe_allow_html=True)

# =========================
# Conectar ao Google Sheets
# =========================
scope = ["https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive"]

credentials = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],  # <<< ALTERADO
    scopes=scope
)
gc = gspread.authorize(credentials)
sh = gc.open_by_key(st.secrets["sheets"]["sheet_id"])
worksheet = sh.sheet1  # primeira aba

# ==========================================================
# Registrar visita SOMENTE quando for usuário real
# ==========================================================
if usuario_real() and "visitor_id" not in st.session_state:

    st.session_state.visitor_id = str(uuid.uuid4())
    st.session_state.first_access_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # salvar no Google Sheets
    worksheet.append_row([st.session_state.visitor_id, st.session_state.first_access_time])

visitor_id = st.session_state.get("visitor_id", "—")
first_access_time = st.session_state.get("first_access_time", "—")


# =========================
# Configurações do Streamlit
# =========================
st.set_page_config(layout="wide")
st.title("Mapa de Crimes de Juazeiro-BA")
st.markdown("Visualize a localização dos crimes na cidade em um mapa interativo.")

# =========================
# CSV ZIP no GitHub
# =========================
GITHUB_URL = "https://raw.githubusercontent.com/uirasiqueira/heatmap_crime_juazeiro/main/raw.zip"

# =========================
# Função para carregar dados
# =========================
@st.cache_data
def load_data(url):
    try:
        df = pd.read_csv(url, compression='zip', encoding='latin1')

        # Normalização dos nomes das colunas
        df.columns = (
            df.columns
            .str.strip()
            .str.replace('\ufeff', '')  # remove BOM
            .str.upper()
        )

        # Corrigir LATITUDE e LONGITUDE
        df['LATITUDE'] = pd.to_numeric(df['LATITUDE'].astype(str).str.replace(',', '.'), errors='coerce')
        df['LONGITUDE'] = pd.to_numeric(df['LONGITUDE'].astype(str).str.replace(',', '.'), errors='coerce')

        # Filtrar Juazeiro-BA
        df_juazeiro = df[df['MUNICIPIO FATO'].str.contains('Juazeiro', case=False, na=False)]

        # Remover linhas sem coordenadas
        df_juazeiro = df_juazeiro.dropna(subset=['LATITUDE', 'LONGITUDE'])

        return df_juazeiro
    except Exception as e:
        st.error(f"Erro ao carregar CSV: {e}")
        return pd.DataFrame()

# Carregar dados
df_juazeiro = load_data(GITHUB_URL)

# Preview dos dados
if df_juazeiro.empty:
    st.stop()
else:
    st.markdown("""
Este dashboard apresenta a criminalidade em Juazeiro-BA a partir de dados oficiais. 
Ele oferece duas visualizações complementares:

1. Mapa de Calor (HeatMap): mostra a densidade de crimes por região.
2. Mapa Detalhado com Ícones: permite ver detalhes de cada ocorrência.

Estas duas perspectivas permitem tanto uma **análise macro** quanto **micro**.
""")


# =========================
# MAPAS LADO A LADO
# =========================
col1, col2 = st.columns(2)


# -----------------------------------
# MAPA 1 – HEATMAP
# -----------------------------------
with col1:
    st.subheader("Heatmap de Criminalidade")

    mapa_heat = folium.Map(
        location=[df_juazeiro['LATITUDE'].mean(), df_juazeiro['LONGITUDE'].mean()],
        zoom_start=12
    )

    heat_data = df_juazeiro[['LATITUDE', 'LONGITUDE']].values.tolist()

    HeatMap(
        heat_data,
        radius=18,
        blur=12,
        max_zoom=1,
        min_opacity=0.5
    ).add_to(mapa_heat)

    st_folium(mapa_heat, height=600, width="100%")


# -----------------------------------
# MAPA 2 – MARCADORES COM CLUSTER
# -----------------------------------
with col2:
    st.subheader("Mapa Detalhado com Marcadores")

    mapa_markers = folium.Map(
        location=[df_juazeiro['LATITUDE'].mean(), df_juazeiro['LONGITUDE'].mean()],
        zoom_start=12
    )

    cluster = MarkerCluster().add_to(mapa_markers)

    color_map = {
        "HOMICIDIO": "darkred",
        "ROUBO": "red",
        "FURTO": "blue",
        "AGRESSAO": "orange",
        "OUTROS": "green"
    }

    for idx, row in df_juazeiro.iterrows():
        if pd.notna(row['LATITUDE']) and pd.notna(row['LONGITUDE']):
            delito = str(row['DELITO']).strip().upper()
            cor = color_map.get(delito, "gray")

            popup_html = f"""
            <b>Delito:</b> {row['DELITO']}<br>
            <b>Bairro:</b> {row['BAIRRO']}<br>
            <b>Data:</b> {row['DATA_FATO']}<br>
            <b>Hora:</b> {row['HORA_FATO']}<br>
            <b>Idade:</b> {row['IDADE']}<br>
            <b>Vítima (iniciais):</b> {row['INICIAIS']}<br>
            <b>Ocupação:</b> {row['OCUPACAO']}
            """

            folium.Marker(
                location=[row['LATITUDE'], row['LONGITUDE']],
                icon=folium.Icon(icon="exclamation", prefix='fa', color=cor),
                popup=popup_html
            ).add_to(cluster)

    st_folium(mapa_markers, height=600, width="100%")
