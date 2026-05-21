import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import pytz
import time

from config import (
    HUMIDITY_LOW_THRESHOLD,
    AIR_QUALITY_BAD_THRESHOLD,
    HISTORY_HOURS,
)
import bigquery_client as bq
import weather_api as weather

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Weather Monitor",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@300;400;600;700;800&family=Figtree:wght@400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Figtree', sans-serif;
    color: #1a2b4a;
}

.stApp {
    background: linear-gradient(180deg, #e8f4fd 0%, #f0f8ff 40%, #ffffff 100%);
}

#MainMenu, footer, header { visibility: hidden; }

/* Remove default streamlit padding */
.block-container { padding-top: 2rem !important; }

/* ── Metric cards ── */
.metric-card {
    background: white;
    border-radius: 20px;
    padding: 22px 24px;
    box-shadow: 0 2px 16px rgba(30,100,180,0.08), 0 1px 4px rgba(30,100,180,0.05);
    border: 1px solid rgba(180,215,255,0.6);
    transition: transform 0.2s, box-shadow 0.2s;
    position: relative;
    overflow: hidden;
}
.metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, #4a9eff, #74c0fc);
    border-radius: 20px 20px 0 0;
}
.metric-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 28px rgba(30,100,180,0.13);
}

.metric-label {
    font-family: 'Figtree', sans-serif;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    color: #7aa8d4;
    margin-bottom: 10px;
}
.metric-value {
    font-family: 'Nunito', sans-serif;
    font-size: 38px;
    font-weight: 800;
    color: #1a2b4a;
    line-height: 1;
}
.metric-unit {
    font-size: 18px;
    font-weight: 600;
    color: #7aa8d4;
    margin-left: 2px;
}
.metric-sub {
    font-size: 13px;
    color: #94b8d6;
    margin-top: 6px;
    font-weight: 500;
}

/* ── Sun card (outdoor temp) ── */
.metric-card.sun::before {
    background: linear-gradient(90deg, #ffd43b, #ff9f43);
}

/* ── Humidity card ── */
.metric-card.humid::before {
    background: linear-gradient(90deg, #74c0fc, #4dabf7);
}

/* ── Air quality card ── */
.metric-card.air::before {
    background: linear-gradient(90deg, #69db7c, #40c057);
}

/* ── Alert banners ── */
.alert-danger {
    background: linear-gradient(135deg, #fff5f5, #ffe3e3);
    border: 1px solid #ffc9c9;
    border-left: 4px solid #ff6b6b;
    border-radius: 12px;
    padding: 14px 18px;
    color: #c92a2a;
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 10px;
}
.alert-warning {
    background: linear-gradient(135deg, #fff9db, #ffec99);
    border: 1px solid #ffe066;
    border-left: 4px solid #fcc419;
    border-radius: 12px;
    padding: 14px 18px;
    color: #e67700;
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 10px;
}
.alert-ok {
    background: linear-gradient(135deg, #ebfbee, #d3f9d8);
    border: 1px solid #b2f2bb;
    border-left: 4px solid #40c057;
    border-radius: 12px;
    padding: 14px 18px;
    color: #2f9e44;
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 10px;
}

/* ── Section titles ── */
.section-title {
    font-family: 'Nunito', sans-serif;
    font-size: 18px;
    font-weight: 800;
    color: #1a2b4a;
    margin-bottom: 16px;
    margin-top: 36px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.section-title::after {
    content: '';
    flex: 1;
    height: 2px;
    background: linear-gradient(90deg, #bee3f8, transparent);
    border-radius: 2px;
    margin-left: 12px;
}

/* ── Forecast cards ── */
.forecast-card {
    background: white;
    border-radius: 18px;
    padding: 18px 12px;
    text-align: center;
    box-shadow: 0 2px 12px rgba(30,100,180,0.07);
    border: 1px solid rgba(180,215,255,0.5);
    transition: transform 0.2s;
}
.forecast-card:hover { transform: translateY(-3px); }
.forecast-day {
    font-family: 'Figtree', sans-serif;
    font-size: 11px;
    font-weight: 600;
    color: #7aa8d4;
    letter-spacing: 1px;
    text-transform: uppercase;
}
.forecast-temp-max {
    font-family: 'Nunito', sans-serif;
    font-size: 24px;
    font-weight: 800;
    color: #1a2b4a;
    margin: 4px 0 0;
}
.forecast-temp-min {
    font-size: 15px;
    font-weight: 600;
    color: #94b8d6;
}
.forecast-desc {
    font-size: 11px;
    color: #7aa8d4;
    margin-top: 4px;
    font-weight: 500;
}

/* ── Header ── */
.dash-header {
    background: linear-gradient(135deg, #1971c2 0%, #1c7ed6 50%, #339af0 100%);
    border-radius: 24px;
    padding: 28px 36px;
    margin-bottom: 28px;
    color: white;
    box-shadow: 0 8px 32px rgba(25,113,194,0.25);
    position: relative;
    overflow: hidden;
}
.dash-header::before {
    content: '☁️';
    position: absolute;
    font-size: 120px;
    right: 40px;
    top: -20px;
    opacity: 0.15;
}
.dash-header::after {
    content: '🌤️';
    position: absolute;
    font-size: 80px;
    right: 180px;
    top: 10px;
    opacity: 0.2;
}
.dash-title {
    font-family: 'Nunito', sans-serif;
    font-size: 28px;
    font-weight: 800;
    color: white;
    letter-spacing: -0.5px;
}
.dash-subtitle {
    font-size: 14px;
    color: rgba(255,255,255,0.75);
    margin-top: 4px;
    font-weight: 500;
}
.dash-time {
    font-family: 'Nunito', sans-serif;
    font-size: 48px;
    font-weight: 800;
    color: white;
    line-height: 1;
    text-align: right;
}
.dash-date {
    font-size: 13px;
    color: rgba(255,255,255,0.7);
    text-align: right;
    margin-top: 4px;
    font-weight: 500;
}

/* ── Live dot ── */
.live-dot {
    display: inline-block;
    width: 9px; height: 9px;
    background: #74fb8a;
    border-radius: 50%;
    margin-right: 8px;
    box-shadow: 0 0 0 3px rgba(116,251,138,0.3);
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0%, 100% { box-shadow: 0 0 0 3px rgba(116,251,138,0.3); }
    50% { box-shadow: 0 0 0 6px rgba(116,251,138,0.1); }
}

/* ── Badge colors ── */
.badge-good     { color: #2f9e44; font-weight: 700; }
.badge-moderate { color: #e67700; font-weight: 700; }
.badge-bad      { color: #c92a2a; font-weight: 700; }

/* ── Radio buttons ── */
div[data-testid="stRadio"] > div {
    color: #1a2b4a !important;
    background: white;
    border-radius: 50px;
    padding: 4px;
    display: inline-flex;
    box-shadow: 0 2px 8px rgba(30,100,180,0.08);
    border: 1px solid rgba(180,215,255,0.6);
}

/* ── Dataframe ── */
.stDataFrame { border-radius: 16px; overflow: hidden; }

/* ── Weather icon card ── */
.weather-condition-card {
    background: linear-gradient(135deg, #e7f5ff, #dbe4ff);
    border-radius: 20px;
    padding: 22px 24px;
    text-align: center;
    border: 1px solid rgba(180,215,255,0.6);
    box-shadow: 0 2px 16px rgba(30,100,180,0.08);
}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def air_quality_label(aqi):
    if aqi is None: return "—", "badge-good"
    if aqi < 50:    return "Excellent", "badge-good"
    elif aqi < 100: return "Good", "badge-good"
    elif aqi < 150: return "Moderate", "badge-moderate"
    else:           return "Poor", "badge-bad"


def format_date(dt):
    days   = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    if isinstance(dt, str): dt = datetime.strptime(dt, "%Y-%m-%d")
    return f"{days[dt.weekday()]} {dt.day} {months[dt.month-1]}"


def make_line_chart(df, y_col, color, title, unit):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["measurement_time"], y=df[y_col], mode="lines",
        line=dict(color=color, width=2.5),
        fill="tozeroy",
        fillcolor=color.replace("rgb", "rgba").replace(")", ", 0.08)"),
        hovertemplate=f"<b>%{{y:.1f}}{unit}</b><br>%{{x|%H:%M}}<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color="#7aa8d4", family="Figtree"), x=0),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color="#94b8d6", family="Figtree"),
        margin=dict(l=0, r=0, t=40, b=0),
        height=200,
        xaxis=dict(showgrid=False, color="#b8d4e8", linecolor="#e8f4fd"),
        yaxis=dict(showgrid=True, gridcolor="#f0f8ff", color="#b8d4e8", linecolor="#e8f4fd"),
        showlegend=False,
    )
    return fig


# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_latest(): return bq.get_latest_reading()

@st.cache_data(ttl=60)
def load_history(hours): return bq.get_historical_data(hours)

@st.cache_data(ttl=300)
def load_daily_stats(): return bq.get_daily_stats(days=7)

@st.cache_data(ttl=600)
def load_weather(): return weather.get_current_weather()

@st.cache_data(ttl=3600)
def load_forecast(): return weather.get_forecast()


# ── Header ────────────────────────────────────────────────────────────────────
tz = pytz.timezone('Europe/Zurich')
now = datetime.now(tz)
col_title, col_time = st.columns([3, 1])
with col_title:
    st.markdown(f"""
    <div class="dash-header">
        <div class="dash-title"><span class="live-dot"></span>Weather Monitor</div>
        <div class="dash-subtitle">Lausanne, Switzerland &nbsp;·&nbsp; Real-time indoor & outdoor monitoring</div>
    </div>
    """, unsafe_allow_html=True)
with col_time:
    st.markdown(f"""
    <div style="padding-top:8px;">
        <div class="dash-time">{now.strftime('%H:%M')}</div>
        <div class="dash-date">{now.strftime('%A, %d %B %Y')}</div>
    </div>
    """, unsafe_allow_html=True)

# ── History selector ──────────────────────────────────────────────────────────
hours_options = {"6h": 6, "12h": 12, "24h": 24, "48h": 48, "7 days": 168}

if "selected_hours_label" not in st.session_state:
    st.session_state.selected_hours_label = "24h"

cols_btn = st.columns(len(hours_options))
for i, (label, val) in enumerate(hours_options.items()):
    with cols_btn[i]:
        is_active = st.session_state.selected_hours_label == label
        btn_style = "background:#1971c2;color:white;border:none;" if is_active else "background:white;color:#1a2b4a;border:1px solid #bee3f8;"
        if st.button(label, key=f"btn_{label}", use_container_width=False):
            st.session_state.selected_hours_label = label
            st.rerun()

selected_label = st.session_state.selected_hours_label
selected_hours = hours_options[selected_label]

# ── Load data ─────────────────────────────────────────────────────────────────
latest          = load_latest()
history_df      = load_history(selected_hours)
daily_df        = load_daily_stats()
current_weather = load_weather()
forecast        = load_forecast()

# ── Alerts ────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">⚠️ Alerts</div>', unsafe_allow_html=True)
has_alert = False
if latest is not None:
    if latest.get("indoor_humidity") is not None and latest["indoor_humidity"] < HUMIDITY_LOW_THRESHOLD:
        st.markdown(f'<div class="alert-danger">💧 Low indoor humidity: <strong>{latest["indoor_humidity"]:.1f}%</strong> — below threshold of {HUMIDITY_LOW_THRESHOLD}%</div>', unsafe_allow_html=True)
        has_alert = True
    if latest.get("indoor_air_quality") is not None and latest["indoor_air_quality"] > AIR_QUALITY_BAD_THRESHOLD:
        st.markdown(f'<div class="alert-warning">🌫️ Poor air quality: <strong>{latest["indoor_air_quality"]:.0f} AQI</strong> — above threshold of {AIR_QUALITY_BAD_THRESHOLD}</div>', unsafe_allow_html=True)
        has_alert = True
if not has_alert:
    st.markdown('<div class="alert-ok">✅ All systems normal — no active alerts</div>', unsafe_allow_html=True)

# ── Indoor readings ───────────────────────────────────────────────────────────
st.markdown('<div class="section-title">🏠 Indoor — Current Reading</div>', unsafe_allow_html=True)
if latest is not None:
    aqi_label, aqi_class = air_quality_label(latest.get("indoor_air_quality"))
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">🌡️ Temperature</div>
            <div class="metric-value">{latest['indoor_temp']:.1f}<span class="metric-unit">°C</span></div>
            <div class="metric-sub">Indoor sensor</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card humid">
            <div class="metric-label">💧 Humidity</div>
            <div class="metric-value">{latest['indoor_humidity']:.0f}<span class="metric-unit">%</span></div>
            <div class="metric-sub">Indoor sensor</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card air">
            <div class="metric-label">🌿 Air Quality</div>
            <div class="metric-value {aqi_class}" style="font-size:28px;padding-top:4px;">{aqi_label}</div>
            <div class="metric-sub">{latest['indoor_air_quality']:.0f} AQI</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        ts = pd.to_datetime(latest["measurement_time"]).strftime("%H:%M")
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">🕐 Last Updated</div>
            <div class="metric-value" style="font-size:30px;">{ts}</div>
            <div class="metric-sub">M5Stack sensor</div>
        </div>""", unsafe_allow_html=True)
else:
    st.info("No sensor data available in BigQuery yet.")

# ── Outdoor weather ───────────────────────────────────────────────────────────
st.markdown('<div class="section-title">🌤️ Outdoor — Current Weather</div>', unsafe_allow_html=True)
if "error" not in current_weather:
    cw = current_weather
    ow1, ow2, ow3, ow4 = st.columns(4)
    with ow1:
        st.markdown(f"""
        <div class="metric-card sun">
            <div class="metric-label">🌡️ Temperature</div>
            <div class="metric-value">{cw['temp']:.1f}<span class="metric-unit">°C</span></div>
            <div class="metric-sub">Feels like {cw['feels_like']:.1f}°C</div>
        </div>""", unsafe_allow_html=True)
    with ow2:
        st.markdown(f"""
        <div class="metric-card humid">
            <div class="metric-label">💧 Humidity</div>
            <div class="metric-value">{cw['humidity']}<span class="metric-unit">%</span></div>
            <div class="metric-sub">Outdoor</div>
        </div>""", unsafe_allow_html=True)
    with ow3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">💨 Wind Speed</div>
            <div class="metric-value">{cw['wind_speed']:.1f}<span class="metric-unit">m/s</span></div>
            <div class="metric-sub">{cw['description']}</div>
        </div>""", unsafe_allow_html=True)
    with ow4:
        st.markdown(f"""
        <div class="weather-condition-card">
            <div class="metric-label">☁️ Conditions</div>
            <img src="https://openweathermap.org/img/wn/{cw['icon']}@2x.png" width="64" style="margin:-4px 0">
            <div style="font-size:13px;color:#1971c2;font-weight:600;">{cw['description']}</div>
            <div style="font-size:11px;color:#94b8d6;margin-top:2px;">{cw['pressure']} hPa</div>
        </div>""", unsafe_allow_html=True)
else:
    st.error(f"Weather API error: {current_weather['error']}")

# ── Forecast ──────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">📅 5-Day Forecast</div>', unsafe_allow_html=True)
if isinstance(forecast, list) and forecast:
    cols = st.columns(len(forecast))
    for i, day in enumerate(forecast):
        with cols[i]:
            st.markdown(f"""
            <div class="forecast-card">
                <div class="forecast-day">{format_date(day['date'])}</div>
                <img src="https://openweathermap.org/img/wn/{day['icon']}@2x.png" width="52" style="margin:2px 0">
                <div class="forecast-temp-max">{day['temp_max']:.0f}°<span class="forecast-temp-min"> {day['temp_min']:.0f}°</span></div>
                <div class="forecast-desc">{day['description']}</div>
                <div style="font-size:11px;color:#74c0fc;margin-top:6px;font-weight:600;">💧 {day['humidity']}%</div>
            </div>""", unsafe_allow_html=True)

# ── Historical charts ─────────────────────────────────────────────────────────
st.markdown(f'<div class="section-title">📈 Historical Data — {selected_label}</div>', unsafe_allow_html=True)
if not history_df.empty:
    ch1, ch2 = st.columns(2)
    with ch1: st.plotly_chart(make_line_chart(history_df, "indoor_temp",        "rgb(25,113,194)",  "Indoor Temperature",  "°C"), use_container_width=True)
    with ch2: st.plotly_chart(make_line_chart(history_df, "indoor_humidity",    "rgb(51,154,240)",  "Indoor Humidity",     "%"),  use_container_width=True)
    ch3, ch4 = st.columns(2)
    with ch3: st.plotly_chart(make_line_chart(history_df, "indoor_air_quality", "rgb(64,192,87)",   "Air Quality (AQI)",   ""),   use_container_width=True)
    with ch4: st.plotly_chart(make_line_chart(history_df, "outdoor_temp",       "rgb(255,159,67)",  "Outdoor Temperature", "°C"), use_container_width=True)
else:
    st.info("No historical data available for this period.")

# ── Weekly stats ──────────────────────────────────────────────────────────────
if not daily_df.empty:
    st.markdown('<div class="section-title">📊 Statistics — Last 7 Days</div>', unsafe_allow_html=True)
    daily_df["day"] = daily_df["day"].apply(lambda d: format_date(str(d)))
    daily_df.columns = ["Day", "Avg Indoor Temp (°C)", "Min (°C)", "Max (°C)",
                        "Avg Humidity (%)", "Avg AQI", "Avg Outdoor Temp (°C)"]
    st.dataframe(daily_df, use_container_width=True, hide_index=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center;margin-top:56px;padding-top:24px;
            border-top:2px solid #e8f4fd;
            font-family:'Figtree',sans-serif;font-size:12px;color:#94b8d6;font-weight:500;">
    Weather Monitor &nbsp;·&nbsp; Cloud & Advanced Analytics &nbsp;·&nbsp; UNIL 2026
</div>""", unsafe_allow_html=True)

time.sleep(1)
st.rerun()
