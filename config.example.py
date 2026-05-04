# ============================================
# Project Weather - Configuration Template
# ============================================
# Copy this file to `config.py` and fill in your real values.
# `config.py` is gitignored and will NOT be committed.

# Google Cloud
PROJECT_ID = "your-gcp-project-id"
PROJECT_LOCATION = "europe-west6"
DATASET_NAME = "weather_data"
SENSOR_TABLE = "sensor_data"

# Path to the GCP service account key (relative to project root)
GOOGLE_APPLICATION_CREDENTIALS = "credentials/gcp-service-account.json"

# OpenWeatherMap API
# Get your free API key at https://home.openweathermap.org/api_keys
OPENWEATHERMAP_API_KEY = "your-openweathermap-api-key"

# IPInfo API (optional, used for IP-based geolocation)
# Get your free API key at https://ipinfo.io/signup
IPINFO_API_KEY = ""

# Backend service URL (filled after Cloud Run deployment)
SERVICE_CLOUD_RUN_URL = "https://weather-service-197991375095.europe-west6.run.app"