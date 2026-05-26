import os

# Google Cloud / BigQuery
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "project-weather-494814")
DATASET_ID = os.environ.get("BQ_DATASET_ID", "weather_data")
TABLE_ID   = os.environ.get("BQ_TABLE_ID", "sensor_data")


# Alert thresholds — CO2 in ppm
HUMIDITY_LOW_THRESHOLD = 40    # % — alert if below
CO2_BAD_THRESHOLD      = 1200  # ppm — poor air quality
CO2_ALERT_THRESHOLD    = 1500  # ppm — danger alert

