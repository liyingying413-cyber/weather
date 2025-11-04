# Weather on Map — Open-Meteo (no background image)
import requests
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
import folium

st.set_page_config(page_title="Weather — Map Picker", page_icon="⛅", layout="wide")

# ---------- API endpoints ----------
GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
REVERSE = "https://geocoding-api.open-meteo.com/v1/reverse"
FORECAST = "https://api.open-meteo.com/v1/forecast"

@st.cache_data(ttl=3600, show_spinner=False)
def geocode(name: str, count: int = 8, language: str = "en"):
    if not name:
        return []
    r = requests.get(GEOCODE, params={"name": name, "count": count, "language": language}, timeout=20)
    r.raise_for_status()
    return r.json().get("results", []) or []

@st.cache_data(ttl=3600, show_spinner=False)
def reverse_geocode(lat: float, lon: float, language: str = "en"):
    r = requests.get(REVERSE, params={"latitude": lat, "longitude": lon, "language": language}, timeout=20)
    r.raise_for_status()
    return (r.json().get("results") or [None])[0]

@st.cache_data(ttl=900, show_spinner=False)
def fetch_forecast(lat: float, lon: float, tz: str, metric: bool):
    params = {
        "latitude": lat, "longitude": lon, "timezone": tz or "auto",
        "current": ["temperature_2m","apparent_temperature","relative_humidity_2m","wind_speed_10m"],
        "hourly": ["temperature_2m","precipitation","wind_speed_10m"],
        "daily": ["temperature_2m_max","temperature_2m_min","precipitation_sum","wind_speed_10m_max"],
        "forecast_days": 7,
        "temperature_unit": "celsius" if metric else "fahrenheit",
        "wind_speed_unit": "kmh" if metric else "mph",
        "precipitation_unit": "mm",
    }
    r = requests.get(FORECAST, params=params, timeout=20)
    r.raise_for_status()
    return r.json()

# ---------- Sidebar ----------
st.sidebar.header("🔎 Search or Pick a City")
units = st.sidebar.radio("Units", ["metric (°C, km/h)", "imperial (°F, mph)"], index=0)
metric = units.startswith("metric")
q = st.sidebar.text_input("City name", value="Seoul")
count = st.sidebar.slider("Candidates", 1, 10, 5)

# initialize default location
if "loc" not in st.session_state:
    res = geocode("Seoul", count=1)
    if res:
        st.session_state["loc"] = res[0]
    else:
        st.session_state["loc"] = {
            "name":"Seoul","latitude":37.57,"longitude":126.98,
            "country":"South Korea","timezone":"Asia/Seoul"
        }

if st.sidebar.button("Search", use_container_width=True):
    found = geocode(q, count=count)
    if found:
        st.session_state["loc"] = found[0]

# ---------- Map ----------
st.title("⛅ Weather — Open API (Map Picker)")
st.markdown("Click on any location on the map to see its weather information.")
loc = st.session_state["loc"]
lat, lon = loc["latitude"], loc["longitude"]

m = folium.Map(location=[lat, lon], zoom_start=4, tiles="cartodbpositron")
folium.Marker([lat, lon],
              tooltip=f"{loc.get('name')}, {loc.get('country','')}",
              icon=folium.Icon(color="blue")).add_to(m)
out = st_folium(m, height=420, width=None, returned_objects=[])

if out and out.get("last_clicked"):
    clicked = out["last_clicked"]
    lat, lon = clicked["lat"], clicked["lng"]
    rev = reverse_geocode(lat, lon) or {}
    if rev:
        st.session_state["loc"] = {
            "name": rev.get("name") or rev.get("admin1") or "Selected point",
            "admin1": rev.get("admin1"),
            "country": rev.get("country"),
            "latitude": lat, "longitude": lon,
            "timezone": rev.get("timezone") or "auto"
        }

# ---------- Weather display ----------
loc = st.session_state["loc"]
place = f"**{loc.get('name','')}**, {loc.get('admin1','')}, {loc.get('country','')}".replace(' ,','')
st.markdown(f"### {place}")

data = fetch_forecast(loc["latitude"], loc["longitude"], loc.get("timezone","auto"), metric)

cur = data.get("current", {})
daily = data.get("daily", {})
hourly = data.get("hourly", {})

c1, c2, c3, c4 = st.columns(4)
c1.metric("Temperature", f"{cur.get('temperature_2m','–')}°")
c2.metric("Feels like", f"{cur.get('apparent_temperature','–')}°")
c3.metric("Wind", f"{cur.get('wind_speed_10m','–')} {'km/h' if metric else 'mph'}")
c4.metric("Humidity", f"{cur.get('relative_humidity_2m','–')}%")

st.markdown("#### Next 24 hours")
h_temp = (hourly.get("temperature_2m") or [])[:24]
h_prec = (hourly.get("precipitation") or [])[:24]
h_wind = (hourly.get("wind_speed_10m") or [])[:24]

if h_temp:
    st.line_chart({"temperature": h_temp}, height=180)
if h_prec:
    st.bar_chart({"precipitation": h_prec}, height=120)
if h_wind:
    st.line_chart({"wind": h_wind}, height=120)

st.markdown("#### 7-day forecast")
df = pd.DataFrame({
    "date": daily.get("time", []),
    "max °": daily.get("temperature_2m_max", []),
    "min °": daily.get("temperature_2m_min", []),
    "precip mm": daily.get("precipitation_sum", []),
    "wind max": daily.get("wind_speed_10m_max", []),
})
if not df.empty:
    st.dataframe(df, use_container_width=True, hide_index=True)

st.caption("Data: © Open-Meteo.com • No API key required.")
