# Weather Monitor Dashboard

Streamlit dashboard deployed on Google Cloud Run to monitor indoor/outdoor weather data in real time.

## Structure

```
dashboard/
├── app.py              # Main Streamlit interface
├── bigquery_client.py  # BigQuery queries
├── weather_api.py      # OpenWeatherMap API
├── config.py           # Configuration variables
├── requirements.txt    # Python dependencies
└── Dockerfile          # For Cloud Run
```

## Environment Variables

Configure these in Cloud Run (never hardcode them in the source code):

| Variable | Description | Example |
|---|---|---|
| `GCP_PROJECT_ID` | Google Cloud project ID | `project-weather-494814` |
| `BQ_DATASET_ID` | BigQuery dataset | `weather_data` |
| `BQ_TABLE_ID` | BigQuery table | `sensor_data` |
| `OPENWEATHER_API_KEY` | OpenWeatherMap API key | `abc123...` |
| `CITY` | City for weather data | `Lausanne` |
| `COUNTRY_CODE` | ISO country code | `CH` |

## Deployment on Google Cloud Run

### 1. Authenticate
```bash
gcloud auth login
gcloud config set project project-weather-494814
```

### 2. Build & Deploy (single command)
```bash
cd dashboard/

gcloud run deploy weather-dashboard \
  --source . \
  --region europe-west6 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars GCP_PROJECT_ID=project-weather-494814,BQ_DATASET_ID=weather_data,BQ_TABLE_ID=sensor_data,OPENWEATHER_API_KEY=YOUR_KEY,CITY=Lausanne,COUNTRY_CODE=CH \
  --memory 512Mi \
  --cpu 1
```

### 3. Verify deployment
```bash
gcloud run services describe weather-dashboard --region europe-west6
```

## Features

- Real-time data from BigQuery (auto-refresh every 60s)
- Alerts if humidity < 40% or AQI > 150
- Outdoor weather via OpenWeatherMap
- 5-day forecast
- Historical charts (6h / 12h / 24h / 48h / 7 days)
- Daily statistics (last 7 days)
- Dark responsive design

## Local Development

```bash
pip install -r requirements.txt

export OPENWEATHER_API_KEY=your_key
export GCP_PROJECT_ID=project-weather-494814

streamlit run app.py
```
