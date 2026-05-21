import os
 
# Google Cloud / BigQuery
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "project-weather-494814")
DATASET_ID = os.environ.get("BQ_DATASET_ID", "weather_data")
TABLE_ID   = os.environ.get("BQ_TABLE_ID", "sensor_data")
 
# OpenWeatherMap
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "e563987fe14945673a0204d4d4a30ce2")
CITY         = os.environ.get("CITY", "Lausanne")
COUNTRY_CODE = os.environ.get("COUNTRY_CODE", "CH")
 
# Alert thresholds — CO2 in ppm
HUMIDITY_LOW_THRESHOLD    = 40    # % — alert if below
CO2_MODERATE_THRESHOLD    = 800   # ppm — moderate air quality
CO2_BAD_THRESHOLD         = 1200  # ppm — poor air quality
CO2_ALERT_THRESHOLD       = 1500  # ppm — alert triggered
 
# Dashboard settings
REFRESH_INTERVAL_SECONDS = 60
HISTORY_HOURS = 24
 
