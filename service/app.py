import os
import json
import math
import requests
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
#  WEATHER JSON (pour Streamlit — même géoloc que le M5Stack)
# ─────────────────────────────────────────────────────────────

@app.route('/get-weather-json', methods=['GET'])
def get_weather_json():
    """Current weather as JSON via IP geolocation — same source as M5Stack."""
    try:
        ip = request.args.get('ip', '8.8.8.8')
        location = weather_client.fetch_location_data(ip)
        lat, lon = location['loc'].split(',')
        data = weather_client.fetch_weather_data(lat, lon, current_weather=True)
        return jsonify({
            'city':        data['name'],
            'temp':        data['main']['temp'],
            'feels_like':  data['main']['feels_like'],
            'humidity':    data['main']['humidity'],
            'description': data['weather'][0]['description'].capitalize(),
            'icon':        data['weather'][0]['icon'],
            'wind_speed':  data['wind']['speed'],
            'pressure':    data['main']['pressure'],
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/get-forecast-json', methods=['GET'])
def get_forecast_json():
    """3-slot forecast as JSON (24h/48h/72h) — identical data points as /get-forecast-image."""
    try:
        ip = request.args.get('ip', '8.8.8.8')
        location = weather_client.fetch_location_data(ip)
        lat, lon = location['loc'].split(',')
        raw = weather_client.fetch_weather_data(lat, lon, current_weather=False)
        slots = [
            (raw['list'][8],  '24h'),
            (raw['list'][16], '48h'),
            (raw['list'][24], '72h'),
        ]
        result = []
        for fc, label in slots:
            result.append({
                'label':       label,
                'date':        fc['dt_txt'].split(' ')[0],
                'temp':        fc['main']['temp'],
                'humidity':    fc['main']['humidity'],
                'description': fc['weather'][0]['description'].capitalize(),
                'icon':        fc['weather'][0]['icon'],
            })
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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

def _draw_weather_icon(icon_code, size):
    """Draw a weather icon using Pillow shapes — no network call, works on dark bg."""
    w, h   = size
    img    = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d      = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2
    grp    = icon_code[:2]
    day    = not icon_code.endswith('n')

    SUN   = (255, 210,  40, 255)
    MOON  = (210, 220, 255, 255)
    CLOUD = (175, 190, 220, 255)
    RAIN  = ( 80, 140, 255, 230)
    SNOW  = (200, 225, 255, 230)
    BOLT  = (255, 230,  50, 255)
    FOG   = (160, 165, 190, 160)

    def sun(scx, scy, r, col=SUN):
        d.ellipse([scx-r, scy-r, scx+r, scy+r], fill=col)
        rl = max(3, r // 2)
        for a in range(0, 360, 45):
            rd = math.radians(a)
            x1 = scx + int((r + 2) * math.cos(rd))
            y1 = scy + int((r + 2) * math.sin(rd))
            x2 = scx + int((r + 2 + rl) * math.cos(rd))
            y2 = scy + int((r + 2 + rl) * math.sin(rd))
            d.line([x1, y1, x2, y2], fill=col, width=max(2, w // 22))

    def cloud(ccx, ccy, r, col=CLOUD):
        rh = r * 45 // 100
        d.ellipse([ccx-r,               ccy-rh,        ccx+r,            ccy+rh       ], fill=col)
        r2 = r * 50 // 100
        d.ellipse([ccx-r*55//100-r2//2, ccy-rh-r2//3,  ccx-r*55//100+r2, ccy+rh//2   ], fill=col)
        r3 = r * 58 // 100
        d.ellipse([ccx-r//5,            ccy-rh-r3*2//3, ccx+r*7//10,     ccy+rh//4   ], fill=col)

    if grp == '01':
        if day:
            sun(cx, cy, w * 28 // 100)
        else:
            r = w * 28 // 100
            d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=MOON)
            d.ellipse([cx-r//3, cy-r, cx+r+r//2, cy+r], fill=(0, 0, 0, 0))

    elif grp == '02':
        if day:
            sun(cx - w//5, cy - h//4, w // 5)
        else:
            rn = w // 5
            d.ellipse([cx-w//5-rn, cy-h//4-rn, cx-w//5+rn, cy-h//4+rn], fill=MOON)
        cloud(cx + w//10, cy + h//8, w * 30 // 100)

    elif grp == '03':
        cloud(cx, cy, w * 38 // 100)

    elif grp == '04':
        cloud(cx - w//10, cy - h//10, w * 38 // 100, (130, 145, 175, 255))
        cloud(cx + w//8,  cy + h//8,  w * 32 // 100)

    elif grp in ('09', '10'):
        cloud(cx, cy - h//8, w * 36 // 100, (120, 130, 160, 255))
        for dx in [-w//4, -w//10, w//10, w//4]:
            d.line([cx+dx, cy+h//4, cx+dx-3, cy*3//2],
                   fill=RAIN, width=max(2, w // 24))

    elif grp == '11':
        cloud(cx, cy - h//8, w * 36 // 100, (95, 100, 135, 255))
        pts = [(cx+4, cy+h//6), (cx-6, cy+h//3), (cx+2, cy+h//3),
               (cx-8, cy*3//2), (cx+10, cy*5//12), (cx+2, cy*5//12)]
        d.polygon(pts, fill=BOLT)

    elif grp == '13':
        cloud(cx, cy - h//8, w * 36 // 100, (185, 200, 225, 255))
        sr = max(2, w // 16)
        for dx, dy in [(-w//4, 0), (0, 0), (w//4, 0), (-w//8, h//7), (w//8, h//7)]:
            d.ellipse([cx+dx-sr, cy+h//3+dy-sr, cx+dx+sr, cy+h//3+dy+sr], fill=SNOW)

    elif grp == '50':
        for i, fy in enumerate(range(cy - h//5, cy + h//3, max(1, h // 7))):
            fw = w * 65 // 100 - i * 5
            d.ellipse([cx-fw//2, fy-max(2, h//28), cx+fw//2, fy+max(2, h//28)], fill=FOG)

    else:
        sun(cx, cy, w * 28 // 100)

    return img


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

        BG = (10, 10, 15)   # same as M5Stack screen background
        img  = Image.new('RGB', (320, 100), color=BG)
        draw = ImageDraw.Draw(img)

        # Top cyan accent line only — no card fill, blends with screen
        draw.rectangle([(0, 0), (320, 2)], fill=(0, 229, 255))

        # City name
        draw.text((8, 5),  city[:18],                      fill=(0, 229, 255),   font=_font(11))
        draw.text((8, 20), '{:.1f}°C'.format(temp),        fill=(255, 171, 0),   font=_font(28))
        draw.text((8, 72), 'Feels {:.0f}°C'.format(feels), fill=(70, 70, 100),   font=_font(10))
        draw.text((8, 84), desc[:22],                       fill=(160, 160, 200), font=_font(10))

        # Subtle vertical separator
        draw.line([(158, 4), (158, 96)], fill=(22, 22, 38), width=1)

        # Right side stats
        draw.text((164, 5),  'Humidity',                   fill=(55, 75, 100),   font=_font(10))
        draw.text((164, 18), '{}%'.format(hum),            fill=(68, 138, 255),  font=_font(16))
        draw.text((164, 48), 'Wind',                        fill=(55, 75, 100),   font=_font(10))
        draw.text((164, 60), '{:.1f} m/s'.format(wind),    fill=(120, 120, 160), font=_font(14))

        # Weather icon
        icon = _draw_weather_icon(icon_code, (56, 56))
        _paste_icon(img, icon, 258, 6, bg_color=BG)

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return send_file(buf, mimetype='image/png')
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get-forecast-image', methods=['GET'])
def get_forecast_image():
    """Generate 320x120 PNG with 24h/48h/72h columns matching the placeholder design."""
    try:
        ip = request.args.get('ip', '8.8.8.8')
        location = weather_client.fetch_location_data(ip)
        lat, lon = location['loc'].split(',')
        forecast_data = weather_client.fetch_weather_data(lat, lon, current_weather=False)

        # 3h slots: index 8=24h, 16=48h, 24=72h
        forecasts = [
            forecast_data['list'][8],
            forecast_data['list'][16],
            forecast_data['list'][24],
        ]
        col_labels = ['24h', '48h', '72h']

        W, H = 320, 120
        BG   = (8, 8, 20)

        img  = Image.new('RGB', (W, H), color=BG)
        draw = ImageDraw.Draw(img)
        draw.rectangle([(0, 0), (W, 2)], fill=(0, 229, 255))

        # Draw icons locally — no network needed
        icons = {i: _draw_weather_icon(fc['weather'][0]['icon'], (52, 52))
                 for i, fc in enumerate(forecasts)}

        col_w = W // 3  # 106 px per column

        for i, (fc, label) in enumerate(zip(forecasts, col_labels)):
            x    = i * col_w
            temp = fc['main']['temp']
            hum  = fc['main']['humidity']

            # "24h" / "48h" / "72h" in orange
            draw.text((x + 6, 6), label, fill=(255, 171, 0), font=_font(14))

            # "22°C | 45%" in dim grey-blue
            draw.text((x + 6, 28), '{:.0f}°C | {}%'.format(temp, hum),
                      fill=(160, 160, 200), font=_font(11))

            # Icon centered horizontally in column
            icon_x = x + (col_w - 52) // 2
            _paste_icon(img, icons.get(i), icon_x, 48, bg_color=BG)

            # Thin vertical separator
            if i < 2:
                draw.line([(x + col_w, 4), (x + col_w, H - 4)],
                          fill=(25, 25, 45), width=1)

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return send_file(buf, mimetype='image/png')
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get-history-image', methods=['GET'])
def get_history_image():
    """Generate a 320x200 PNG: 3 stat cards + 3 sparklines (Pillow only, ~8 KB)."""
    try:
        hours = int(request.args.get('hours', 24))
        rows  = bq_client.get_historical_data(hours)

        W, H   = 320, 200
        BG     = (8,  8,  20)
        CARD   = (12, 12, 28)
        ACCENT = (0, 229, 255)

        img  = Image.new('RGB', (W, H), BG)
        draw = ImageDraw.Draw(img)
        draw.rectangle([(0, 0), (W, 2)],      fill=ACCENT)
        draw.rectangle([(0, H-3), (W, H)],    fill=ACCENT)

        if not rows or len(rows) < 2:
            draw.text((60, 90), 'No history data yet', fill=(100, 100, 130), font=_font(13))
            buf = io.BytesIO()
            img.save(buf, format='PNG', optimize=True)
            buf.seek(0)
            return send_file(buf, mimetype='image/png')

        temps = [float(r.get('indoor_temp',        0)) for r in rows]
        hums  = [float(r.get('indoor_humidity',    0)) for r in rows]
        co2s  = [float(r.get('indoor_air_quality', 0)) for r in rows]

        latest_co2 = co2s[-1]
        if   latest_co2 < 600:  co2_col = (0, 230, 118)
        elif latest_co2 < 1000: co2_col = (255, 234, 0)
        elif latest_co2 < 2000: co2_col = (255, 171, 0)
        else:                   co2_col = (255, 23,  68)

        # ── Stat cards (y 3–43) ─────────────────────────────────
        cw = W // 3
        cards = [
            ('INDOOR',   '{:.1f}°C'.format(temps[-1]), (255, 171, 0)),
            ('HUMIDITY', '{:.0f}%'.format(hums[-1]),   (68, 138, 255)),
            ('CO2',      '{:.0f}ppm'.format(co2s[-1]), co2_col),
        ]
        for i, (label, value, color) in enumerate(cards):
            x0 = i * cw + 1
            draw.rectangle([(x0, 3), (x0 + cw - 2, 43)], fill=CARD)
            draw.rectangle([(x0, 3), (x0 + cw - 2, 5)],  fill=color)
            draw.text((x0 + 5, 8),  label, fill=(90, 90, 130), font=_font(9))
            draw.text((x0 + 5, 20), value, fill=color,         font=_font(14))

        # ── Sparkline helper ────────────────────────────────────
        LPAD = 28
        CW   = W - LPAD - 4

        def sparkline(values, y0, ch, color, row_label):
            draw.rectangle([(LPAD, y0), (LPAD + CW, y0 + ch)], fill=CARD)
            vmin, vmax = min(values), max(values)
            span = max(vmax - vmin, 0.01)
            n    = len(values)
            pts  = []
            for idx, v in enumerate(values):
                x = LPAD + int(idx * CW / (n - 1))
                y = y0 + ch - 2 - int((v - vmin) / span * (ch - 4))
                pts.append((x, y))
            if len(pts) > 1:
                draw.line(pts, fill=color, width=2)
            if pts:
                lx, ly = pts[-1]
                draw.ellipse([lx-3, ly-3, lx+3, ly+3], fill=color)
            draw.text((0, y0),          '{:.0f}'.format(vmax), fill=color, font=_font(8))
            draw.text((0, y0+ch-9),     '{:.0f}'.format(vmin), fill=color, font=_font(8))
            draw.text((LPAD+2, y0+1),   row_label,             fill=color, font=_font(8))

        sparkline(temps, 48,  40, (255, 171, 0),  '°C')
        sparkline(hums,  93,  40, (68, 138, 255), 'H%')
        sparkline(co2s,  138, 40, co2_col,        'CO2')

        buf = io.BytesIO()
        img.save(buf, format='PNG', optimize=True)
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


@app.route('/tts-text', methods=['POST'])
def tts_text():
    """Convert any text to speech and return a WAV file — used to read Q&A answers aloud."""
    try:
        data = request.get_json()
        text = data.get('text', '')
        if not text:
            return jsonify({"error": "text is required"}), 400
        audio = text_to_speech_client.generate_speech(text[:500])
        temp_file = os.path.join(TMP_DIR, 'answer_output.wav')
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

        # Build 5-day daily forecast summary (more useful than raw 3h entries)
        daily = {}
        for entry in forecast_data['list']:
            day = entry['dt_txt'][:10]
            if day not in daily:
                daily[day] = {'temps': [], 'conds': [], 'wind': []}
            daily[day]['temps'].append(entry['main']['temp'])
            daily[day]['conds'].append(entry['weather'][0]['description'])
            daily[day]['wind'].append(entry['wind']['speed'])
        forecast_lines = []
        for day, d in sorted(daily.items())[:5]:
            mid_cond = d['conds'][len(d['conds']) // 2]
            forecast_lines.append(
                '{}: avg {:.0f}C (min {:.0f} max {:.0f}), {}, wind {:.1f}m/s'.format(
                    day,
                    sum(d['temps']) / len(d['temps']),
                    min(d['temps']), max(d['temps']),
                    mid_cond,
                    sum(d['wind']) / len(d['wind'])
                )
            )
        forecast_5d = '\n'.join(forecast_lines)

        # Last 48h indoor history for "yesterday" indoor questions
        history_rows = bq_client.get_historical_data(hours=48)
        if history_rows:
            indoor_history = 'Last 48h indoor (newest last):\n' + '\n'.join(
                '  {}: {:.1f}C, {:.0f}% hum, {:.0f}ppm CO2'.format(
                    str(r.get('measurement_time', ''))[:16],
                    float(r.get('indoor_temp', 0)),
                    float(r.get('indoor_humidity', 0)),
                    float(r.get('indoor_air_quality', 0))
                )
                for r in history_rows[-8:]
            )
        else:
            indoor_history = 'No indoor history available'

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
                "5-day forecast:\n{}\n"
                "Indoor history (48h):\n{}\n"
                "Latest indoor sensors: {}{}\n"
                "User question: {}"
            ).format(local_city, current_weather, forecast_5d,
                     indoor_history, latest_indoor, extra_city_context, question)
 
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
 
        # 5a. Si ville valide detectee, on dit au M5Stack de demander l'image + phrase parlée
        if city_is_valid:
            temp  = city_weather['main']['temp']
            hum   = city_weather['main']['humidity']
            desc  = city_weather['weather'][0]['description'].capitalize()
            speech_text = (
                "In {city}, it is {temp:.0f} degrees. {desc}. Humidity is {hum} percent."
            ).format(city=extracted_city.capitalize(), temp=temp, desc=desc, hum=hum)
            return jsonify({
                "type":          "image",
                "transcription":  question,
                "city":           extracted_city,
                "speech_text":    speech_text,
            }), 200
 
        # 5b. Si ville mentionnee mais introuvable, fallback texte
        if extracted_city and extracted_city.lower() != "none":
            return jsonify({
                "type":"text",
                "transcription": question,
                "lines":[["City", extracted_city[:18]],
                         ["Status", "Not found"]]
            }), 200
 
        # 5c. Question generale : reponse tabulaire + phrase parlée via Gemini
        structured_prompt = (
            'User question: "{}"\n'
            'Local city: {}\n'
            'Outdoor weather: {}\n'
            '5-day forecast:\n{}\n'
            'Indoor history (48h):\n{}\n'
            'Indoor sensors: {}\n\n'
            'Answer the question using the data above. '
            'Reply ONLY with a JSON object with two fields:\n'
            '  "lines": array of 3 to 6 [label, value] pairs (labels max 12 chars, values max 18 chars)\n'
            '  "speech": a natural spoken English sentence, max 25 words, directly answering the question\n'
            'Example: {{"lines":[["Topic","Indoor temp"],["Now","22.3 C"],["Trend","Stable"]],"speech":"The indoor temperature is 22 degrees and has been stable all morning."}}\n'
            'No markdown, no code fences, just the raw JSON object.'
        ).format(question, local_city, current_weather, forecast_5d,
                 indoor_history, latest_indoor)

        SYSTEM_INSTRUCTION = (
            "You return ONLY a JSON object with 'lines' (English label/value pairs) "
            "and 'speech' (natural English sentence). No markdown, no prose outside JSON."
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

        speech_text = ""
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                raw_lines  = parsed.get('lines', [])
                speech_text = parsed.get('speech', '')[:400]
            elif isinstance(parsed, list):
                raw_lines = parsed   # backwards compat si Gemini renvoie encore un tableau
            else:
                raise ValueError("Unexpected format")
            lines = [[str(p[0])[:14], str(p[1])[:18]]
                     for p in raw_lines if len(p) >= 2]
            if not lines:
                lines = [["Answer", "No data"]]
        except Exception:
            lines = [["Answer", cleaned[:18] if cleaned else "No data"]]

        return jsonify({
            "type":        "text",
            "transcription": question,
            "lines":       lines[:6],
            "speech_text": speech_text,
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
        icon = _draw_weather_icon(icon_code, (72, 72))
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