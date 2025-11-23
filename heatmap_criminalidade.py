import streamlit as st
import pandas as pd
import folium
import gspread
from folium.plugins import HeatMap, MarkerCluster
from streamlit_folium import st_folium
from google.oauth2.service_account import Credentials
from datetime import datetime


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

# =========================
# Registrar visita (APENAS 1 VEZ)
# =========================
if "visit_logged" not in st.session_state:
    st.session_state["visit_logged"] = False

if not st.session_state["visit_logged"]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    worksheet.append_row([now])
    st.session_state["visit_logged"] = True


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

1. Mapa de Calor (HeatMap): mostra a dens
