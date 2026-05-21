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

        # Enrich with real outdoor weather from OpenWeatherMap
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
    """Return current weather and forecast as JSON."""
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

        temp = current["main"]["temp"]
        feels = current["main"]["feels_like"]
        hum  = current["main"]["humidity"]
        desc = current["weather"][0]["description"].title()
        city = current.get("name", "Unknown")
        wind = current.get("wind", {}).get("speed", 0)

        # ── Canvas 320x95 ─────────────────────────────────────
        img  = Image.new('RGB', (320, 95), color=(8, 8, 20))
        draw = ImageDraw.Draw(img)

        # Top accent line
        draw.rectangle([(0, 0), (320, 2)], fill=(0, 229, 255))

        # City name — cyan top left
        draw.text((10, 6),  city[:18],               fill=(0, 229, 255))

        # Temperature — large amber
        draw.text((10, 22), '{:.1f}C'.format(temp),  fill=(255, 171, 0))

        # Feels like — small grey
        draw.text((10, 58), 'Feels {:.0f}C'.format(feels), fill=(100, 100, 130))

        # Description — white centre
        draw.text((10, 72), desc[:28],               fill=(200, 200, 220))

        # Humidity — right side blue
        draw.text((210, 22), 'Hum',                  fill=(80, 100, 120))
        draw.text((210, 36), '{}%'.format(hum),      fill=(68, 138, 255))

        # Wind — right side
        draw.text((210, 58), 'Wind',                 fill=(80, 100, 120))
        draw.text((210, 72), '{:.1f}m/s'.format(wind), fill=(150, 150, 180))

        # Vertical separator
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

        # Top accent line
        draw.rectangle([(0, 0), (320, 2)], fill=(0, 229, 255))

        # Column headers
        x_positions = [10, 115, 220]
        for i, fc in enumerate(forecasts):
            x = x_positions[i]
            date = datetime.strptime(fc['dt_txt'], '%Y-%m-%d %H:%M:%S')
            draw.text((x, 6),  date.strftime('%a %d'),        fill=(0, 229, 255))
            draw.text((x, 26), '{}C'.format(round(fc['main']['temp'])), fill=(255, 171, 0))
            draw.text((x, 46), '{}%'.format(fc['main']['humidity']),    fill=(68, 138, 255))
            draw.text((x, 66), fc['weather'][0]['description'][:12],    fill=(160, 160, 180))
            draw.text((x, 86), '{:.1f}m/s'.format(fc['wind']['speed']), fill=(120, 120, 150))
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

        # Build a rich context for Gemini
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

@app.route('/ask-question', methods=['POST'])
def ask_question():
    """
    Receive raw audio from M5Stack, transcribe it with Speech-to-Text,
    answer with Gemini (with weather + BigQuery context), return audio WAV.
    """
    try:
        # 1. Get audio bytes from request
        audio_bytes = request.data
        if not audio_bytes:
            return jsonify({"error": "No audio data received"}), 400

        # 2. Get IP for weather context
        ip = request.args.get('ip', '8.8.8.8')

        # 3. Transcribe audio → text
        question = speech_to_text_client.transcribe_audio(audio_bytes)
        if not question:
            return jsonify({"error": "Could not understand audio"}), 400

        # 4. Build context: current weather + latest BigQuery data
        location_data = weather_client.fetch_location_data(ip)
        lat, lon = location_data['loc'].split(',')
        current_weather = weather_client.fetch_weather_data(lat, lon, current_weather=True)
        latest_data = bq_client.get_latest_sensor_data()

        context = f"""
Current outdoor weather: {current_weather}
Latest indoor sensor data from BigQuery: {latest_data}
User question: {question}
"""

        SYSTEM_INSTRUCTION = """You are a smart home weather assistant.
Answer the user's question based on the provided weather and sensor data.
Be concise (max 60 words), friendly and helpful.
No emojis, no special characters."""

        # 5. Generate answer with Gemini
        answer = vertex_ai_client.get_weather_description(context, SYSTEM_INSTRUCTION)

        # 6. Convert answer to speech
        audio = text_to_speech_client.generate_speech(answer)

        temp_file = os.path.join(TMP_DIR, 'answer_output.wav')
        with open(temp_file, 'wb') as f:
            f.write(audio)
        return send_file(temp_file, mimetype='audio/wav')

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)