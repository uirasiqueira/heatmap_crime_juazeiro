import streamlit as st
import pandas as pd
import folium
from folium.plugins import HeatMap, MarkerCluster
from streamlit_folium import st_folium

# =========================
# Configurações do Streamlit
# =========================
st.set_page_config(layout="wide")
st.title("Mapa de Crimes de Juazeiro")
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
    ### Sobre os dados
    Este conjunto contém registros de ocorrências policiais na cidade de Juazeiro (BA).  
    A base inclui informações como:
    - Tipo de delito  
    - Bairro  
    - Data e hora do fato  
    - Coordenadas geográficas (latitude e longitude)  

    O mapa abaixo utiliza essas coordenadas para gerar uma visualização de calor das áreas com maior concentração de ocorrências.
    """)

# =========================
# Criar mapa
# =========================
mapa = folium.Map(
    location=[df_juazeiro['LATITUDE'].mean(), df_juazeiro['LONGITUDE'].mean()],
    zoom_start=12
)

# Criar HeatMap mais escuro e intenso
heat_data = df_juazeiro[['LATITUDE', 'LONGITUDE']].values.tolist()

HeatMap(
    heat_data,
    radius=18,          # aumenta o tamanho dos pontos
    blur=12,            # deixa mais definido
    max_zoom=1,         # intensifica contraste
    min_opacity=0.5,    # aumenta visibilidade
).add_to(mapa)

# Exibir mapa no Streamlit
st.subheader("Mapa de Crimes - HeatMap (Intenso)")
st_folium(mapa, width=900, height=600)


# =========================
# MAPA 2: Marcadores Interativos com Cluster e Cores
# =========================
st.subheader("Mapa 2: Pontos de Criminalidade Detalhados (ícones)")

mapa_markers = folium.Map(
    location=[df_juazeiro['LATITUDE'].mean(), df_juazeiro['LONGITUDE'].mean()],
    zoom_start=12
)

cluster = MarkerCluster().add_to(mapa_markers)

# Cores para cada tipo de delito (usadas no icon color)
color_map = {
    "HOMICIDIO": "darkred",
    "ROUBO": "red",
    "FURTO": "blue",
    "AGRESSAO": "orange",
    "OUTROS": "green"
}

for idx, row in df_juazeiro.iterrows():
    if pd.notna(row['LATITUDE']) and pd.notna(row['LONGITUDE']):
        # Normalizar nome do delito
        delito = str(row['DELITO']).strip().upper()
        cor = color_map.get(delito, "gray")  # cinza se não definido

        popup_html = f"""
        <b>Delito:</b> {row['DELITO']}<br>
        <b>Bairro:</b> {row['BAIRRO']}<br>
        <b>Data:</b> {row['DATA_FATO']}<br>
        <b>Hora:</b> {row['HORA_FATO']}<br>
        <b>Idade:</b> {row['IDADE']}<br>
        <b>Agente (iniciais):</b> {row['INICIAIS']}<br>
        <b>Ocupação:</b> {row['OCUPACAO']}
        """

        folium.Marker(
            location=[row['LATITUDE'], row['LONGITUDE']],
            icon=folium.Icon(icon="exclamation", prefix='fa', color=cor),
            popup=popup_html
        ).add_to(cluster)

st_folium(mapa_markers, width=900, height=600)
