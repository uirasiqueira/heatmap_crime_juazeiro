import streamlit as st
import pandas as pd
import folium
import gspread
from folium.plugins import HeatMap, MarkerCluster
from streamlit_folium import st_folium
from google.oauth2.service_account import Credentials
from datetime import datetime
import uuid
from user_agents import parse

# =========================
# 1. Conectar ao Google Sheets
# =========================
scope = ["https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive"]

credentials = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=scope
)
gc = gspread.authorize(credentials)
sh = gc.open_by_key(st.secrets["sheets"]["sheet_id"])
worksheet_visitas = sh.sheet1        # aba 1
worksheet_usuarios = sh.worksheet("usuarios")  # aba 2

# =========================
# 2. Capturar dados do usuário (server-side)
# =========================
def coletar_infos_usuario():
    user_agent_str = st.request.headers.get("user-agent", "")
    accept_language = st.request.headers.get("accept-language", "")
    
    ua = parse(user_agent_str)
    
    browser = f"{ua.browser.family} {ua.browser.version_string}"
    os = f"{ua.os.family} {ua.os.version_string}"
    device = "Mobile" if ua.is_mobile else "Tablet" if ua.is_tablet else "PC"
    language = accept_language.split(",")[0] if accept_language else "—"
    
    # Fuso horário não é garantido server-side; estimamos pelo locale do navegador se enviado
    timezone = "—"
    
    return {
        "browser": browser,
        "os": os,
        "device": device,
        "language": language,
        "timezone": timezone
    }

# =========================
# 3. Registrar visita SOMENTE uma vez
# =========================
if "visitor_id" not in st.session_state:
    st.session_state.visitor_id = str(uuid.uuid4())
    st.session_state.first_access_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    visitor_id = st.session_state.visitor_id
    first_access_time = st.session_state.first_access_time

    # Registrar visita (aba 1)
    worksheet_visitas.append_row([visitor_id, first_access_time])

    # Registrar informações do usuário (aba 2)
    user_info = coletar_infos_usuario()
    st.session_state["client_info"] = user_info
    worksheet_usuarios.append_row([
        visitor_id,
        first_access_time,
        user_info["browser"],
        user_info["os"],
        user_info["device"],
        user_info["language"],
        user_info["timezone"]
    ])
else:
    visitor_id = st.session_state.visitor_id
    first_access_time = st.session_state.first_access_time
    user_info = st.session_state.get("client_info", {})

# =========================
# 4. Interface do Streamlit
# =========================
st.set_page_config(layout="wide")
st.title("Mapa de Crimes de Juazeiro-BA")
st.markdown(f"📅 Primeiro acesso registrado em: **{first_access_time}** UTC")
st.markdown("Visualize a localização dos crimes na cidade em um mapa interativo.")

# =========================
# 5. Carregar dados do CSV ZIP
# =========================
GITHUB_URL = "https://raw.githubusercontent.com/uirasiqueira/heatmap_crime_juazeiro/main/raw.zip"

@st.cache_data
def load_data(url):
    try:
        df = pd.read_csv(url, compression='zip', encoding='latin1')

        df.columns = (
            df.columns
            .str.strip()
            .str.replace('\ufeff', '')
            .str.upper()
        )

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
# 6. Mapas lado a lado
# =========================
col1, col2 = st.columns(2)

# ----------------------------
# Mapa 1 – HeatMap
# ----------------------------
with col1:
    st.subheader("Heatmap de Criminalidade")
    mapa_heat = folium.Map(
        location=[df_juazeiro['LATITUDE'].mean(), df_juazeiro['LONGITUDE'].mean()],
        zoom_start=12
    )

    HeatMap(
        df_juazeiro[['LATITUDE', 'LONGITUDE']].values.tolist(),
        radius=18,
        blur=12,
        max_zoom=1,
        min_opacity=0.5
    ).add_to(mapa_heat)

    st_folium(mapa_heat, height=600, width="100%")

# ----------------------------
# Mapa 2 – Marcadores
# ----------------------------
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
