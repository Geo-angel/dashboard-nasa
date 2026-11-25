# Dashboard · Asteroides cercanos a la Tierra (NASA NeoWs)

Evidencia EP.03.01 · Herramientas de Visualización · UPQ  
Transformación de la API de la práctica 12 (NASA NeoWs) a un dashboard con Streamlit.

## Ejecutar

```bash
pip install -r requirements.txt
streamlit run app.py
```

Por defecto lee `respuesta.json` (datos del 1 sep al 26 oct 2026), así que **no necesita llave**.
Para consultar la API en vivo: consigue una llave gratis en https://api.nasa.gov y ponla en
`.streamlit/secrets.toml` (ver `.streamlit/secrets.toml.example`) o escríbela en la barra lateral.
La llave nunca se guarda en el repositorio.
