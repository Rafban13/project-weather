import os
from flask import Flask, jsonify, request, send_file
from bigquery_client import BigQueryClient
from weather_client import WeatherClient
from vertexai_client import VertexAIClient
from texttospeech_client import TextToSpeechClient
from speechtotext_client import SpeechToTextClient
from PIL import Image, ImageDraw
import io
from datetime import datetime

app = Flask(__name__)
bq_client = BigQueryClient()
weather_client = WeatherClient()
vertex_ai_client = VertexAIClient()
text_to_speech_client = TextToSpeechClient()
speech_to_text_client = SpeechToTextClient()
TMP_DIR = '/tmp'


@app.route("/")
def home():
    return "Hello from Project Weather !"


# ─────────────────────────────────────────────────────────────
#  BIGQUERY
# ─────────────────────────────────────────────────────────────

@app.route('/send-to-bigquery', methods=['POST'])
def send_to_bigquery():
    """Receive sensor data from M5Stack and store in BigQuery."""
    try:
        data = request.get_json()
        ip = data.get('ip_address')
        if not ip:
            return jsonify({"error": "ip_address is required"}), 400

        location = weather_client.fetch_location_data(ip)
        lat, lon = location['loc'].split(',')
        current = weather_client.fetch_weather_data(lat, lon, current_weather=True)
        data['outdoor_temp'] = current['main']['temp']
        data['outdoor_humidity'] = current['main']['humidity']

        result = bq_client.insert_sensor_data(data)
        return jsonify({"message": result}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/sync-from-bigquery', methods=['GET'])
def sync_from_bigquery():
    """Return the latest sensor row from BigQuery for device startup sync."""
    try:
        result = bq_client.get_latest_sensor_data()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────
#  OUTDOOR WEATHER
# ─────────────────────────────────────────────────────────────

@app.route('/get-outdoor-weather', methods=['GET'])
def get_outdoor_weather():
    try:
        ip = request.args.get('ip', '8.8.8.8')
        location = weather_client.fetch_location_data(ip)
        lat, lon = location['loc'].split(',')
        current = weather_client.fetch_weather_data(lat, lon, current_weather=True)
        forecast = weather_client.fetch_weather_data(lat, lon, current_weather=False)
        return jsonify({
            "location": location.get('city', 'Unknown'),
            "current": current,
            "forecast": forecast
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────
#  WEATHER IMAGES
# ─────────────────────────────────────────────────────────────

@app.route('/get-weather-image', methods=['GET'])
def get_weather_image():
    """Generate a 320x95 PNG showing current outdoor weather for M5Stack."""
    try:
        ip = request.args.get('ip', '8.8.8.8')
        location = weather_client.fetch_location_data(ip)
        lat, lon = location['loc'].split(',')
        current = weather_client.fetch_weather_data(lat, lon, current_weather=True)

        temp  = current["main"]["temp"]
        feels = current["main"]["feels_like"]
        hum   = current["main"]["humidity"]
        desc  = current["weather"][0]["description"].title()
        city  = current.get("name", "Unknown")
        wind  = current.get("wind", {}).get("speed", 0)

        img  = Image.new('RGB', (320, 95), color=(8, 8, 20))
        draw = ImageDraw.Draw(img)

        draw.rectangle([(0, 0), (320, 2)], fill=(0, 229, 255))
        draw.text((10, 6),  city[:18],                    fill=(0, 229, 255))
        draw.text((10, 22), '{:.1f}C'.format(temp),       fill=(255, 171, 0))
        draw.text((10, 58), 'Feels {:.0f}C'.format(feels),fill=(100, 100, 130))
        draw.text((10, 72), desc[:28],                    fill=(200, 200, 220))
        draw.text((210, 22), 'Hum',                       fill=(80, 100, 120))
        draw.text((210, 36), '{}%'.format(hum),           fill=(68, 138, 255))
        draw.text((210, 58), 'Wind',                      fill=(80, 100, 120))
        draw.text((210, 72), '{:.1f}m/s'.format(wind),    fill=(150, 150, 180))
        draw.line([(200, 8), (200, 88)], fill=(30, 30, 50), width=1)

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return send_file(buf, mimetype='image/png')
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get-forecast-image', methods=['GET'])
def get_forecast_image():
    """Generate a 320x110 PNG showing 3-day forecast for M5Stack."""
    try:
        ip = request.args.get('ip', '8.8.8.8')
        location = weather_client.fetch_location_data(ip)
        lat, lon = location['loc'].split(',')
        forecast_data = weather_client.fetch_weather_data(lat, lon, current_weather=False)

        forecasts = [
            forecast_data['list'][8],
            forecast_data['list'][16],
            forecast_data['list'][24],
        ]

        img  = Image.new('RGB', (320, 110), color=(8, 8, 20))
        draw = ImageDraw.Draw(img)
        draw.rectangle([(0, 0), (320, 2)], fill=(0, 229, 255))

        x_positions = [10, 115, 220]
        for i, fc in enumerate(forecasts):
            x = x_positions[i]
            date = datetime.strptime(fc['dt_txt'], '%Y-%m-%d %H:%M:%S')
            draw.text((x, 6),  date.strftime('%a %d'),                     fill=(0, 229, 255))
            draw.text((x, 26), '{}C'.format(round(fc['main']['temp'])),    fill=(255, 171, 0))
            draw.text((x, 46), '{}%'.format(fc['main']['humidity']),       fill=(68, 138, 255))
            draw.text((x, 66), fc['weather'][0]['description'][:12],       fill=(160, 160, 180))
            draw.text((x, 86), '{:.1f}m/s'.format(fc['wind']['speed']),    fill=(120, 120, 150))
            if i < 2:
                draw.line([(x + 95, 4), (x + 95, 106)], fill=(30, 30, 50), width=1)

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return send_file(buf, mimetype='image/png')
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────
#  VOICE — TTS (PIR triggered)
# ─────────────────────────────────────────────────────────────

@app.route('/generate-current-weather-spoken', methods=['POST'])
def generate_current_weather_spoken():
    """Generate a spoken weather announcement triggered by PIR motion sensor."""
    data = request.get_json()
    if 'ip' not in data:
        return jsonify({"error": "IP address is required"}), 400
    try:
        location_data = weather_client.fetch_location_data(data['ip'])
        lat, lon = location_data['loc'].split(',')
        current_weather = weather_client.fetch_weather_data(lat, lon, current_weather=True)
        forecast_data   = weather_client.fetch_weather_data(lat, lon, current_weather=False)
        next_day = forecast_data['list'][8]

        context = {
            "current": current_weather,
            "tomorrow": next_day
        }

        SYSTEM_INSTRUCTION = """You are a friendly smart home weather assistant.
Speak naturally and concisely (max 60 words).
Give the current conditions AND one practical tip (umbrella, sunscreen, jacket, etc).
No emojis, no special characters. Be warm and engaging."""

        description = vertex_ai_client.get_weather_description(str(context), SYSTEM_INSTRUCTION)
        audio = text_to_speech_client.generate_speech(description)

        temp_file = os.path.join(TMP_DIR, 'weather_output.wav')
        with open(temp_file, 'wb') as f:
            f.write(audio)
        return send_file(temp_file, mimetype='audio/wav')
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────
#  VOICE — Speech-to-Text + Gemini Q&A
# ─────────────────────────────────────────────────────────────

def _get_weather_for_city(city_name: str) -> dict:
    """Fetch weather for any city by name using OpenWeatherMap."""
    try:
        url = (f"https://api.openweathermap.org/data/2.5/weather"
               f"?q={city_name}&appid={weather_client.openweathermap_api_key}&units=metric")
        import requests
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return {}
    except:
        return {}

def _get_forecast_for_city(city_name: str) -> dict:
    """Fetch forecast for any city by name using OpenWeatherMap."""
    try:
        url = (f"https://api.openweathermap.org/data/2.5/forecast"
               f"?q={city_name}&appid={weather_client.openweathermap_api_key}&units=metric")
        import requests
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return {}
    except:
        return {}


@app.route('/ask-question', methods=['POST'])
def ask_question():
    """
    Receive audio from M5Stack, transcribe with Speech-to-Text,
    answer with Gemini (weather + BigQuery context), return audio WAV.
    Supports questions about any city worldwide.
    """
    try:
        audio_bytes = request.data
        if not audio_bytes:
            return jsonify({"error": "No audio data received"}), 400

        ip = request.args.get('ip', '8.8.8.8')

        # 1. Transcribe audio → text
        question = speech_to_text_client.transcribe_audio(audio_bytes)
        if not question:
            # Return a "didn't understand" audio response
            sorry = "Sorry, I didn't catch that. Could you please repeat your question?"
            audio = text_to_speech_client.generate_speech(sorry)
            temp_file = os.path.join(TMP_DIR, 'answer_output.wav')
            with open(temp_file, 'wb') as f:
                f.write(audio)
            return send_file(temp_file, mimetype='audio/wav'), 200

        # 2. Get local weather context
        location_data = weather_client.fetch_location_data(ip)
        lat, lon = location_data['loc'].split(',')
        local_city = location_data.get('city', 'your location')
        current_weather = weather_client.fetch_weather_data(lat, lon, current_weather=True)
        forecast_data   = weather_client.fetch_weather_data(lat, lon, current_weather=False)
        next_days = forecast_data['list'][:8]  # next 24h
        latest_data = bq_client.get_latest_sensor_data()

        # 3. Detect if question mentions another city
        # Ask Gemini to extract city name from question
        city_extract_prompt = f"""
Extract the city name from this question if it mentions a specific city.
Question: "{question}"
Reply with ONLY the city name, or reply with "none" if no city is mentioned.
Examples:
- "What is the weather in Geneva?" → Geneva
- "Will it rain in Tokyo tomorrow?" → Tokyo  
- "What is the temperature outside?" → none
- "Should I take an umbrella?" → none
"""
        extracted_city = vertex_ai_client.get_weather_description(
            city_extract_prompt,
            "You extract city names from questions. Reply with ONLY the city name or 'none'."
        ).strip().lower()

        # 4. If another city detected, fetch its weather
        extra_city_context = ""
        if extracted_city and extracted_city != "none" and extracted_city != local_city.lower():
            city_weather = _get_weather_for_city(extracted_city)
            city_forecast = _get_forecast_for_city(extracted_city)
            if city_weather:
                extra_city_context = f"\nWeather for {extracted_city}: {city_weather}"
            if city_forecast:
                extra_city_context += f"\nForecast for {extracted_city}: {city_forecast['list'][:8]}"

        # 5. Build full context for Gemini
        context = f"""
Local city: {local_city}
Current outdoor weather (local): {current_weather}
Weather forecast next 24h (local): {next_days}
Latest indoor sensor data: {latest_data}
{extra_city_context}
User question: {question}
"""

        SYSTEM_INSTRUCTION = """You are a smart home weather assistant.
Answer the user's question based on the provided weather and sensor data.
Be concise (max 60 words), friendly and helpful.
If the user asks about a specific city, use the weather data provided for that city.
No emojis, no special characters.
Always respond in English, regardless of the language the user speaks."""

        # 6. Generate answer with Gemini
        answer = vertex_ai_client.get_weather_description(context, SYSTEM_INSTRUCTION)

        # 7. Convert answer to speech
        audio = text_to_speech_client.generate_speech(answer)

        temp_file = os.path.join(TMP_DIR, 'answer_output.wav')
        with open(temp_file, 'wb') as f:
            f.write(audio)
        return send_file(temp_file, mimetype='audio/wav')

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)