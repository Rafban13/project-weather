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
    Recoit un WAV depuis le M5Stack, transcrit, detecte si une ville est mentionnee.
    Renvoie JSON :
      - Si ville detectee : {"type":"image", "transcription":"...", "city":"Tokyo"}
        Le M5Stack appellera ensuite /get-weather-image-large?city=Tokyo
      - Sinon : {"type":"text", "transcription":"...", "lines":[["Label","Value"],...]}
        Le M5Stack affichera ces paires label/valeur en mode tabulaire
    """
    try:
        audio_bytes = request.data
        if not audio_bytes:
            return jsonify({"type":"text", "transcription":"",
                            "lines":[["Error","No audio received"]]}), 200
 
        ip = request.args.get('ip', '8.8.8.8')
 
        # 1. Speech-to-Text
        question = speech_to_text_client.transcribe_audio(audio_bytes)
        if not question:
            return jsonify({
                "type":"text",
                "transcription":"(could not understand)",
                "lines":[["Status","Please retry"],
                         ["Tip","Speak louder"]]
            }), 200
 
        # 2. Detecter si une ville est mentionnee dans la question
        city_extract_prompt = (
            'Extract the city name from this question if it mentions one. '
            'Question: "{}". '
            'Reply with ONLY the city name capitalized, or "none". '
            'Examples: "weather in Tokyo" -> Tokyo, '
            '"temperature outside" -> none, '
            '"will it rain in Paris" -> Paris.'
        ).format(question)
 
        extracted_city = vertex_ai_client.get_weather_description(
            city_extract_prompt,
            "You extract city names. Reply with ONLY the city name or 'none'."
        ).strip()
 
        # 3a. Si ville detectee, on dit au M5Stack de demander l'image
        if extracted_city and extracted_city.lower() != "none":
            # Verifier que la ville existe vraiment dans OpenWeather
            test_weather = _get_weather_for_city(extracted_city)
            if test_weather and test_weather.get('main'):
                return jsonify({
                    "type":"image",
                    "transcription": question,
                    "city": extracted_city
                }), 200
            # Si l'API OpenWeather ne reconnait pas la ville, fallback texte
            return jsonify({
                "type":"text",
                "transcription": question,
                "lines":[["City", extracted_city[:18]],
                         ["Status", "Not found"]]
            }), 200
 
        # 3b. Sinon, question generale : reponse texte structuree
        location_data = weather_client.fetch_location_data(ip)
        lat, lon = location_data['loc'].split(',')
        local_city = location_data.get('city', 'your location')
        current_weather = weather_client.fetch_weather_data(lat, lon, current_weather=True)
        forecast_data   = weather_client.fetch_weather_data(lat, lon, current_weather=False)
        next_days = forecast_data['list'][:8]
        latest_indoor = bq_client.get_latest_sensor_data()
 
        # Demande a Gemini une reponse structuree en paires label/valeur
        # pour affichage tabulaire sur le M5Stack (320x240, max 6 lignes)
        structured_prompt = (
            'User question: "{}"\n'
            'Local city: {}\n'
            'Outdoor weather: {}\n'
            'Next 24h forecast: {}\n'
            'Indoor sensors: {}\n\n'
            'Answer the question using the data above. '
            'Reply ONLY with a JSON array of 3 to 6 [label, value] pairs. '
            'Labels are short (max 12 chars), values are short (max 18 chars). '
            'Example output: '
            '[["Topic","Indoor temp"],["Now","22.3 C"],["Trend","Stable"]]. '
            'No markdown, no comments, no code fences, just the JSON array.'
        ).format(question, local_city, current_weather, next_days, latest_indoor)
 
        SYSTEM_INSTRUCTION = (
            "You return ONLY a JSON array of [label,value] pairs. "
            "No prose, no markdown fences, just the raw JSON array."
        )
 
        raw_answer = vertex_ai_client.get_weather_description(
            structured_prompt, SYSTEM_INSTRUCTION
        )
 
        # Nettoyer la reponse de Gemini (peut contenir des backticks ou du markdown)
        cleaned = raw_answer.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.split('```')[1]
            if cleaned.startswith('json'):
                cleaned = cleaned[4:]
        cleaned = cleaned.strip()
 
        try:
            import json as _json
            lines = _json.loads(cleaned)
            if not isinstance(lines, list):
                raise ValueError("Not a list")
            # Valider la forme [[str,str],...] et limiter la longueur
            lines = [[str(p[0])[:14], str(p[1])[:18]]
                     for p in lines if len(p) >= 2]
            if not lines:
                lines = [["Answer", "No data"]]
        except Exception:
            # Fallback : si Gemini n'a pas renvoye du JSON propre
            lines = [["Answer", cleaned[:18] if cleaned else "No data"]]
 
        return jsonify({
            "type":"text",
            "transcription": question,
            "lines": lines[:6]
        }), 200
 
    except Exception as e:
        return jsonify({
            "type":"text",
            "transcription":"(error)",
            "lines":[["Error", str(e)[:18]]]
        }), 200


@app.route('/get-weather-image-large', methods=['GET'])
def get_weather_image_large():
    """
    Genere un PNG 320x240 stylise pour la meteo d'une ville donnee.
    Utilise par le M5Stack quand la question concerne une ville.
    """
    try:
        city = request.args.get('city', 'Lausanne')
        weather_data = _get_weather_for_city(city)
 
        if not weather_data or not weather_data.get('main'):
            # Image d'erreur si la ville n'est pas trouvee
            img = Image.new('RGB', (320, 240), color=(10, 10, 15))
            draw = ImageDraw.Draw(img)
            draw.rectangle([(0, 0), (320, 3)], fill=(255, 23, 68))
            draw.text((20, 100), "City not found:", fill=(255, 200, 200))
            draw.text((20, 120), city[:20], fill=(255, 255, 255))
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            return send_file(buf, mimetype='image/png')
 
        temp  = weather_data["main"]["temp"]
        feels = weather_data["main"]["feels_like"]
        hum   = weather_data["main"]["humidity"]
        press = weather_data["main"].get("pressure", 0)
        desc  = weather_data["weather"][0]["description"].title()
        wind  = weather_data.get("wind", {}).get("speed", 0)
        name  = weather_data.get("name", city)
 
        # Palette coherente avec le design du M5Stack (dark minimalist)
        img  = Image.new('RGB', (320, 240), color=(10, 10, 15))
        draw = ImageDraw.Draw(img)
 
        # Bandeau accent en haut
        draw.rectangle([(0, 0), (320, 3)], fill=(0, 229, 255))
 
        # Ville en haut
        draw.text((14, 12), name[:24], fill=(0, 229, 255))
 
        # Temperature en gros
        draw.text((14, 35), '{:.1f}'.format(temp), fill=(255, 171, 0))
        draw.text((100, 50), 'C', fill=(255, 171, 0))
 
        # "Feels like" sous la temp
        draw.text((14, 78), 'Feels {:.0f}C'.format(feels), fill=(120, 120, 150))
 
        # Description meteo
        draw.text((14, 100), desc[:32], fill=(220, 220, 240))
 
        # Separateur horizontal
        draw.line([(14, 125), (306, 125)], fill=(60, 60, 80), width=1)
 
        # Colonne gauche : humidite et vent
        draw.text((14, 140), 'Humidity', fill=(100, 110, 130))
        draw.text((14, 155), '{}%'.format(hum), fill=(68, 138, 255))
        draw.text((14, 180), 'Wind', fill=(100, 110, 130))
        draw.text((14, 195), '{:.1f} m/s'.format(wind), fill=(150, 150, 180))
 
        # Colonne droite : pression et timestamp UTC
        draw.text((170, 140), 'Pressure', fill=(100, 110, 130))
        draw.text((170, 155), '{} hPa'.format(press), fill=(200, 200, 220))
 
        now_utc = datetime.utcnow().strftime('%H:%M UTC')
        draw.text((170, 180), 'Updated', fill=(100, 110, 130))
        draw.text((170, 195), now_utc, fill=(150, 150, 180))
 
        # Bandeau accent en bas
        draw.rectangle([(0, 237), (320, 240)], fill=(0, 229, 255))
 
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return send_file(buf, mimetype='image/png')
 
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)