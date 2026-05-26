# 🌤️ Project Weather

> Indoor & Outdoor Weather Monitoring System  
> Cloud and Advanced Analytics — Spring 2026

## 🎬 Demo Video

▶️ [Watch on YouTube](https://youtu.be/_qHEpmxgNes)

---

## 👥 Team

| Name | GitHub | Role |
|------|--------|------|
| **Raffaele-Alban Bakija** | [@Rafban13](https://github.com/Rafban13) | M5Stack device interface (Python/UIFlow), Streamlit cloud dashboard |
| **Arlind Kadriu** | [@63didi](https://github.com/63didi) | Flask backend service, BigQuery integration, AI/ML APIs (STT, TTS, Gemini) |

---

## 📋 Project Overview

This project implements an indoor/outdoor weather monitoring system using an M5Stack Core2 IoT device equipped with three sensors (temperature/humidity, air quality, motion). The system:

- Collects **indoor measurements** (temperature, humidity, CO₂/air quality) in real time
- Fetches **outdoor weather** from OpenWeatherMap via IP geolocation
- Stores all data in **Google BigQuery**
- Displays everything on a **Streamlit cloud dashboard** with historical charts
- Features **voice Q&A** — ask the device a question and get an AI-generated spoken answer (Google Speech-to-Text + Gemini + Text-to-Speech)
- Announces weather aloud when **motion is detected** (PIR sensor), at most once per hour

---

## 🏗️ Architecture

3-tier architecture:

```
┌─────────────────────────────────────────────────────┐
│  DATA LAYER       Google BigQuery                   │
│                   weather_data.sensor_data          │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│  MIDDLEWARE       Flask (Cloud Run, europe-west6)   │
│  service/app.py   BigQuery · OpenWeatherMap         │
│                   Gemini · STT · TTS · Pillow       │
└──────┬────────────────────────────┬─────────────────┘
       │                            │
┌──────▼──────────┐      ┌──────────▼──────────────────┐
│  ON-DEVICE UI   │      │  CLOUD UI                   │
│  M5Stack Core2  │      │  Streamlit (Cloud Run)      │
│  m5stack/       │      │  dashboard/                 │
└─────────────────┘      └─────────────────────────────┘
```

---

## 📁 Repository Structure

```
project-weather/
├── m5stack/                  # M5Stack device code
│   ├── main.py               # Main UIFlow application
│   ├── wifi_config.py        # WiFi credentials (gitignored)
│   └── wifi_config.example.py
├── service/                  # Flask backend (Cloud Run)
│   ├── app.py                # API routes
│   ├── bigquery_client.py
│   ├── weather_client.py
│   ├── vertexai_client.py
│   ├── speechtotext_client.py
│   ├── texttospeech_client.py
│   ├── requirements.txt
│   └── Dockerfile
├── dashboard/                # Streamlit dashboard (Cloud Run)
│   ├── app.py
│   ├── bigquery_client.py
│   ├── weather_api.py
│   ├── config.py
│   ├── requirements.txt
│   └── Dockerfile
├── credentials/              # GCP service account key (gitignored)
├── config.py                 # Local secrets (gitignored)
├── config.example.py         # Config template
└── res/                      # Static assets (default images)
```

---

## 🚀 Deployment

### Prerequisites

- Google Cloud project with billing enabled
- APIs enabled: BigQuery, Cloud Run, Cloud Build, Artifact Registry, Vertex AI, Text-to-Speech, Speech-to-Text
- OpenWeatherMap API key (free tier)
- M5Stack Core2 with UIFlow 1.15.0

### 1. Clone and configure

```bash
git clone https://github.com/Rafban13/project-weather.git
cd project-weather

# Copy the config template and fill in your values
cp config.example.py config.py
```

Edit `config.py` with your GCP project ID, BigQuery dataset/table names, OpenWeatherMap key, and path to your service account JSON.

### 2. Authenticate with Google Cloud

```bash
gcloud auth login
gcloud config set project project-weather-494814
```

### 3. Deploy the Flask backend

```bash
cd service
gcloud run deploy weather-service \
  --source . \
  --project project-weather-494814 \
  --region europe-west6 \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1
```

Note the deployed URL — it goes into `config.py` as `SERVICE_CLOUD_RUN_URL`.

### 4. Deploy the Streamlit dashboard

```bash
cd dashboard
gcloud run deploy weather-dashboard \
  --source . \
  --project project-weather-494814 \
  --region europe-west6 \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --set-env-vars GCP_PROJECT_ID=project-weather-494814,BQ_DATASET_ID=weather_data,BQ_TABLE_ID=sensor_data
```

Verify both services are running:

```bash
gcloud run services describe weather-service   --region europe-west6
gcloud run services describe weather-dashboard --region europe-west6
```

### 5. Set up the M5Stack

1. Copy `m5stack/wifi_config.example.py` to `m5stack/wifi_config.py` and add your WiFi credentials
2. Upload `main.py` and `wifi_config.py` to the M5Stack via UIFlow File Manager
3. Upload the contents of `m5stack/flash_res/` to `/flash/res/` on the device
4. Run `main.py` — the device connects to WiFi and syncs from BigQuery automatically

### 6. Local development (dashboard only)

```bash
cd dashboard
pip install -r requirements.txt
streamlit run app.py
```

Requires a valid `config.py` at the project root with GCP credentials.

---

## ☁️ Google Cloud Resources

| Resource | Value |
|----------|-------|
| Project ID | `project-weather-494814` |
| Region | `europe-west6` (Zürich) |
| BigQuery Dataset | `weather_data` |
| BigQuery Table | `sensor_data` |

### BigQuery Schema

| Column | Type | Description |
|--------|------|-------------|
| `measurement_time` | TIMESTAMP | When the measurement was taken |
| `indoor_temp` | FLOAT | Indoor temperature (°C) |
| `indoor_humidity` | FLOAT | Indoor humidity (%) |
| `indoor_air_quality` | FLOAT | CO₂ level (ppm) |
| `outdoor_temp` | FLOAT | Outdoor temperature (°C) |
| `outdoor_humidity` | FLOAT | Outdoor humidity (%) |
| `ip_address` | STRING | M5Stack public IP (for geolocation) |
| `device_id` | STRING | Device identifier |

---

## 🔒 Security

Sensitive files are excluded from Git via `.gitignore`:
- `config.py` — GCP credentials and API keys
- `m5stack/wifi_config.py` — WiFi passwords
- `credentials/` — GCP service account JSON

Use `config.example.py` and `m5stack/wifi_config.example.py` as templates.

---

## 📅 Course Information

- **Course**: Cloud and Advanced Analytics
- **Institution**: HEC Lausanne / UNIL
- **Term**: Spring 2026
- **Final submission**: May 26, 2026
