import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import time

from config import (
    HUMIDITY_LOW_THRESHOLD,
    AIR_QUALITY_BAD_THRESHOLD,
    HISTORY_HOURS,
)
import bigquery_client as bq
import weather_api as weather

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Weather Monitor",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=Space+Mono:wght@400;700&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

.stApp {
    background: linear-gradient(135deg, #0f1117 0%, #1a1f2e 50%, #0f1117 100%);
    color: #e8eaf0;
}

/* Hide default Streamlit elements */
#MainMenu, footer, header { visibility: hidden; }

/* Metric cards */
.metric-card {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px;
    padding: 20px 24px;
    backdrop-filter: blur(10px);
    transition: border-color 0.3s;
}
.metric-card:hover { border-color: rgba(99,179,237,0.4); }

.metric-label {
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: #718096;
    margin-bottom: 8px;
}
.metric-value {
    font-size: 36px;
    font-weight: 600;
    color: #e8eaf0;
    line-height: 1;
}
.metric-unit {
    font-size: 16px;
    color: #a0aec0;
    margin-left: 4px;
}
.metric-sub {
    font-size: 13px;
    color: #718096;
    margin-top: 6px;
}

/* Alert banner */
.alert-danger {
    background: rgba(229,62,62,0.15);
    border: 1px solid rgba(229,62,62,0.4);
    border-radius: 12px;
    padding: 12px 18px;
    color: #fc8181;
    font-size: 14px;
    margin-bottom: 8px;
}
.alert-warning {
    background: rgba(236,153,75,0.15);
    border: 1px solid rgba(236,153,75,0.4);
    border-radius: 12px;
    padding: 12px 18px;
    color: #f6ad55;
    font-size: 14px;
    margin-bottom: 8px;
}

/* Section title */
.section-title {
    font-family: 'Space Mono', monospace;
    font-size: 12px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #4a90d9;
    margin-bottom: 16px;
    margin-top: 32px;
    border-bottom: 1px solid rgba(74,144,217,0.2);
    padding-bottom: 8px;
}

/* Forecast cards */
.forecast-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 16px 12px;
    text-align: center;
}
.forecast-day {
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    color: #718096;
    letter-spacing: 1px;
    text-transform: uppercase;
}
.forecast-temp {
    font-size: 22px;
    font-weight: 600;
    color: #e8eaf0;
    margin: 4px 0;
}
.forecast-desc {
    font-size: 11px;
    color: #a0aec0;
}

/* Dashboard header */
.dash-header {
    padding: 24px 0 16px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    margin-bottom: 28px;
}
.dash-title {
    font-family: 'Space Mono', monospace;
    font-size: 22px;
    font-weight: 700;
    color: #e8eaf0;
    letter-spacing: -0.5px;
}
.dash-subtitle {
    font-size: 14px;
    color: #718096;
    margin-top: 4px;
}
.live-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    background: #48bb78;
    border-radius: 50%;
    margin-right: 8px;
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
}

/* Quality badge */
.badge-good { color: #48bb78; }
.badge-moderate { color: #f6ad55; }
.badge-bad { color: #fc8181; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def air_quality_label(aqi):
    if aqi is None:
        return "—", "badge-good"
    if aqi < 50:
        return "Excellent", "badge-good"
    elif aqi < 100:
        return "Bon", "badge-good"
    elif aqi < 150:
        return "Modéré", "badge-moderate"
    else:
        return "Mauvais", "badge-bad"


def format_date(dt):
    days_fr = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    months_fr = ["jan", "fév", "mar", "avr", "mai", "jun",
                 "jul", "aoû", "sep", "oct", "nov", "déc"]
    if isinstance(dt, str):
        dt = datetime.strptime(dt, "%Y-%m-%d")
    return f"{days_fr[dt.weekday()]} {dt.day} {months_fr[dt.month - 1]}"


def make_line_chart(df, y_col, color, title, unit):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["measurement_time"],
        y=df[y_col],
        mode="lines",
        line=dict(color=color, width=2),
        fill="tozeroy",
        fillcolor=color.replace(")", ", 0.1)").replace("rgb", "rgba"),
        hovertemplate=f"%{{y:.1f}}{unit}<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color="#a0aec0"), x=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#a0aec0", family="DM Sans"),
        margin=dict(l=0, r=0, t=40, b=0),
        height=200,
        xaxis=dict(showgrid=False, color="#4a5568"),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)", color="#4a5568"),
        showlegend=False,
    )
    return fig


# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_latest():
    return bq.get_latest_reading()

@st.cache_data(ttl=60)
def load_history(hours):
    return bq.get_historical_data(hours)

@st.cache_data(ttl=300)
def load_daily_stats():
    return bq.get_daily_stats(days=7)

@st.cache_data(ttl=600)
def load_weather():
    return weather.get_current_weather()

@st.cache_data(ttl=3600)
def load_forecast():
    return weather.get_forecast()


# ── Header ────────────────────────────────────────────────────────────────────
now = datetime.now()
col_title, col_time = st.columns([3, 1])
with col_title:
    st.markdown(f"""
    <div class="dash-header">
        <div class="dash-title">
            <span class="live-dot"></span>Weather Monitor
        </div>
        <div class="dash-subtitle">Lausanne · Tableau de bord en temps réel</div>
    </div>
    """, unsafe_allow_html=True)
with col_time:
    st.markdown(f"""
    <div style="text-align:right; padding-top:28px;">
        <div style="font-family:'Space Mono',monospace; font-size:20px; color:#e8eaf0;">
            {now.strftime('%H:%M')}
        </div>
        <div style="font-size:13px; color:#718096;">{now.strftime('%A %d %B %Y')}</div>
    </div>
    """, unsafe_allow_html=True)

# ── History selector ──────────────────────────────────────────────────────────
hours_options = {"6h": 6, "12h": 12, "24h": 24, "48h": 48, "7 jours": 168}
selected_label = st.radio(
    "Période d'historique",
    list(hours_options.keys()),
    horizontal=True,
    index=2,
    label_visibility="collapsed"
)
selected_hours = hours_options[selected_label]

# ── Load data ─────────────────────────────────────────────────────────────────
latest = load_latest()
history_df = load_history(selected_hours)
daily_df = load_daily_stats()
current_weather = load_weather()
forecast = load_forecast()

# ── Alerts ───────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">⚠️ Alertes</div>', unsafe_allow_html=True)
has_alert = False

if latest is not None:
    if latest.get("indoor_humidity") is not None and latest["indoor_humidity"] < HUMIDITY_LOW_THRESHOLD:
        st.markdown(f'<div class="alert-danger">💧 Humidité intérieure basse : <strong>{latest["indoor_humidity"]:.1f}%</strong> (seuil : {HUMIDITY_LOW_THRESHOLD}%)</div>', unsafe_allow_html=True)
        has_alert = True
    if latest.get("indoor_air_quality") is not None and latest["indoor_air_quality"] > AIR_QUALITY_BAD_THRESHOLD:
        st.markdown(f'<div class="alert-warning">🌫️ Qualité de l\'air dégradée : <strong>{latest["indoor_air_quality"]:.0f} AQI</strong> (seuil : {AIR_QUALITY_BAD_THRESHOLD})</div>', unsafe_allow_html=True)
        has_alert = True

if not has_alert:
    st.markdown('<div style="color:#48bb78; font-size:14px; margin-bottom:16px;">✅ Tout est normal — aucune alerte active</div>', unsafe_allow_html=True)

# ── Current readings ──────────────────────────────────────────────────────────
st.markdown('<div class="section-title">🏠 Intérieur — Lecture actuelle</div>', unsafe_allow_html=True)

if latest is not None:
    aqi_label, aqi_class = air_quality_label(latest.get("indoor_air_quality"))
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Température</div>
            <div class="metric-value">{latest['indoor_temp']:.1f}<span class="metric-unit">°C</span></div>
            <div class="metric-sub">Intérieur</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Humidité</div>
            <div class="metric-value">{latest['indoor_humidity']:.0f}<span class="metric-unit">%</span></div>
            <div class="metric-sub">Intérieur</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Qualité de l'air</div>
            <div class="metric-value {aqi_class}">{aqi_label}</div>
            <div class="metric-sub">{latest['indoor_air_quality']:.0f} AQI</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        ts = pd.to_datetime(latest["measurement_time"]).strftime("%H:%M")
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Dernière mise à jour</div>
            <div class="metric-value" style="font-size:28px;">{ts}</div>
            <div class="metric-sub">Capteur M5Stack</div>
        </div>""", unsafe_allow_html=True)
else:
    st.warning("Aucune donnée disponible dans BigQuery pour l'instant.")

# ── Outdoor current ───────────────────────────────────────────────────────────
st.markdown('<div class="section-title">🌤️ Extérieur — Météo actuelle</div>', unsafe_allow_html=True)

if "error" not in current_weather:
    cw = current_weather
    ow1, ow2, ow3, ow4 = st.columns(4)
    with ow1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Température</div>
            <div class="metric-value">{cw['temp']:.1f}<span class="metric-unit">°C</span></div>
            <div class="metric-sub">Ressenti {cw['feels_like']:.1f}°C</div>
        </div>""", unsafe_allow_html=True)
    with ow2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Humidité</div>
            <div class="metric-value">{cw['humidity']}<span class="metric-unit">%</span></div>
            <div class="metric-sub">Extérieur</div>
        </div>""", unsafe_allow_html=True)
    with ow3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Vent</div>
            <div class="metric-value">{cw['wind_speed']:.1f}<span class="metric-unit">m/s</span></div>
            <div class="metric-sub">{cw['description']}</div>
        </div>""", unsafe_allow_html=True)
    with ow4:
        img_url = weather.icon_url(cw['icon'])
        st.markdown(f"""
        <div class="metric-card" style="text-align:center;">
            <div class="metric-label">Conditions</div>
            <img src="{img_url}" width="60" style="margin:-8px 0">
            <div class="metric-sub">{cw['description']}</div>
        </div>""", unsafe_allow_html=True)
else:
    st.error(f"Erreur météo : {current_weather['error']}")

# ── Forecast ──────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">📅 Prévisions 5 jours</div>', unsafe_allow_html=True)

if isinstance(forecast, list) and forecast:
    cols = st.columns(len(forecast))
    for i, day in enumerate(forecast):
        with cols[i]:
            img_url = weather.icon_url(day["icon"])
            st.markdown(f"""
            <div class="forecast-card">
                <div class="forecast-day">{format_date(day['date'])}</div>
                <img src="{img_url}" width="48" style="margin:4px 0">
                <div class="forecast-temp">{day['temp_max']:.0f}° <span style="color:#718096;font-size:16px">{day['temp_min']:.0f}°</span></div>
                <div class="forecast-desc">{day['description']}</div>
                <div style="font-size:11px;color:#718096;margin-top:4px;">💧 {day['humidity']}%</div>
            </div>""", unsafe_allow_html=True)

# ── Historical charts ─────────────────────────────────────────────────────────
st.markdown(f'<div class="section-title">📈 Historique — {selected_label}</div>', unsafe_allow_html=True)

if not history_df.empty:
    ch1, ch2 = st.columns(2)
    with ch1:
        fig_temp = make_line_chart(history_df, "indoor_temp", "rgb(99,179,237)", "Température intérieure", "°C")
        st.plotly_chart(fig_temp, use_container_width=True)
    with ch2:
        fig_hum = make_line_chart(history_df, "indoor_humidity", "rgb(72,187,120)", "Humidité intérieure", "%")
        st.plotly_chart(fig_hum, use_container_width=True)

    ch3, ch4 = st.columns(2)
    with ch3:
        fig_aqi = make_line_chart(history_df, "indoor_air_quality", "rgb(236,153,75)", "Qualité de l'air (AQI)", "")
        st.plotly_chart(fig_aqi, use_container_width=True)
    with ch4:
        fig_out = make_line_chart(history_df, "outdoor_temp", "rgb(159,122,234)", "Température extérieure", "°C")
        st.plotly_chart(fig_out, use_container_width=True)
else:
    st.info("Pas encore de données historiques pour cette période.")

# ── Weekly stats table ────────────────────────────────────────────────────────
if not daily_df.empty:
    st.markdown('<div class="section-title">📊 Statistiques — 7 derniers jours</div>', unsafe_allow_html=True)
    daily_df["day"] = daily_df["day"].apply(lambda d: format_date(str(d)))
    daily_df.columns = ["Jour", "Moy. temp int (°C)", "Min (°C)", "Max (°C)",
                         "Moy. humidité (%)", "Moy. AQI", "Moy. temp ext (°C)"]
    st.dataframe(daily_df, use_container_width=True, hide_index=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center; margin-top:48px; padding-top:24px;
            border-top:1px solid rgba(255,255,255,0.06);
            font-family:'Space Mono',monospace; font-size:11px; color:#4a5568;">
    Weather Monitor · Cloud & Advanced Analytics · UNIL 2026
</div>
""", unsafe_allow_html=True)

# Auto-refresh toutes les 60s
time.sleep(1)
st.rerun()
