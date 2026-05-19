import os
from flask import Flask, jsonify, request, send_file
from bigquery_client import BigQueryClient
from weather_client import WeatherClient
from vertexai_client import VertexAIClient
from texttospeech_client import TextToSpeechClient
from PIL import Image, ImageDraw, ImageFont
import io

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
    

if __name__== '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)


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
        
        # Convertir en bytes
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        
        return send_file(buf, mimetype='image/png')
    except Exception as e:
        return jsonify({"error": str(e)}), 500