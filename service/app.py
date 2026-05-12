import os
from flask import Flask, jsonify, request, send_file
from bigquery_client import BigQueryClient
from weather_client import WeatherClient
from vertexai_client import VertexAIClient
from texttospeech_client import TextToSpeechClient


app = Flask(__name__)
bq_client = BigQueryClient()
weather_client = WeatherClient()
vertex_ai_client = VertexAIClient()
texttospeech_client = TextToSpeechClient()
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
