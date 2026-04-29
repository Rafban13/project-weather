# 🌤️ Project Weather

> Indoor & Outdoor Weather Monitoring System
> Cloud and Advanced Analytics — Spring 2026

## 👥 Team

- **Raffaele-Alban Bakija** ([@Rafban13](https://github.com/Rafban13)) — *role TBD*
- **Arlind Kadriu** ([@63didi](https://github.com/63didi)) — *role TBD*

## 📋 Project Overview

This project implements an indoor/outdoor weather monitoring system using an M5Stack IoT device equipped with environmental sensors. The system collects indoor measurements (temperature, humidity, air quality) and combines them with outdoor weather data fetched from external APIs. All data is stored in Google BigQuery and visualized through both an on-device interface and a cloud-based Streamlit dashboard.

The device also features voice announcements (Text-to-Speech), AI-generated weather descriptions (Vertex AI / Gemini), and motion-triggered interactions.

## 🏗️ Architecture

The project follows a 3-tier architecture:

- **Data layer**: Google BigQuery (sensor data + historical weather)
- **Middleware**: Flask service deployed on Google Cloud Run
- **UI layer**:
  - On-device: M5Stack Core2 (Python / UIFlow)
  - Cloud: Streamlit dashboard deployed on Google Cloud Run

## 📁 Repository Structure

```
project-weather/
├── m5stack/          # M5Stack device code (Python)
├── service/          # Flask backend service
├── dashboard/        # Streamlit cloud dashboard
├── sql/              # BigQuery schema and queries
└── res/              # Static assets (images, fonts, icons)
```

## 🚀 Status

🚧 **In active development** — see commit history for progress.

## ☁️ Google Cloud Setup

- **Project ID**: `project-weather-494814`
- **Region**: `europe-west6` (Zürich)
- **BigQuery Dataset**: `weather_data`
- **BigQuery Table**: `sensor_data`

### Schema of `sensor_data`

| Column | Type | Description |
|--------|------|-------------|
| `measurement_time` | TIMESTAMP | When the measurement was taken |
| `indoor_temp` | FLOAT | Indoor temperature (°C) |
| `indoor_humidity` | FLOAT | Indoor humidity (%) |
| `indoor_air_quality` | FLOAT | Indoor air quality / CO2 (ppm) |
| `outdoor_temp` | FLOAT | Outdoor temperature (°C) |
| `outdoor_humidity` | FLOAT | Outdoor humidity (%) |
| `ip_address` | STRING | M5Stack IP (for geolocation) |
| `device_id` | STRING | Device identifier |

### APIs Enabled

- BigQuery API
- Cloud Run Admin API
- Cloud Build API
- Artifact Registry API
- Vertex AI API
- Cloud Text-to-Speech API
- Cloud Speech-to-Text API

## 📅 Course Information

- **Course**: Cloud and Advanced Analytics
- **Institution**: HEC Lausanne / UNIL
- **Term**: Spring 2026
- **Final submission**: May 26, 2026