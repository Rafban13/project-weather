# ============================================================
#  Project Weather — M5Stack Core2
#  Dark Minimalist UI — v2
#  Features: WiFi, Dashboard, Forecast, PIR TTS, Q&A, Alerts
# ============================================================

from m5stack_ui import M5Screen, M5Label, M5Img, FONT_MONT_10, FONT_MONT_14, FONT_MONT_34
from m5stack import btnA, btnB, btnC, speaker
import unit
from network import WLAN, STA_IF
import urequests
import utime as time
import socket
import struct
from machine import RTC
import gc

# ── Screen ──────────────────────────────────────────────────
screen = M5Screen()
screen.clean_screen()
screen.set_screen_bg_color(0x0A0A0F)

# ── Sensors ─────────────────────────────────────────────────
env3 = unit.get(unit.ENV3, unit.PORTA)
pir  = unit.get(unit.PIR,  unit.PORTB)
tvoc = unit.get(unit.TVOC, unit.PORTC)

# ── Config ──────────────────────────────────────────────────
FLASK_URL       = "https://weather-service-197991375095.europe-west6.run.app"
DEVICE_ID       = "m5stack-Tesla"
NTP_DELTA       = 3155673600
NTP_QUERY       = b'\x1b' + 47 * b'\0'
NTP_SERVER      = 'ch.pool.ntp.org'
TIMEZONE_OFFSET = 2 * 3600

# Audio recording config
RECORD_SECONDS  = 4       # seconds to record voice question
SAMPLE_RATE     = 16000   # Hz — required by Google Speech-to-Text

try:
    from wifi_config import KNOWN_NETWORKS
except ImportError:
    KNOWN_NETWORKS = {"newyork": "", "iot-unil": "", "public-unil": ""}
NETWORK_NAMES = list(KNOWN_NETWORKS.keys())

wlan = WLAN(STA_IF)
wlan.active(True)
time.sleep(1)

# ── State ────────────────────────────────────────────────────
device_public_ip       = None
current_page           = "wifi"
selected_network_index = 0
last_tts_played        = 0        # timestamp of last PIR-triggered TTS
last_outdoor_temp      = 0
last_outdoor_humidity  = 0
is_recording           = False    # True while recording voice question

# ── Colours ──────────────────────────────────────────────────
C_BG      = 0x0A0A0F
C_ACCENT  = 0x00E5FF   # cyan
C_WARM    = 0xFFAB00   # amber  — temperature
C_COOL    = 0x448AFF   # blue   — humidity
C_GREEN   = 0x00E676   # green  — good air
C_YELLOW  = 0xFFEA00   # yellow — warning
C_RED     = 0xFF1744   # red    — alert
C_DIM     = 0x333344   # very muted
C_MID     = 0x7777AA   # secondary text
C_WHITE   = 0xDDDDFF   # soft white

# ============================================================
#  WIFI PAGE
# ============================================================
wf_title  = M5Label('', x=65,  y=8,   color=C_ACCENT,  font=FONT_MONT_14)
wf_hint   = M5Label('', x=12,  y=28,  color=C_MID,     font=FONT_MONT_10)
wf_line   = M5Label('', x=12,  y=44,  color=C_DIM,     font=FONT_MONT_10)
wf_net0   = M5Label('', x=12,  y=62,  color=C_WHITE,   font=FONT_MONT_14)
wf_net1   = M5Label('', x=12,  y=86,  color=C_WHITE,   font=FONT_MONT_14)
wf_net2   = M5Label('', x=12,  y=110, color=C_WHITE,   font=FONT_MONT_14)
wf_status = M5Label('', x=12,  y=150, color=C_YELLOW,  font=FONT_MONT_10)

# ============================================================
#  DASHBOARD PAGE
# ============================================================
# Top bar
db_time   = M5Label('', x=6,   y=3,   color=C_MID,    font=FONT_MONT_10)
db_status = M5Label('', x=228, y=3,   color=C_GREEN,  font=FONT_MONT_10)

# Indoor — left column
db_in_lbl = M5Label('', x=6,   y=20,  color=C_MID,    font=FONT_MONT_10)
db_temp   = M5Label('', x=6,   y=32,  color=C_WARM,   font=FONT_MONT_34)

# Humidity — right column
db_hm_lbl = M5Label('', x=172, y=20,  color=C_MID,    font=FONT_MONT_10)
db_hum    = M5Label('', x=168, y=32,  color=C_COOL,   font=FONT_MONT_34)
db_hum_alert = M5Label('', x=168, y=78, color=C_RED,  font=FONT_MONT_10)

# CO2 — right column below humidity
db_co2_lbl = M5Label('', x=172, y=90,  color=C_MID,   font=FONT_MONT_10)
db_co2     = M5Label('', x=168, y=102, color=C_GREEN,  font=FONT_MONT_14)
db_co2_tag = M5Label('', x=168, y=118, color=C_GREEN,  font=FONT_MONT_10)

# Divider
db_div    = M5Label('', x=6,   y=120,  color=C_DIM,   font=FONT_MONT_10)

# Weather image (outdoor)
db_wimg   = M5Img("/flash/res/default_current_weather.png", x=0, y=128)

# Bottom hint
db_hint   = M5Label('', x=6,   y=226,  color=C_DIM,   font=FONT_MONT_10)

# ============================================================
#  FORECAST PAGE
# ============================================================
fc_title  = M5Label('', x=85,  y=3,   color=C_ACCENT, font=FONT_MONT_14)
fc_img    = M5Img("/flash/res/default_future_weather.png", x=0, y=22)
fc_hint   = M5Label('', x=6,   y=226,  color=C_DIM,   font=FONT_MONT_10)

# ============================================================
#  Q&A PAGE  (new!)
# ============================================================
qa_title  = M5Label('', x=85,  y=8,   color=C_ACCENT, font=FONT_MONT_14)
qa_line   = M5Label('', x=12,  y=28,  color=C_DIM,    font=FONT_MONT_10)
qa_info   = M5Label('', x=12,  y=50,  color=C_WHITE,  font=FONT_MONT_14)
qa_info2  = M5Label('', x=12,  y=75,  color=C_MID,    font=FONT_MONT_10)
qa_status = M5Label('', x=12,  y=110, color=C_YELLOW, font=FONT_MONT_14)
qa_hint   = M5Label('', x=6,   y=226,  color=C_DIM,   font=FONT_MONT_10)


# ============================================================
#  HELPERS
# ============================================================
def co2_style(co2):
    if co2 < 600:   return C_GREEN,  'EXCELLENT'
    elif co2 < 1000: return C_YELLOW, 'GOOD'
    elif co2 < 2000: return C_WARM,   'POOR'
    else:            return C_RED,    'DANGER'

def sync_ntp():
    try:
        addr = socket.getaddrinfo(NTP_SERVER, 123)[0][-1]
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(10)
        s.sendto(NTP_QUERY, addr)
        msg, _ = s.recvfrom(48)
        s.close()
        ntp_time = struct.unpack('!I', msg[40:44])[0] - NTP_DELTA + TIMEZONE_OFFSET
        lt = time.localtime(ntp_time)
        RTC().datetime((lt[0], lt[1], lt[2], 0, lt[3], lt[4], lt[5], 0))
        return True
    except:
        return False

def fmt_time():
    try:
        t = time.localtime()
        days = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
        return '{} {:02d}.{:02d}  {:02d}:{:02d}'.format(
            days[t[6]], t[2], t[1], t[3], t[4])
    except:
        return ''

# ── Hide helpers ─────────────────────────────────────────────
def hide_wifi():
    wf_title.set_text(''); wf_hint.set_text(''); wf_line.set_text('')
    wf_net0.set_text(''); wf_net1.set_text(''); wf_net2.set_text('')
    wf_status.set_text('')

def hide_dashboard():
    db_time.set_text('');   db_status.set_text('')
    db_in_lbl.set_text(''); db_temp.set_text('')
    db_hm_lbl.set_text(''); db_hum.set_text('')
    db_hum_alert.set_text('')
    db_co2_lbl.set_text(''); db_co2.set_text(''); db_co2_tag.set_text('')
    db_div.set_text('');    db_hint.set_text('')
    db_wimg.set_hidden(True)

def hide_forecast():
    fc_title.set_text(''); fc_hint.set_text('')
    fc_img.set_hidden(True)

def hide_qa():
    qa_title.set_text(''); qa_line.set_text('')
    qa_info.set_text('');  qa_info2.set_text('')
    qa_status.set_text(''); qa_hint.set_text('')

# ============================================================
#  PAGE RENDERERS
# ============================================================
def show_wifi_page():
    global current_page
    current_page = "wifi"
    screen.set_screen_bg_color(0x08080F)
    hide_dashboard(); hide_forecast(); hide_qa()
    wf_title.set_text('//  WiFi Setup')
    wf_hint.set_text('A / C : navigate      B : connect')
    wf_line.set_text('________________________________')
    wf_status.set_text('Select a network')
    _render_networks()

def show_dashboard_page():
    global current_page
    current_page = "dashboard"
    screen.set_screen_bg_color(C_BG)
    hide_wifi(); hide_forecast(); hide_qa()
    db_in_lbl.set_text('INDOOR')
    db_hm_lbl.set_text('HUM')
    db_co2_lbl.set_text('CO2')
    db_div.set_text('____________________________')
    db_wimg.set_hidden(False)
    db_hint.set_text('< WiFi    Q&A    Forecast >')
    db_time.set_text(fmt_time())

def show_forecast_page():
    global current_page
    current_page = "forecast"
    screen.set_screen_bg_color(C_BG)
    hide_wifi(); hide_dashboard(); hide_qa()
    fc_title.set_text('3-DAY FORECAST')
    fc_img.set_hidden(False)
    fc_hint.set_text('< Q&A             WiFi >')
    if wlan.isconnected():
        _fetch_forecast_img()

def show_qa_page():
    global current_page
    current_page = "qa"
    screen.set_screen_bg_color(C_BG)
    hide_wifi(); hide_dashboard(); hide_forecast()
    qa_title.set_text('//  Ask Me')
    qa_line.set_text('________________________________')
    qa_info.set_text('Press B to ask a question')
    qa_info2.set_text('Speak for 4 seconds after the beep')
    qa_status.set_text('')
    qa_hint.set_text('< Dashboard       Forecast >')

# ── Network list ─────────────────────────────────────────────
def _render_networks():
    labels = [wf_net0, wf_net1, wf_net2]
    for i, lbl in enumerate(labels):
        if i < len(NETWORK_NAMES):
            name = NETWORK_NAMES[i]
            if i == selected_network_index:
                lbl.set_text('  >  ' + name)
                lbl.set_text_color(C_ACCENT)
            else:
                lbl.set_text('     ' + name)
                lbl.set_text_color(C_MID)
        else:
            lbl.set_text('')

# ============================================================
#  NETWORK CONNECTION
# ============================================================
def connect_selected():
    global device_public_ip
    ssid     = NETWORK_NAMES[selected_network_index]
    password = KNOWN_NETWORKS[ssid]
    wf_status.set_text('Connecting to {}...'.format(ssid))
    if wlan.isconnected():
        wlan.disconnect(); time.sleep(1)
    wlan.connect(ssid, password)
    t0 = time.time()
    while not wlan.isconnected() and time.time() - t0 < 15:
        time.sleep(1)
    if wlan.isconnected():
        wf_status.set_text('Connected  OK')
        time.sleep(0.5)
        try:
            r = urequests.get('http://api.ipify.org/?format=text')
            device_public_ip = r.text; r.close()
        except:
            pass
        sync_ntp()
        _sync_from_bigquery()   # ← sync last values at startup
        show_dashboard_page()
        _fetch_weather_img()
    else:
        wf_status.set_text('Failed — try again')

# ============================================================
#  BIGQUERY STARTUP SYNC
# ============================================================
def _sync_from_bigquery():
    """At startup, load last known values from BigQuery."""
    global last_outdoor_temp, last_outdoor_humidity
    try:
        r = urequests.get(FLASK_URL + '/sync-from-bigquery')
        if r.status_code == 200:
            d = r.json()
            last_outdoor_temp     = d.get('outdoor_temp', 0)
            last_outdoor_humidity = d.get('outdoor_humidity', 0)
        r.close()
    except:
        pass

# ============================================================
#  DATA FETCH
# ============================================================
def _fetch_weather_img():
    try:
        r = urequests.get(
            FLASK_URL + '/get-weather-image?ip=' + (device_public_ip or '8.8.8.8'))
        if r.status_code == 200:
            with open('/flash/res/current_weather.png', 'wb') as f:
                f.write(r.content)
            r.close()
            db_wimg.set_img_src('/flash/res/current_weather.png')
        else:
            r.close()
    except:
        pass

def _fetch_forecast_img():
    try:
        r = urequests.get(
            FLASK_URL + '/get-forecast-image?ip=' + (device_public_ip or '8.8.8.8'))
        if r.status_code == 200:
            with open('/flash/res/forecast_weather.png', 'wb') as f:
                f.write(r.content)
            r.close()
            fc_img.set_img_src('/flash/res/forecast_weather.png')
        else:
            r.close()
    except:
        pass

def _send_data(temp, hum, co2):
    """Send indoor sensor data to Flask → BigQuery."""
    try:
        payload = {
            'indoor_temp':        temp,
            'indoor_humidity':    hum,
            'indoor_air_quality': co2,
            'outdoor_temp':       last_outdoor_temp,
            'outdoor_humidity':   last_outdoor_humidity,
            'ip_address':         device_public_ip or 'unknown',
            'device_id':          DEVICE_ID
        }
        r = urequests.post(FLASK_URL + '/send-to-bigquery', json=payload)
        ok = r.status_code == 200
        r.close()
        if ok:
            db_status.set_text('Sent')
            db_status.set_text_color(C_GREEN)
        else:
            db_status.set_text('Err')
            db_status.set_text_color(C_RED)
        time.sleep(2)
        db_status.set_text('')
    except:
        db_status.set_text('Err')
        db_status.set_text_color(C_RED)

# ============================================================
#  PIR — WEATHER ANNOUNCEMENT  (max once per hour)
# ============================================================
def _play_weather_tts():
    """Announce weather when motion is detected — max once every 3600s."""
    global last_tts_played
    now = time.time()
    if now - last_tts_played < 3600:   # ← once per hour
        return
    try:
        db_status.set_text('TTS...')
        db_status.set_text_color(C_YELLOW)
        r = urequests.post(
            FLASK_URL + '/generate-current-weather-spoken',
            json={'ip': device_public_ip or '8.8.8.8'}
        )
        if r.status_code == 200:
            with open('/flash/weather.wav', 'wb') as f:
                f.write(r.content)
            r.close()
            speaker.playWAV('/flash/weather.wav', volume=6)
            last_tts_played = now
        else:
            r.close()
        db_status.set_text('')
    except:
        db_status.set_text('TTS err')
        db_status.set_text_color(C_RED)

# ============================================================
#  Q&A — RECORD + ASK
# ============================================================
def _ask_question():
    """Record voice, send to Flask Speech-to-Text + Gemini, play answer."""
    global is_recording
    if not wlan.isconnected():
        qa_status.set_text('No WiFi')
        return
    try:
        is_recording = True
        qa_status.set_text('Recording...')
        qa_status.set_text_color(C_RED)

        # Beep to signal start of recording
        speaker.tone(1000, 200)
        time.sleep(0.1)

        # Record audio from M5Stack built-in microphone
        audio_data = speaker.record(RECORD_SECONDS * SAMPLE_RATE, SAMPLE_RATE)

        qa_status.set_text('Thinking...')
        qa_status.set_text_color(C_YELLOW)

        # Send raw audio bytes to Flask
        r = urequests.post(
            FLASK_URL + '/ask-question?ip=' + (device_public_ip or '8.8.8.8'),
            data=bytes(audio_data),
            headers={'Content-Type': 'application/octet-stream'}
        )
        if r.status_code == 200:
            with open('/flash/answer.wav', 'wb') as f:
                f.write(r.content)
            r.close()
            qa_status.set_text('Playing...')
            qa_status.set_text_color(C_GREEN)
            speaker.playWAV('/flash/answer.wav', volume=6)
            qa_status.set_text('Done  — press B to ask again')
            qa_status.set_text_color(C_MID)
        else:
            r.close()
            qa_status.set_text('Error — try again')
            qa_status.set_text_color(C_RED)
    except Exception as e:
        qa_status.set_text('Err: {}'.format(str(e)[:20]))
        qa_status.set_text_color(C_RED)
    finally:
        is_recording = False

# ============================================================
#  ALERT HELPERS
# ============================================================
def _check_humidity_alert(hum):
    """Show red alert if humidity is below 40%."""
    if hum < 40:
        db_hum.set_text_color(C_RED)
        db_hum_alert.set_text('! LOW HUM')
    else:
        db_hum.set_text_color(C_COOL)
        db_hum_alert.set_text('')

# ============================================================
#  BUTTON CALLBACKS
# ============================================================
def _btn_a():
    global selected_network_index
    if current_page == "wifi":
        selected_network_index = (selected_network_index - 1) % len(NETWORK_NAMES)
        _render_networks()
    elif current_page == "dashboard":
        show_wifi_page()
    elif current_page == "qa":
        show_dashboard_page()
    elif current_page == "forecast":
        show_qa_page()

def _btn_b():
    if current_page == "wifi":
        connect_selected()
    elif current_page == "dashboard":
        show_qa_page()
    elif current_page == "qa":
        _ask_question()          # ← record & ask
    elif current_page == "forecast":
        show_wifi_page()

def _btn_c():
    global selected_network_index
    if current_page == "wifi":
        selected_network_index = (selected_network_index + 1) % len(NETWORK_NAMES)
        _render_networks()
    elif current_page == "dashboard":
        show_forecast_page()
    elif current_page == "qa":
        show_forecast_page()

btnA.wasPressed(_btn_a)
btnB.wasPressed(_btn_b)
btnC.wasPressed(_btn_c)

# ============================================================
#  STARTUP
# ============================================================
show_wifi_page()

if wlan.isconnected():
    wf_status.set_text('Already connected')
    try:
        r = urequests.get('http://api.ipify.org/?format=text')
        device_public_ip = r.text; r.close()
    except:
        pass
    sync_ntp()
    _sync_from_bigquery()    # ← sync last values from BigQuery
    time.sleep(1)
    show_dashboard_page()
    _fetch_weather_img()

# ============================================================
#  MAIN LOOP
# ============================================================
data_last_sent       = time.time() - 250   # send after ~50s
weather_last_checked = time.time() - 115   # fetch image after ~5s
time_last_updated    = time.time() - 55

while True:
    try:
        if current_page == "dashboard":
            # ── Read sensors ─────────────────────────────────
            temp = env3.temperature
            hum  = env3.humidity
            co2  = tvoc.eCO2

            # ── Display indoor values ────────────────────────
            db_temp.set_text('{:.1f}'.format(temp))
            db_hum.set_text('{:.0f}%'.format(hum))

            # ── Humidity alert ───────────────────────────────
            _check_humidity_alert(hum)

            # ── CO2 with colour ──────────────────────────────
            co2_color, co2_tag = co2_style(co2)
            db_co2.set_text('{}ppm'.format(co2))
            db_co2.set_text_color(co2_color)
            db_co2_tag.set_text(co2_tag)
            db_co2_tag.set_text_color(co2_color)

            # ── Clock ────────────────────────────────────────
            now = time.time()
            if now - time_last_updated >= 60:
                db_time.set_text(fmt_time())
                time_last_updated = now

            # ── Network tasks ────────────────────────────────
            if wlan.isconnected():
                # PIR → TTS (once per hour max)
                if pir.state == 1:
                    _play_weather_tts()
                # Send to BigQuery every 5 min
                if now - data_last_sent >= 300:
                    _send_data(temp, hum, co2)
                    data_last_sent = now
                # Refresh weather image every 2 min
                if now - weather_last_checked >= 120:
                    _fetch_weather_img()
                    weather_last_checked = now
            else:
                db_status.set_text('No WiFi')
                db_status.set_text_color(C_RED)

    except Exception as e:
        if current_page == "dashboard":
            db_status.set_text('Err')
            db_status.set_text_color(C_RED)

    time.sleep(1)
    gc.collect()