import os

# Google Cloud / BigQuery
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "project-weather-494814")
DATASET_ID = os.environ.get("BQ_DATASET_ID", "weather_data")
TABLE_ID   = os.environ.get("BQ_TABLE_ID", "sensor_data")

# OpenWeatherMap
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "e563987fe14945673a0204d4d4a30ce2")
CITY         = os.environ.get("CITY", "Lausanne")
COUNTRY_CODE = os.environ.get("COUNTRY_CODE", "CH")

# Alert thresholds
HUMIDITY_LOW_THRESHOLD    = 40   # % — alert if below
AIR_QUALITY_BAD_THRESHOLD = 150  # AQI — alert if above

# Dashboard settings
REFRESH_INTERVAL_SECONDS = 60
HISTORY_HOURS = 24  # default history window in hours
