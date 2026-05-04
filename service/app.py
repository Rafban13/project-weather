from flask import Flask, jsonify, request
from bigquery_client import BigQueryClient
from weather_client import WeatherClient

weather_client = WeatherClient()

app = Flask(__name__)
bq_client = BigQueryClient()
weather_client = WeatherClient()

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
        city = request.args.get('city', 'Lausanne')
        result = weather_client.get_current_weather(city)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__== '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
