import json
import os
import re
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

GRIS = "#B9C3D1"
AZUL = "#1C4C9A"
ARCHIVO = Path(__file__).parent / "respuesta.json"
URL = "https://api.nasa.gov/neo/rest/v1/feed"

st.set_page_config(page_title="Asteroides cercanos a la Tierra", page_icon="☄️", layout="wide")


def aplanar(datos: dict) -> pd.DataFrame:
    filas = []
    for fecha, asteroides in datos["near_earth_objects"].items():
        for a in asteroides:
            ap = a["close_approach_data"][0]
            filas.append(
                {
                    "id": a["id"],
                    "nombre": a["name"].strip("()"),
                    "fecha": fecha,
                    "diametro_m": (
                        a["estimated_diameter"]["meters"]["estimated_diameter_min"]
                        + a["estimated_diameter"]["meters"]["estimated_diameter_max"]
                    )
                    / 2,
                    "velocidad_kms": ap["relative_velocity"]["kilometers_per_second"],
                    "distancia_km": ap["miss_distance"]["kilometers"],
                    "magnitud": a["absolute_magnitude_h"],
                    "peligroso": a["is_potentially_hazardous_asteroid"],
                    "jpl": a["nasa_jpl_url"],
                }
            )
    df = pd.DataFrame(filas)
    for c in ["diametro_m", "velocidad_kms", "distancia_km", "magnitud"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df = df.dropna().drop_duplicates(subset=["id", "fecha"]).reset_index(drop=True)
    df["distancia_lunar"] = df["distancia_km"] / 384_400
    df["tipo"] = df["peligroso"].map({True: "Potencialmente peligroso", False: "No peligroso"})
    return df


@st.cache_data(show_spinner="Leyendo respuesta.json…")
def cargar_archivo() -> pd.DataFrame:
    with open(ARCHIVO, encoding="utf-8") as f:
        return aplanar(json.load(f))


@st.cache_data(show_spinner="Consultando la API de la NASA…", ttl=3600)
def cargar_api(token: str, inicio: date, semanas: int) -> pd.DataFrame:
    combinado = {"near_earth_objects": {}}
    for i in range(semanas):
        ini = inicio + timedelta(days=7 * i)
        fin = ini + timedelta(days=6)
        r = requests.get(
            URL,
            params={"start_date": ini.isoformat(), "end_date": fin.isoformat(), "api_key": token},
            timeout=30,
        )
        if r.status_code in (401, 403):
            raise ValueError("La NASA rechazó la llave (401/403).")
        if r.status_code == 429:
            raise ValueError("Superaste el límite de la API (2,000 por hora).")
        if r.status_code != 200:
            raise ValueError(f"La API respondió con código {r.status_code}.")
        if "json" not in r.headers.get("Content-Type", "").lower():
            raise ValueError("La respuesta no es JSON.")
        combinado["near_earth_objects"].update(r.json()["near_earth_objects"])
    return aplanar(combinado)


def obtener_token() -> str:
    try:
        t = st.secrets.get("NASA_API_KEY", "")
    except Exception:
        t = ""
    return (t or os.environ.get("NASA_API_KEY", "")).strip()


st.sidebar.title("☄️ Filtros")
fuente = st.sidebar.radio("Fuente de datos", ["Archivo guardado (respuesta.json)", "API de la NASA en vivo"])

if fuente.startswith("Archivo"):
    df = cargar_archivo()
else:
    token = obtener_token() or st.sidebar.text_input("Llave de la NASA", type="password")
    inicio = st.sidebar.date_input("Fecha de inicio", date.today() - timedelta(days=28))
    semanas = st.sidebar.slider("Semanas a consultar", 1, 8, 4)
    if not token:
        st.info("Escribe tu llave en la barra lateral o defínela en `.streamlit/secrets.toml`.")
        st.stop()
    if len(token) != 40 or not token.isalnum():
        st.error("La llave de la NASA debe tener 40 letras y números.")
        st.stop()
    try:
        df = cargar_api(token, inicio, semanas)
    except ValueError as e:
        st.error(str(e))
        st.stop()
    except requests.RequestException as e:
        st.error(f"Error de conexión ({type(e).__name__}).")
        st.stop()

fmin, fmax = df["fecha"].min().date(), df["fecha"].max().date()
rango = st.sidebar.date_input("Rango de fechas", (fmin, fmax), min_value=fmin, max_value=fmax)
if isinstance(rango, tuple) and len(rango) == 2:
    df = df[(df["fecha"].dt.date >= rango[0]) & (df["fecha"].dt.date <= rango[1])]

tipos = st.sidebar.multiselect(
    "Tipo", ["No peligroso", "Potencialmente peligroso"], default=["No peligroso", "Potencialmente peligroso"]
)
df = df[df["tipo"].isin(tipos)]

dmax = float(df["diametro_m"].max()) if len(df) else 1.0
dmin_sel, dmax_sel = st.sidebar.slider("Diámetro (m)", 0.0, dmax, (0.0, dmax))
df = df[(df["diametro_m"] >= dmin_sel) & (df["diametro_m"] <= dmax_sel)]

st.title("Asteroides cercanos a la Tierra")
st.caption("Fuente: NASA NeoWs (api.nasa.gov) · Práctica 12 · Herramientas de Visualización · UPQ")

if df.empty:
    st.warning("Ningún asteroide cumple con los filtros seleccionados.")
    st.stop()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Asteroides", f"{len(df):,}")
k2.metric("Potencialmente peligrosos", f"{int(df['peligroso'].sum()):,}")
k3.metric("Diámetro mediano", f"{df['diametro_m'].median():.0f} m")
k4.metric("Paso más cercano", f"{df['distancia_lunar'].min():.1f} distancias a la Luna")

COLORES = {"No peligroso": GRIS, "Potencialmente peligroso": AZUL}

c1, c2 = st.columns(2)
with c1:
    st.subheader("La mayoría mide menos de 200 m")
    f = px.histogram(df, x="diametro_m", nbins=40, log_y=True, color_discrete_sequence=[AZUL],
                     labels={"diametro_m": "Diámetro estimado (m)", "count": "Asteroides (escala log)"})
    f.add_vline(x=df["diametro_m"].median(), line_dash="dash", line_color="gray",
                annotation_text=f"mediana {df['diametro_m'].median():.0f} m")
    f.update_layout(yaxis_title="Asteroides (escala log)", bargap=0.05)
    st.plotly_chart(f, width="stretch")

with c2:
    st.subheader("Los peligrosos son más grandes")
    f = px.box(df, x="tipo", y="diametro_m", color="tipo", log_y=True, color_discrete_map=COLORES,
               labels={"diametro_m": "Diámetro (m, escala log)", "tipo": ""}, points="outliers")
    f.update_layout(showlegend=False)
    st.plotly_chart(f, width="stretch")

c3, c4 = st.columns(2)
with c3:
    st.subheader("Cercanía y velocidad casi no se relacionan")
    r = df["distancia_lunar"].corr(df["velocidad_kms"])
    f = px.scatter(df, x="distancia_lunar", y="velocidad_kms", color="tipo", color_discrete_map=COLORES,
                   hover_data=["nombre", "fecha"], opacity=0.75,
                   labels={"distancia_lunar": "Distancia (veces la distancia Tierra-Luna)",
                           "velocidad_kms": "Velocidad (km/s)", "tipo": ""})
    f.update_layout(legend=dict(orientation="h", y=-0.25))
    st.plotly_chart(f, width="stretch")
    st.caption(f"Correlación de Pearson: r = {r:.2f}")

with c4:
    st.subheader("Cuántos asteroides pasan por día")
    por_dia = df.groupby("fecha").size().reset_index(name="asteroides")
    f = px.line(por_dia, x="fecha", y="asteroides", markers=True, color_discrete_sequence=[AZUL],
                labels={"fecha": "Fecha", "asteroides": "Asteroides por día"})
    pico = por_dia.loc[por_dia["asteroides"].idxmax()]
    f.add_annotation(x=pico["fecha"], y=pico["asteroides"], text=f"pico: {int(pico['asteroides'])}", showarrow=True)
    st.plotly_chart(f, width="stretch")

st.subheader("Datos")
st.dataframe(
    df[["fecha", "nombre", "tipo", "diametro_m", "velocidad_kms", "distancia_lunar", "jpl"]]
    .sort_values("distancia_lunar").rename(columns={"jpl": "Ficha JPL"}),
    width="stretch", hide_index=True,
    column_config={
        "Ficha JPL": st.column_config.LinkColumn(display_text="ver"),
        "diametro_m": st.column_config.NumberColumn("Diámetro (m)", format="%.0f"),
        "velocidad_kms": st.column_config.NumberColumn("Velocidad (km/s)", format="%.1f"),
        "distancia_lunar": st.column_config.NumberColumn("Distancia (× Luna)", format="%.1f"),
    },
)
st.download_button("Descargar datos filtrados (CSV)", df.to_csv(index=False).encode("utf-8"), "asteroides.csv", "text/csv")
