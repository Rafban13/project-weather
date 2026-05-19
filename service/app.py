import os
from flask import Flask, jsonify, request, send_file
from bigquery_client import BigQueryClient
from weather_client import WeatherClient
from vertexai_client import VertexAIClient
from texttospeech_client import TextToSpeechClient
from PIL import Image, ImageDraw, ImageFont
import io
from datetime import datetime

app = Flask(__name__)
bq_client = BigQueryClient()
weather_client = WeatherClient()
vertex_ai_client = VertexAIClient()
text_to_speech_client = TextToSpeechClient()
TMP_DIR = '/tmp'

@app.route("/")
def home():
    return "Hello from Project Weather !"

@app.route('/send-to-bigquery', methods=['POST'])
def send_to_bigquery():
    try:
        data = request.get_json()
        result = bq_client.insert_sensor_data(data)
        return jsonify({"message": result}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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

@app.route('/generate-current-weather-spoken', methods=['POST'])
def generate_current_weather_spoken():
    data = request.get_json()
    if 'ip' not in data:
        return jsonify({"error": "IP address is required"}), 400
    try:
        location_data = weather_client.fetch_location_data(data['ip'])
        lat, lon = location_data['loc'].split(',')
        current_weather = weather_client.fetch_weather_data(lat, lon, current_weather=True)

        SYSTEM_INSTRUCTION = """You are a weather assistant. Generate a playful and engaging weather description. Max 50 words. No emojis, no special characters."""

        description = vertex_ai_client.get_weather_description(str(current_weather), SYSTEM_INSTRUCTION)
        audio = text_to_speech_client.generate_speech(description)

        temp_file = os.path.join(TMP_DIR, 'weather_output.wav')
        with open(temp_file, 'wb') as f:
            f.write(audio)

        return send_file(temp_file, mimetype='audio/wav')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get-weather-image', methods=['GET'])
def get_weather_image():
    try:
        ip = request.args.get('ip', '8.8.8.8')
        location = weather_client.fetch_location_data(ip)
        lat, lon = location['loc'].split(',')
        current = weather_client.fetch_weather_data(lat, lon, current_weather=True)

        temp = current["main"]["temp"]
        hum = current["main"]["humidity"]
        desc = current["weather"][0]["description"]
        city = current.get("name", "Unknown")

        # Créer l'image 320x80 pixels (largeur M5Stack, hauteur partielle)
        img = Image.new('RGB', (320, 80), color=(10, 10, 30))
        draw = ImageDraw.Draw(img)

        # Température en grand — orange
        draw.text((10, 5), '{:.1f}C'.format(temp), fill=(205, 129, 0))

        # Humidité — blanc
        draw.text((180, 5), 'Hum: {}%'.format(hum), fill=(255, 255, 255))

        # Description — gris
        draw.text((10, 50), desc[:30], fill=(150, 150, 150))

        # Ville — cyan
        draw.text((180, 50), city[:15], fill=(0, 200, 255))

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)

        return send_file(buf, mimetype='image/png')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get-forecast-image', methods=['GET'])
def get_forecast_image():
    """Génère une image PNG 320x110 avec les prévisions sur 3 jours pour le M5Stack."""
    try:
        ip = request.args.get('ip', '8.8.8.8')
        location = weather_client.fetch_location_data(ip)
        lat, lon = location['loc'].split(',')
        forecast_data = weather_client.fetch_weather_data(lat, lon, current_weather=False)

        # Prévisions à ~24h, ~48h, ~72h
        forecasts = [
            forecast_data['list'][8],
            forecast_data['list'][16],
            forecast_data['list'][24],
        ]

        # Image 320x110 pixels — fond noir
        img = Image.new('RGB', (320, 110), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Titre en haut
        draw.text((10, 2), 'FORECAST', fill=(100, 100, 100))
        draw.line([(0, 16), (320, 16)], fill=(40, 40, 40), width=1)

        # 3 colonnes
        x_positions = [10, 115, 220]

        for i, fc in enumerate(forecasts):
            x = x_positions[i]

            # Date — ex: "Wed 21"
            date = datetime.strptime(fc['dt_txt'], '%Y-%m-%d %H:%M:%S')
            formatted_date = date.strftime('%a %d')

            temp = fc['main']['temp']
            hum = fc['main']['humidity']
            desc = fc['weather'][0]['description']

            # Jour — orange
            draw.text((x, 20), formatted_date, fill=(255, 161, 3))

            # Température — blanc
            draw.text((x, 40), '{}C'.format(round(temp)), fill=(255, 255, 255))

            # Humidité — bleu clair
            draw.text((x, 60), '{}%'.format(hum), fill=(136, 204, 255))

            # Description courte — gris
            draw.text((x, 80), desc[:12], fill=(120, 120, 120))

            # Séparateur vertical
            if i < 2:
                draw.line([(x + 95, 18), (x + 95, 108)], fill=(40, 40, 40), width=1)

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)

        return send_file(buf, mimetype='image/png')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)