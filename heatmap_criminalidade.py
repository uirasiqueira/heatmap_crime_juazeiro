import streamlit as st
import pandas as pd
import folium
from folium.plugins import HeatMap, MarkerCluster
from streamlit_folium import st_folium
from streamlit.components.v1 import html
from google.oauth2.service_account import Credentials
from datetime import datetime
import uuid
import json

# =========================
# Função para coletar info do navegador
# =========================
def coletar_info_cliente():
    js = """
    <script>
    const info = {
        userAgent: navigator.userAgent,
        platform: navigator.platform,
        language: navigator.language,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
    };
    const jsonText = JSON.stringify(info);
    window.parent.postMessage({clientInfo: jsonText}, "*");
    </script>
    """
    html(js, height=0)

# Listener para salvar dados enviados pelo navegador
st.markdown("""
<script>
window.addEventListener("message", (event) => {
    if (event.data.clientInfo) {
        const url = new URL(window.location.href);
        url.searchParams.set("client_info", event.data.clientInfo);
        window.history.replaceState({}, "", url);
    }
});
</script>
""", unsafe_allow_html=True)

# =========================
# Detectar usuário real
# =========================
def usuario_real():
    js_code = """
    <script>
        window.parent.postMessage({isUser: true}, "*");
    </script>
    """
    html(js_code, height=0)
    msg = st.experimental_get_query_params().get("user", [None])[0]
    return msg == "1"

# Atualiza URL com user=1 para navegador real
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
    st.secrets["gcp_service_account"],
    scopes=scope
)
gc = gspread.authorize(credentials)

sh = gc.open_by_key(st.secrets["sheets"]["sheet_id"])
worksheet_visitas = sh.sheet1   # aba 1: visitas
worksheet_usuarios = sh.worksheet("usuarios")  # aba 2: informações do usuário

# =========================
# Registrar visita + info do usuário
# =========================
coletar_info_cliente()

query_params = st.experimental_get_query_params()
client_info_json = query_params.get("client_info", [None])[0]

if client_info_json:
    try:
        client_info = json.loads(client_info_json)
        st.session_state["client_info"] = client_info
    except:
        pass

if usuario_real() and "visitor_id" not in st.session_state:
    st.session_state.visitor_id = str(uuid.uuid4())
    st.session_state.first_access_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Registrar visita (aba 1)
    worksheet_visitas.append_row([
        st.session_state.visitor_id,
        st.session_state.first_access_time
    ])

    # Registrar informações do navegador (aba 2)
    info = st.session_state.get("client_info", {})
    worksheet_usuarios.append_row([
        st.session_state.visitor_id,
        st.session_state.first_access_time,
        info.get("userAgent", "—"),
        info.get("platform", "—"),
        info.get("language", "—"),
        info.get("timezone", "—")
    ])

visitor_id = st.session_state.get("visitor_id", "—")
first_access_time = st.session_state.get("first_access_time", "—")

# =========================
# Interface
# =========================
st.set_page_config(layout="wide")
st.title("Mapa de Crimes de Juazeiro-BA")
st.markdown("Visualize a localização dos crimes na cidade em um mapa interativo.")

# =========================
# Carregar dados CSV ZIP
# =========================
GITHUB_URL = "https://raw.githubusercontent.com/uirasiqueira/heatmap_crime_juazeiro/main/raw.zip"

@st.cache_data
def load_data(url):
    try:
        df = pd.read_csv(url, compression='zip', encoding='latin1')
        df.columns = df.columns.str.strip().str.replace('\ufeff','').str.upper()
        df['LATITUDE'] = pd.to_numeric(df['LATITUDE'].astype(str).str.replace(',', '.'), errors='coerce')
        df['LONGITUDE'] = pd.to_numeric(df['LONGITUDE'].astype(str).str.replace(',', '.'), errors='coerce')
        df_juazeiro = df[df['MUNICIPIO FATO'].str.contains('Juazeiro', case=False, na=False)]
        df_juazeiro = df_juazeiro.dropna(subset=['LATITUDE', 'LONGITUDE'])
        return df_juazeiro
    except Exception as e:
        st.error(f"Erro ao carregar CSV: {e}")
        return pd.DataFrame()

df_juazeiro = load_data(GITHUB_URL)

if df_juazeiro.empty:
    st.stop()
else:
    st.markdown("""
Este dashboard apresenta a criminalidade em Juazeiro-BA a partir de dados oficiais.  
Ele oferece duas visualizações complementares:

1. **Mapa de Calor:** mostra áreas com maior concentração de crimes.  
2. **Mapa Detalhado:** exibe cada ocorrência individualmente, com ícone colorido por tipo de delito.
""")

# =========================
# Mapas lado a lado
# =========================
col1, col2 = st.columns(2)

# --- HeatMap ---
with col1:
    st.subheader("Heatmap de Criminalidade")
    mapa_heat = folium.Map(
        location=[df_juazeiro['LATITUDE'].mean(), df_juazeiro['LONGITUDE'].mean()],
        zoom_start=12
    )
    HeatMap(
        df_juazeiro[['LATITUDE','LONGITUDE']].values.tolist(),
        radius=18,
        blur=12,
        max_zoom=1,
        min_opacity=0.5
    ).add_to(mapa_heat)
    st_folium(mapa_heat, height=600, width="100%")

# --- Mapa Detalhado ---
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
        delito = str(row['DELITO']).strip().upper()
        cor = color_map.get(delito, "gray")
        popup_html = f"""
        <b>Delito:</b> {row['DELITO']}<br>
        <b>Bairro:</b> {row['BAIRRO']}<br>
        <b>Data:</b> {row['DATA_FATO']}<br>
        <b>Hora:</b> {row['HORA_FATO']}<br>
        <b>Idade:</b> {row['IDADE']}<br>
        <b>Iniciais da vítima:</b> {row['INICIAIS']}<br>
        <b>Ocupação:</b> {row['OCUPACAO']}
        """
        folium.Marker(
            location=[row['LATITUDE'], row['LONGITUDE']],
            icon=folium.Icon(icon="exclamation", prefix='fa', color=cor),
            popup=popup_html
        ).add_to(cluster)

    st_folium(mapa_markers, height=600, width="100%")
