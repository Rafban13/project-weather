import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from flask import Flask, jsonify, request, send_file
from bigquery_client import BigQueryClient
from weather_client import WeatherClient
from vertexai_client import VertexAIClient
from texttospeech_client import TextToSpeechClient
from speechtotext_client import SpeechToTextClient
from PIL import Image, ImageDraw, ImageFont
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

def _fetch_weather_icon(icon_code, size):
    """Download an OWM icon and return it as an RGBA PIL Image, or None on failure."""
    try:
        url = 'https://openweathermap.org/img/wn/{}.png'.format(icon_code)
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            icon = Image.open(io.BytesIO(resp.content)).convert('RGBA')
            return icon.resize(size, Image.LANCZOS)
    except Exception:
        pass
    return None


def _paste_icon(base_img, icon, x, y, bg_color=(8, 8, 20)):
    """Paste an RGBA icon onto a RGB base image using its alpha channel."""
    if icon is None:
        return
    bg = Image.new('RGBA', icon.size, bg_color + (255,))
    bg.paste(icon, mask=icon.split()[3])
    base_img.paste(bg.convert('RGB'), (x, y))


def _font(size):
    """Load a scaled default font (Pillow 10+) or fall back to bitmap default."""
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


@app.route('/get-weather-image', methods=['GET'])
def get_weather_image():
    """Generate a 320x100 PNG showing current outdoor weather + OWM icon."""
    try:
        ip = request.args.get('ip', '8.8.8.8')
        location = weather_client.fetch_location_data(ip)
        lat, lon = location['loc'].split(',')
        current = weather_client.fetch_weather_data(lat, lon, current_weather=True)

        temp      = current["main"]["temp"]
        feels     = current["main"]["feels_like"]
        hum       = current["main"]["humidity"]
        desc      = current["weather"][0]["description"].title()
        icon_code = current["weather"][0]["icon"]
        city      = current.get("name", "Unknown")
        wind      = current.get("wind", {}).get("speed", 0)

        img  = Image.new('RGB', (320, 100), color=(8, 8, 20))
        draw = ImageDraw.Draw(img)

        # Accent bar top
        draw.rectangle([(0, 0), (320, 2)], fill=(0, 229, 255))

        # Left panel background card
        draw.rectangle([(0, 2), (158, 100)], fill=(12, 12, 28))

        # City name
        draw.text((8, 5), city[:18], fill=(0, 229, 255), font=_font(11))

        # Big temperature
        draw.text((8, 20), '{:.1f}°C'.format(temp), fill=(255, 171, 0), font=_font(28))

        # Feels like + description
        draw.text((8, 72), 'Feels {:.0f}°C'.format(feels), fill=(90, 90, 120), font=_font(10))
        draw.text((8, 84), desc[:22], fill=(180, 180, 210), font=_font(10))

        # Divider
        draw.line([(160, 4), (160, 96)], fill=(25, 25, 45), width=1)

        # Right stats panel
        draw.text((166, 5),  'Humidity',            fill=(70, 90, 110),  font=_font(10))
        draw.text((166, 18), '{}%'.format(hum),     fill=(68, 138, 255), font=_font(16))
        draw.text((166, 48), 'Wind',                fill=(70, 90, 110),  font=_font(10))
        draw.text((166, 60), '{:.1f} m/s'.format(wind), fill=(140, 140, 170), font=_font(14))

        # Weather icon (top-right corner)
        icon = _fetch_weather_icon(icon_code, (56, 56))
        _paste_icon(img, icon, 258, 6)

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return send_file(buf, mimetype='image/png')
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get-forecast-image', methods=['GET'])
def get_forecast_image():
    """Generate a 320x130 PNG showing 3-day forecast with OWM icons."""
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

        img  = Image.new('RGB', (320, 130), color=(8, 8, 20))
        draw = ImageDraw.Draw(img)
        draw.rectangle([(0, 0), (320, 2)], fill=(0, 229, 255))

        # Fetch all 3 OWM icons in parallel — avoids sequential timeouts
        icon_codes = [fc['weather'][0]['icon'] for fc in forecasts]
        icons = {}
        with ThreadPoolExecutor(max_workers=3) as ex:
            futures = {ex.submit(_fetch_weather_icon, code, (40, 40)): i
                       for i, code in enumerate(icon_codes)}
            for fut in as_completed(futures):
                icons[futures[fut]] = fut.result()

        x_positions = [5, 110, 215]
        for i, fc in enumerate(forecasts):
            x    = x_positions[i]
            date = datetime.strptime(fc['dt_txt'], '%Y-%m-%d %H:%M:%S')

            draw.rectangle([(x, 4), (x + 100, 126)], fill=(12, 12, 28))
            draw.text((x + 4, 6),  date.strftime('%a %d'),                   fill=(0, 229, 255),   font=_font(11))
            _paste_icon(img, icons.get(i), x + 28, 18)
            draw.text((x + 4, 62), '{:.0f}°C'.format(fc['main']['temp']),    fill=(255, 171, 0),   font=_font(16))
            draw.text((x + 4, 82), '{}%'.format(fc['main']['humidity']),      fill=(68, 138, 255),  font=_font(11))
            draw.text((x + 4, 96), fc['weather'][0]['description'][:13],      fill=(150, 150, 180), font=_font(10))
            draw.text((x + 4, 111), '{:.1f}m/s'.format(fc['wind']['speed']), fill=(110, 110, 140), font=_font(10))
            if i < 2:
                draw.line([(x + 103, 4), (x + 103, 126)], fill=(20, 20, 40), width=1)

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return send_file(buf, mimetype='image/png')
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get-history-image', methods=['GET'])
def get_history_image():
    """Generate a 320x200 PNG with a stat header + 24h indoor sensor graph."""
    try:
        hours = int(request.args.get('hours', 24))
        rows  = bq_client.get_historical_data(hours)

        BG_HEX  = '#080814'
        BG_CARD = '#0F0F28'

        if not rows or len(rows) < 2:
            img  = Image.new('RGB', (320, 200), color=(8, 8, 20))
            draw = ImageDraw.Draw(img)
            draw.rectangle([(0, 0), (320, 2)], fill=(0, 229, 255))
            draw.text((80, 95), 'No data available', fill=(100, 100, 130))
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            return send_file(buf, mimetype='image/png')

        df = pd.DataFrame(rows)
        df['measurement_time'] = pd.to_datetime(df['measurement_time'], utc=True)
        df = df.sort_values('measurement_time')
        times = df['measurement_time'].dt.tz_convert('Europe/Zurich')

        latest_temp = df['indoor_temp'].iloc[-1]
        latest_hum  = df['indoor_humidity'].iloc[-1]
        latest_co2  = df['indoor_air_quality'].iloc[-1]

        if   latest_co2 < 600:  co2_label, co2_color = 'EXCELLENT', '#00E676'
        elif latest_co2 < 1000: co2_label, co2_color = 'GOOD',      '#FFEA00'
        elif latest_co2 < 2000: co2_label, co2_color = 'POOR',      '#FFAB00'
        else:                   co2_label, co2_color = 'DANGER',    '#FF1744'

        from matplotlib.gridspec import GridSpec
        fig = plt.figure(figsize=(3.2, 2.0), dpi=100, facecolor=BG_HEX)
        gs  = GridSpec(2, 3, figure=fig, height_ratios=[1, 2.2], hspace=0.08,
                       wspace=0.05, left=0.08, right=0.97, top=0.97, bottom=0.18)

        # ── Stat cards (top row) ────────────────────────────────
        stats = [
            ('INDOOR',  '{:.1f}°C'.format(latest_temp), '#FFAB00'),
            ('HUMIDITY', '{:.0f}%'.format(latest_hum),  '#448AFF'),
            ('CO2',     '{:.0f}p'.format(latest_co2),   co2_color),
        ]
        for col, (label, value, color) in enumerate(stats):
            ax = fig.add_subplot(gs[0, col])
            ax.set_facecolor(BG_CARD)
            ax.set_xlim(0, 1); ax.set_ylim(0, 1)
            ax.axis('off')
            for spine in ax.spines.values():
                spine.set_visible(False)
            ax.axhline(y=0.97, color=color, linewidth=2.5, xmin=0.04, xmax=0.96,
                       solid_capstyle='round')
            ax.text(0.5, 0.62, label,  color='#7777AA', fontsize=5.5,
                    ha='center', va='center', transform=ax.transAxes, fontweight='bold',
                    letterspacing=0.5)
            ax.text(0.5, 0.22, value,  color=color, fontsize=10,
                    ha='center', va='center', transform=ax.transAxes, fontweight='bold')
            if label == 'CO2':
                ax.text(0.5, -0.02, co2_label, color=co2_color, fontsize=4.5,
                        ha='center', va='center', transform=ax.transAxes, fontweight='bold')

        # ── Graph (bottom row) ──────────────────────────────────
        ax1 = fig.add_subplot(gs[1, :])
        ax1.set_facecolor(BG_HEX)
        ax1.plot(times, df['indoor_temp'],     color='#FFAB00', linewidth=1.5, label='Temp °C')
        ax1.plot(times, df['indoor_humidity'], color='#448AFF', linewidth=1.5, label='Hum %')
        ax1.tick_params(colors='#7777AA', labelsize=5.5)
        for spine in ax1.spines.values():
            spine.set_color('#1A1A30')
        ax1.spines['top'].set_visible(False)
        ax1.yaxis.set_tick_params(labelsize=5.5)

        ax2 = ax1.twinx()
        ax2.plot(times, df['indoor_air_quality'], color=co2_color, linewidth=1.2,
                 linestyle='--', label='CO₂ ppm', alpha=0.8)
        ax2.tick_params(colors=co2_color, labelsize=5.5)
        ax2.spines['right'].set_color(co2_color)
        for s in ['top', 'bottom', 'left']:
            ax2.spines[s].set_color('#1A1A30')

        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax1.xaxis.set_major_locator(mdates.HourLocator(interval=4))
        ax1.tick_params(axis='x', rotation=30, labelsize=5.5)
        ax1.grid(axis='y', color='#1A1A30', linewidth=0.5)

        lines1, lbl1 = ax1.get_legend_handles_labels()
        lines2, lbl2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, lbl1 + lbl2, loc='upper right', fontsize=4.5,
                   facecolor='#0A0A1A', edgecolor='#333344', labelcolor='white',
                   framealpha=0.85)

        buf = io.BytesIO()
        fig.savefig(buf, format='PNG', dpi=100, facecolor=BG_HEX)
        plt.close(fig)
        buf.seek(0)

        result_img = Image.open(buf).convert('RGB')
        draw = ImageDraw.Draw(result_img)
        draw.rectangle([(0, 0), (320, 2)], fill=(0, 229, 255))
        draw.rectangle([(0, 197), (320, 200)], fill=(0, 229, 255))

        final_buf = io.BytesIO()
        result_img.save(final_buf, format='PNG')
        final_buf.seek(0)
        return send_file(final_buf, mimetype='image/png')
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
    Recoit un WAV depuis un client (M5Stack ou Streamlit), transcrit
    avec Speech-to-Text, et repond selon le format demande.
 
    Parametre optionnel : ?text_only=true
      - Si oui (utilise par le dashboard Streamlit) :
        Renvoie {"answer": "...", "question": "..."}
      - Si non (utilise par le M5Stack) :
        Renvoie {"type":"image", "transcription":"...", "city":"Tokyo"}
        OU {"type":"text", "transcription":"...", "lines":[["lbl","val"],...]}
    """
    try:
        audio_bytes = request.data
        if not audio_bytes:
            return jsonify({"error": "No audio data received"}), 400
 
        ip = request.args.get('ip', '8.8.8.8')
        text_only = request.args.get('text_only', 'false').lower() == 'true'
 
        # 1. Speech-to-Text
        question = speech_to_text_client.transcribe_audio(audio_bytes)
        if not question:
            sorry = "Sorry, I didn't catch that. Could you please repeat?"
            if text_only:
                return jsonify({"answer": sorry, "question": ""}), 200
            return jsonify({
                "type":"text",
                "transcription":"(could not understand)",
                "lines":[["Status","Please retry"],
                         ["Tip","Speak louder"]]
            }), 200
 
        # 2. Detection ville mentionnee
        city_extract_prompt = (
            'Extract the city name from this question (in any language). '
            'Question: "{}". '
            'Reply with ONLY the city name in English capitalized, or "none". '
            'Examples: '
            '"weather in Tokyo" -> Tokyo, '
            '"quel temps a Paris" -> Paris, '
            '"meteo a Berlin demain" -> Berlin, '
            '"temperature outside" -> none, '
            '"quelle humidite interieure" -> none.'
        ).format(question)
 
        extracted_city = vertex_ai_client.get_weather_description(
            city_extract_prompt,
            "You extract city names. Reply with ONLY the city name or 'none'."
        ).strip()
 
        # 3. Recuperer le contexte meteo + indoor
        location_data = weather_client.fetch_location_data(ip)
        lat, lon = location_data['loc'].split(',')
        local_city = location_data.get('city', 'your location')
        current_weather = weather_client.fetch_weather_data(lat, lon, current_weather=True)
        forecast_data   = weather_client.fetch_weather_data(lat, lon, current_weather=False)
        next_days = forecast_data['list'][:8]
        latest_indoor = bq_client.get_latest_sensor_data()
 
        # 4. Si ville detectee, recuperer sa meteo aussi
        extra_city_context = ""
        city_is_valid = False
        if extracted_city and extracted_city.lower() != "none":
            city_weather = _get_weather_for_city(extracted_city)
            if city_weather and city_weather.get('main'):
                city_is_valid = True
                extra_city_context = "\nWeather for {}: {}".format(
                    extracted_city, city_weather)
 
        # ── BRANCHE STREAMLIT : reponse texte naturelle ──────
        if text_only:
            context = (
                "Local city: {}\n"
                "Current outdoor weather: {}\n"
                "Next 24h forecast: {}\n"
                "Latest indoor sensors: {}{}\n"
                "User question: {}"
            ).format(local_city, current_weather, next_days,
                     latest_indoor, extra_city_context, question)
 
            SYSTEM_INSTRUCTION = (
                "You are a smart home weather assistant. "
                "Answer the user's question based on the provided data. "
                "Be concise (max 80 words), friendly, helpful. "
                "No emojis, no special characters. Always reply in English."
            )
 
            answer = vertex_ai_client.get_weather_description(
                context, SYSTEM_INSTRUCTION)
            return jsonify({"answer": answer, "question": question}), 200
 
        # ── BRANCHE M5STACK : reponse structuree (image ou tableau) ──
 
        # 5a. Si ville valide detectee, on dit au M5Stack de demander l'image
        if city_is_valid:
            return jsonify({
                "type":"image",
                "transcription": question,
                "city": extracted_city
            }), 200
 
        # 5b. Si ville mentionnee mais introuvable, fallback texte
        if extracted_city and extracted_city.lower() != "none":
            return jsonify({
                "type":"text",
                "transcription": question,
                "lines":[["City", extracted_city[:18]],
                         ["Status", "Not found"]]
            }), 200
 
        # 5c. Question generale : reponse tabulaire via Gemini en JSON
        structured_prompt = (
            'User question: "{}"\n'
            'Local city: {}\n'
            'Outdoor weather: {}\n'
            'Next 24h forecast: {}\n'
            'Indoor sensors: {}\n\n'
            'Answer the question using the data above. '
            'Reply ONLY with a JSON array of 3 to 6 [label, value] pairs. '
            'Labels are short (max 12 chars), values are short (max 18 chars). '
            'Example: [["Topic","Indoor temp"],["Now","22.3 C"],["Trend","Stable"]]. '
            'No markdown, no comments, no code fences, just the JSON array.'
        ).format(question, local_city, current_weather, next_days, latest_indoor)
 
        SYSTEM_INSTRUCTION = (
            "You return ONLY a JSON array of [label,value] pairs in English. "
            "Labels and values must be in English, regardless of the question language. "
            "No prose, no markdown fences, just the raw JSON array."
        )
 
        raw_answer = vertex_ai_client.get_weather_description(
            structured_prompt, SYSTEM_INSTRUCTION
        )
 
        # Nettoyer la reponse Gemini (peut contenir des backticks markdown)
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
            lines = [[str(p[0])[:14], str(p[1])[:18]]
                     for p in lines if len(p) >= 2]
            if not lines:
                lines = [["Answer", "No data"]]
        except Exception:
            lines = [["Answer", cleaned[:18] if cleaned else "No data"]]
 
        return jsonify({
            "type":"text",
            "transcription": question,
            "lines": lines[:6]
        }), 200
 
    except Exception as e:
        if request.args.get('text_only', 'false').lower() == 'true':
            return jsonify({"answer": "Error: " + str(e)[:60],
                            "question": ""}), 200
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
 
        img  = Image.new('RGB', (320, 240), color=(8, 8, 20))
        draw = ImageDraw.Draw(img)

        draw.rectangle([(0, 0),   (320, 3)],   fill=(0, 229, 255))
        draw.rectangle([(0, 237), (320, 240)],  fill=(0, 229, 255))

        # Icon top-right
        icon_code = weather_data["weather"][0]["icon"]
        icon = _fetch_weather_icon(icon_code, (72, 72))
        _paste_icon(img, icon, 234, 16, bg_color=(8, 8, 20))

        draw.text((14, 8),  name[:22],                        fill=(0, 229, 255),   font=_font(13))
        draw.text((14, 26), '{:.1f}°C'.format(temp),          fill=(255, 171, 0),   font=_font(38))
        draw.text((14, 80), 'Feels {:.0f}°C'.format(feels),   fill=(100, 100, 130), font=_font(12))
        draw.text((14, 96), desc[:28],                         fill=(200, 200, 230), font=_font(12))

        draw.line([(14, 122), (306, 122)], fill=(30, 30, 50), width=1)

        stats = [
            ('Humidity', '{}%'.format(hum),         (68, 138, 255)),
            ('Wind',     '{:.1f} m/s'.format(wind), (160, 160, 190)),
            ('Pressure', '{} hPa'.format(press),    (180, 180, 210)),
        ]
        for idx, (label, value, color) in enumerate(stats):
            cx = 14 + idx * 102
            draw.rectangle([(cx, 128), (cx + 96, 200)], fill=(12, 12, 30))
            draw.text((cx + 6, 132), label,  fill=(80, 90, 110), font=_font(11))
            draw.text((cx + 6, 148), value,  fill=color,         font=_font(14))

        now_utc = datetime.utcnow().strftime('%H:%M UTC')
        draw.text((14, 210), 'Updated ' + now_utc, fill=(60, 60, 90), font=_font(10))
 
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return send_file(buf, mimetype='image/png')
 
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)