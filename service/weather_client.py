import os
import requests

try:
    import config
    OPENWEATHERMAP_API_KEY = config.OPENWEATHERMAP_API_KEY
    IPINFO_API_KEY = config.IPINFO_API_KEY
except ImportError:
    OPENWEATHERMAP_API_KEY = os.getenv('OPENWEATHERMAP_API_KEY')
    IPINFO_API_KEY = os.getenv('IPINFO_API_KEY')

class WeatherClient:
    def __init__(self):
        self.ipinfo_api_key = IPINFO_API_KEY
        self.openweathermap_api_key = OPENWEATHERMAP_API_KEY
        self.base_url = "https://api.openweathermap.org/data/2.5"

    def fetch_location_data(self, ip: str) -> dict:
        """Get GPS coordinates from an IP address using IPInfo."""
        url = f"https://ipinfo.io/{ip}/json?token={self.ipinfo_api_key}"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()

    def fetch_weather_data(self, lat, lon, current_weather=False) -> dict:
        """Fetch current weather or forecast from OpenWeatherMap."""
        if current_weather:
            url = f"{self.base_url}/weather?lat={lat}&lon={lon}&appid={self.openweathermap_api_key}&units=metric"
        else:
            url = f"{self.base_url}/forecast?lat={lat}&lon={lon}&appid={self.openweathermap_api_key}&units=metric"
        
        response = requests.get(url)
        response.raise_for_status()
        return response.json()