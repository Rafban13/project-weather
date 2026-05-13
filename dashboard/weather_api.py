import requests
from config import OPENWEATHER_API_KEY, CITY, COUNTRY_CODE


BASE_URL = "https://api.openweathermap.org/data/2.5"


def get_current_weather():
    """Fetch current weather for the configured city."""
    url = f"{BASE_URL}/weather"
    params = {
        "q": f"{CITY},{COUNTRY_CODE}",
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
        "lang": "fr"
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return {
            "city": data["name"],
            "temp": data["main"]["temp"],
            "feels_like": data["main"]["feels_like"],
            "humidity": data["main"]["humidity"],
            "description": data["weather"][0]["description"].capitalize(),
            "icon": data["weather"][0]["icon"],
            "wind_speed": data["wind"]["speed"],
            "pressure": data["main"]["pressure"],
        }
    except Exception as e:
        return {"error": str(e)}


def get_forecast():
    """Fetch 5-day / 3-hour forecast, grouped by day."""
    url = f"{BASE_URL}/forecast"
    params = {
        "q": f"{CITY},{COUNTRY_CODE}",
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
        "lang": "fr",
        "cnt": 40  # 5 days × 8 readings/day
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        # Group by date and keep noon reading (or first available)
        days = {}
        for item in data["list"]:
            date = item["dt_txt"].split(" ")[0]
            hour = item["dt_txt"].split(" ")[1]
            if date not in days or hour == "12:00:00":
                days[date] = {
                    "date": date,
                    "temp_min": item["main"]["temp_min"],
                    "temp_max": item["main"]["temp_max"],
                    "description": item["weather"][0]["description"].capitalize(),
                    "icon": item["weather"][0]["icon"],
                    "humidity": item["main"]["humidity"],
                }

        return list(days.values())[:5]
    except Exception as e:
        return {"error": str(e)}


def icon_url(icon_code: str) -> str:
    return f"https://openweathermap.org/img/wn/{icon_code}@2x.png"
