# Weather — Click on Map only (robust reverse geocode + timezone fallback)
import requests
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
import folium

st.set_page_config(page_title="Weather — Click on Map", page_icon="⛅", layout="wide")

# ---------------- Open-Meteo endpoints ----------------
REVERSE = "https://geocoding-api.open-meteo.com/v1/reverse"
FORECAST = "https://api.open-meteo.com/v1/forecast"
TIMEZONE_API = "https://timezone.open-meteo.com/v1/timezone"

# ---------- helpers ----------
@st.cache_data(ttl=3600, show_spinner=False)
def reverse_geocode(lat: float, lon: float, language: str = "en"):
    """Return nearest place info for a lat/lon. None on HTTP error."""
    try:
        r = requests.get(REVERSE, params={"latitude": lat, "longitude": lon, "language": language}, timeout=15)
        r.raise_for_status()
        results = r.json().get("results") or []
        return results[0] if results else None
    except Exception:
        return None

@st.cache_data(ttl=86400, show_spinner=False)
def get_timezone(lat: float, lon: float):
    """Fetch IANA timezone for a coordinate. Returns 'auto' on failure."""
    try:
        r = requests.get(TIMEZONE_API, params={"latitude": lat, "longitude": lon}, timeout=10)
        r.raise_for_status()
        return (r.json() or {}).get("timezone", "auto")
    except Exception:
        return "auto"

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

# ---------------- Sidebar (units only) ----------------
st.sidebar.header("Options")
units = st.sidebar.radio("Units", ["metric (°C, km/h)", "imperial (°F, mph)"], index=0)
metric = units.startswith("metric")
if st.sidebar.button("Clear cache"):
    st.cache_data.clear()
    st.experimental_rerun()

# ---------------- Map ----------------
st.title("⛅ Weather — Click any place on the map")
st.caption("Zoom到城市后点击地图即可。若点击海面或无人区，会自动回退为坐标点的天气。")

# 首次默认到首尔；之后都以用户点击为准
if "loc" not in st.session_state:
    st.session_state["loc"] = {
        "name": "Seoul", "admin1": "Seoul", "country": "South Korea",
        "latitude": 37.57, "longitude": 126.98, "timezone": "Asia/Seoul"
    }

loc = st.session_state["loc"]
m = folium.Map(location=[loc["latitude"], loc["longitude"]], zoom_start=5, tiles="cartodbpositron")
folium.Marker([loc["latitude"], loc["longitude"]],
              tooltip=f"{loc.get('name')}, {loc.get('country','')}",
              icon=folium.Icon(color="blue")).add_to(m)

out = st_folium(m, height=480, use_container_width=True)

# 处理点击：逆地理编码失败则使用时区兜底
if out and out.get("last_clicked"):
    lat = float(out["last_clicked"]["lat"])
    lon = float(out["last_clicked"]["lng"])

    rev = reverse_geocode(lat, lon)  # None if HTTP error / no result
    if rev:
        tz = rev.get("timezone") or get_timezone(lat, lon)
        name = rev.get("name") or rev.get("admin1") or "Selected point"
        admin1 = rev.get("admin1")
        country = rev.get("country")
    else:
        tz = get_timezone(lat, lon)
        name = f"Selected point ({lat:.2f}, {lon:.2f})"
        admin1, country = None, None

    st.session_state["loc"] = {
        "name": name, "admin1": admin1, "country": country,
        "latitude": lat, "longitude": lon, "timezone": tz
    }
    loc = st.session_state["loc"]

# ---------------- Weather display ----------------
place = " · ".join([x for x in [loc.get("name"), loc.get("admin1"), loc.get("country")] if x])
st.markdown(f"### {place}")

try:
    data = fetch_forecast(loc["latitude"], loc["longitude"], loc.get("timezone","auto"), metric)
except Exception as e:
    st.error("Fetching forecast failed. Please click another point or try again.")
    st.stop()

cur, hourly, daily = data.get("current", {}), data.get("hourly", {}), data.get("daily", {})

c1, c2, c3, c4 = st.columns(4)
c1.metric("Temperature", f"{cur.get('temperature_2m','–')}°")
c2.metric("Feels like", f"{cur.get('apparent_temperature','–')}°")
c3.metric("Wind", f"{cur.get('wind_speed_10m','–')} {'km/h' if metric else 'mph'}")
c4.metric("Humidity", f"{cur.get('relative_humidity_2m','–')}%")

st.markdown("#### Next 24 hours")
h_temp = (hourly.get("temperature_2m") or [])[:24]
h_prec = (hourly.get("precipitation") or [])[:24]
h_wind = (hourly.get("wind_speed_10m") or [])[:24]
if h_temp: st.line_chart({"temperature": h_temp}, height=180)
if h_prec: st.bar_chart({"precipitation": h_prec}, height=120)
if h_wind: st.line_chart({"wind": h_wind}, height=120)

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
