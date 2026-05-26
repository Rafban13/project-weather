import requests
import bigquery_client as bq

FLASK_URL = 'https://weather-service-197991375095.europe-west6.run.app'


def _get_device_ip():
    """Get last device public IP from BigQuery — ensures same location as M5Stack."""
    try:
        latest = bq.get_latest_reading()
        if latest is not None and 'ip_address' in latest:
            ip = str(latest['ip_address']).strip()
            if ip and ip != 'unknown':
                return ip
    except Exception:
        pass
    return '8.8.8.8'


def get_current_weather():
    """Fetch current weather using the M5Stack device's geolocated IP."""
    try:
        ip = _get_device_ip()
        resp = requests.get(f'{FLASK_URL}/get-weather-json', params={'ip': ip}, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {'error': str(e)}


def get_forecast():
    """Fetch 5-day forecast using the M5Stack device's geolocated IP."""
    try:
        ip = _get_device_ip()
        resp = requests.get(f'{FLASK_URL}/get-forecast-json', params={'ip': ip}, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {'error': str(e)}


def icon_url(icon_code: str) -> str:
    """Return the OpenWeatherMap icon URL for a given icon code."""
    return f'https://openweathermap.org/img/wn/{icon_code}@2x.png'
