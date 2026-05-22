# ============================================================
#  Project Weather — M5Stack Core2
#  Dark Minimalist UI — v3
#  Features: WiFi, Dashboard, Forecast, PIR TTS, Q&A,
#            Alerts, RGB LEDs, Speech-to-Text
# ============================================================

from m5stack_ui import M5Screen, M5Label, M5Img, FONT_MONT_10, FONT_MONT_14, FONT_MONT_34
from m5stack import btnA, btnB, btnC, speaker
from m5stack import rgb  # ← RGB LEDs
import unit
import MicrophonePDM as MIC  # ← Microphone
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
last_tts_played        = 0
last_outdoor_temp      = 0
last_outdoor_humidity  = 0
is_recording           = False

# ── Colours (screen) ─────────────────────────────────────────
C_BG      = 0x0A0A0F
C_ACCENT  = 0x00E5FF
C_WARM    = 0xFFAB00
C_COOL    = 0x448AFF
C_GREEN   = 0x00E676
C_YELLOW  = 0xFFEA00
C_RED     = 0xFF1744
C_DIM     = 0x333344
C_MID     = 0x7777AA
C_WHITE   = 0xDDDDFF

# ── LED colours (RGB hex) ─────────────────────────────────────
LED_BLUE   = 0x0000FF   # boot / startup
LED_ORANGE = 0xFF6600   # connecting / loading
LED_GREEN  = 0x00FF00   # success / connected
LED_RED    = 0xFF0000   # error
LED_PURPLE = 0x9900FF   # recording voice
LED_WHITE  = 0xFFFFFF   # TTS speaking
LED_CYAN   = 0x00FFFF   # dashboard idle
LED_OFF    = 0x000000   # off

# ── LED helpers ───────────────────────────────────────────────
def led_set(color, brightness=30):
    """Set all 10 side LEDs to a color."""
    rgb.setColorAll(color)
    rgb.setBrightness(brightness)

def led_off():
    rgb.setColorAll(LED_OFF)

# ============================================================
#  WIFI PAGE
# ============================================================
wf_title  = M5Label('', x=65,  y=8,   color=C_ACCENT, font=FONT_MONT_14)
wf_hint   = M5Label('', x=12,  y=28,  color=C_MID,    font=FONT_MONT_10)
wf_line   = M5Label('', x=12,  y=44,  color=C_DIM,    font=FONT_MONT_10)
wf_net0   = M5Label('', x=12,  y=62,  color=C_WHITE,  font=FONT_MONT_14)
wf_net1   = M5Label('', x=12,  y=86,  color=C_WHITE,  font=FONT_MONT_14)
wf_net2   = M5Label('', x=12,  y=110, color=C_WHITE,  font=FONT_MONT_14)
wf_status = M5Label('', x=12,  y=150, color=C_YELLOW, font=FONT_MONT_10)

# ============================================================
#  DASHBOARD PAGE
# ============================================================
db_time      = M5Label('', x=6,   y=3,   color=C_MID,   font=FONT_MONT_10)
db_status    = M5Label('', x=228, y=3,   color=C_GREEN, font=FONT_MONT_10)
db_in_lbl    = M5Label('', x=6,   y=20,  color=C_MID,   font=FONT_MONT_10)
db_temp      = M5Label('', x=6,   y=32,  color=C_WARM,  font=FONT_MONT_34)
db_hm_lbl    = M5Label('', x=172, y=20,  color=C_MID,   font=FONT_MONT_10)
db_hum       = M5Label('', x=168, y=32,  color=C_COOL,  font=FONT_MONT_34)
db_hum_alert = M5Label('', x=168, y=78,  color=C_RED,   font=FONT_MONT_10)
db_co2_lbl   = M5Label('', x=172, y=90,  color=C_MID,   font=FONT_MONT_10)
db_co2       = M5Label('', x=168, y=102, color=C_GREEN, font=FONT_MONT_14)
db_co2_tag   = M5Label('', x=168, y=118, color=C_GREEN, font=FONT_MONT_10)
db_div       = M5Label('', x=6,   y=120, color=C_DIM,   font=FONT_MONT_10)
db_wimg      = M5Img("/flash/res/default_current_weather.png", x=0, y=128)
db_hint      = M5Label('', x=6,   y=226, color=C_DIM,   font=FONT_MONT_10)

# ============================================================
#  FORECAST PAGE
# ============================================================
fc_title = M5Label('', x=85, y=3,   color=C_ACCENT, font=FONT_MONT_14)
fc_img   = M5Img("/flash/res/default_future_weather.png", x=0, y=22)
fc_hint  = M5Label('', x=6,  y=226, color=C_DIM,    font=FONT_MONT_10)

# ============================================================
#  Q&A PAGE
# ============================================================
qa_title  = M5Label('', x=85, y=8,   color=C_ACCENT, font=FONT_MONT_14)
qa_line   = M5Label('', x=12, y=28,  color=C_DIM,    font=FONT_MONT_10)
qa_info   = M5Label('', x=12, y=50,  color=C_WHITE,  font=FONT_MONT_14)
qa_info2  = M5Label('', x=12, y=75,  color=C_MID,    font=FONT_MONT_14)
qa_status = M5Label('', x=12, y=110, color=C_YELLOW, font=FONT_MONT_14)
qa_hint   = M5Label('', x=6,  y=226, color=C_DIM,    font=FONT_MONT_10)

# ============================================================
#  HELPERS
# ============================================================
def co2_style(co2):
    if co2 < 600:    return C_GREEN,  'EXCELLENT'
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
    led_set(LED_BLUE)
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
    led_set(LED_CYAN, 15)

def show_forecast_page():
    global current_page
    current_page = "forecast"
    screen.set_screen_bg_color(C_BG)
    hide_wifi(); hide_dashboard(); hide_qa()
    fc_title.set_text('3-DAY FORECAST')
    fc_img.set_hidden(False)
    fc_hint.set_text('< Q&A             WiFi >')
    led_set(LED_CYAN, 15)
    if wlan.isconnected():
        _fetch_forecast_img()

def show_qa_page():
    global current_page
    current_page = "qa"
    screen.set_screen_bg_color(C_BG)
    hide_wifi(); hide_dashboard(); hide_forecast()
    qa_title.set_text('//  Ask Me')
    qa_line.set_text('________________________________')
    qa_info.set_text('Press B to record')
    qa_info2.set_text('Speak clearly for 4 seconds')
    qa_status.set_text('Ready !')
    qa_status.set_text_color(C_GREEN)
    qa_hint.set_text('< Dashboard       Forecast >')
    led_set(LED_CYAN, 15)

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
    led_set(LED_ORANGE)  # ← orange pendant connexion
    if wlan.isconnected():
        wlan.disconnect(); time.sleep(1)
    wlan.connect(ssid, password)
    t0 = time.time()
    while not wlan.isconnected() and time.time() - t0 < 15:
        time.sleep(1)
    if wlan.isconnected():
        led_set(LED_GREEN)  # ← vert = connecté
        wf_status.set_text('Connected  OK')
        time.sleep(0.5)
        try:
            r = urequests.get('http://api.ipify.org/?format=text')
            device_public_ip = r.text; r.close()
        except:
            pass
        sync_ntp()
        _sync_from_bigquery()
        show_dashboard_page()
        _fetch_weather_img()
    else:
        led_set(LED_RED)  # ← rouge = échec
        wf_status.set_text('Failed — try again')

# ============================================================
#  BIGQUERY STARTUP SYNC
# ============================================================
def _sync_from_bigquery():
    """At startup, load last known values from BigQuery."""
    global last_outdoor_temp, last_outdoor_humidity
    try:
        led_set(LED_ORANGE)  # ← orange pendant sync
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
        led_set(LED_ORANGE, 10)  # ← orange pendant chargement
        r = urequests.get(
            FLASK_URL + '/get-weather-image?ip=' + (device_public_ip or '8.8.8.8'))
        if r.status_code == 200:
            with open('/flash/res/current_weather.png', 'wb') as f:
                f.write(r.content)
            r.close()
            db_wimg.set_img_src('/flash/res/current_weather.png')
        else:
            r.close()
        led_set(LED_CYAN, 15)  # ← retour cyan
    except:
        led_set(LED_CYAN, 15)

def _fetch_forecast_img():
    try:
        led_set(LED_ORANGE, 10)
        r = urequests.get(
            FLASK_URL + '/get-forecast-image?ip=' + (device_public_ip or '8.8.8.8'))
        if r.status_code == 200:
            with open('/flash/res/forecast_weather.png', 'wb') as f:
                f.write(r.content)
            r.close()
            fc_img.set_img_src('/flash/res/forecast_weather.png')
        else:
            r.close()
        led_set(LED_CYAN, 15)
    except:
        led_set(LED_CYAN, 15)

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
        led_set(LED_ORANGE, 10)
        r = urequests.post(FLASK_URL + '/send-to-bigquery', json=payload)
        ok = r.status_code == 200
        r.close()
        if ok:
            led_set(LED_GREEN, 20)
            db_status.set_text('Sent')
            db_status.set_text_color(C_GREEN)
        else:
            led_set(LED_RED)
            db_status.set_text('Err')
            db_status.set_text_color(C_RED)
        time.sleep(2)
        db_status.set_text('')
        led_set(LED_CYAN, 15)
    except:
        led_set(LED_RED)
        db_status.set_text('Err')
        db_status.set_text_color(C_RED)
        time.sleep(2)
        led_set(LED_CYAN, 15)

# ============================================================
#  PIR — WEATHER ANNOUNCEMENT  (max once per hour)
# ============================================================
def _play_weather_tts():
    """Announce weather when motion detected — max once every 3600s."""
    global last_tts_played
    now = time.time()
    if now - last_tts_played < 3600:
        return
    try:
        led_set(LED_WHITE)  # ← blanc = TTS en cours
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
        led_set(LED_CYAN, 15)
    except:
        db_status.set_text('TTS err')
        db_status.set_text_color(C_RED)
        led_set(LED_RED)
        time.sleep(2)
        led_set(LED_CYAN, 15)

# ============================================================
#  Q&A — RECORD + ASK
# ============================================================
def _ask_question():
    # Nettoyer le micro au cas où il serait encore actif
    try:
     MIC.deinit(1000)
    except:
        pass
    gc.collect()
    
    global is_recording
    if not wlan.isconnected():
        qa_status.set_text('No WiFi')
        qa_status.set_text_color(C_RED)
        led_set(LED_RED)
        time.sleep(2)
        led_set(LED_CYAN, 15)
        return
    try:
        is_recording = True

        # ── Countdown ────────────────────────────────────────
        qa_status.set_text('Recording in 2 seconds...')
        qa_status.set_text_color(C_YELLOW)
        led_set(LED_ORANGE)
        time.sleep(2)

        # ── Recording + progress bar ─────────────────────────
        qa_status.set_text('Recording...')
        qa_status.set_text_color(C_RED)
        led_set(LED_PURPLE)

        gc.collect()
        MIC.begin(pin_ws=0, pin_data=34, sample_rate_hz=16000,
                  buffer_length_ms=1000, block_length_ms=100)
        MIC.recordStart(open('/flash/question.wav', 'wb'), 2000)  # ← 2 secondes

        # Barre de progression — 2 secondes
        bar_full = 20
        for i in range(bar_full, -1, -1):
            filled = '|' * i
            empty  = ' ' * (bar_full - i)
            qa_info2.set_text('[{}{}]'.format(filled, empty))
            time.sleep_ms(100)  # ← 20 x 100ms = 2 secondes exactement

        MIC.waitRecordDone(6000)
        MIC.deinit(10000)
        gc.collect()

        # ── Sending ──────────────────────────────────────────
        qa_info2.set_text('')
        qa_status.set_text('Processing...')
        qa_status.set_text_color(C_YELLOW)
        led_set(LED_ORANGE)

        with open('/flash/question.wav', 'rb') as f:
            wav_data = f.read()

        r = urequests.post(
            FLASK_URL + '/ask-question?ip=' + (device_public_ip or '8.8.8.8'),
            data=wav_data,
            headers={'Content-Type': 'audio/wav'}
        )
        del wav_data
        gc.collect()

        if r.status_code == 200:
            with open('/flash/answer.wav', 'wb') as f:
                f.write(r.content)
            r.close()
            del r
            gc.collect()
            qa_status.set_text('Playing...')
            qa_status.set_text_color(C_GREEN)
            led_set(LED_WHITE)
            speaker.playWAV('/flash/answer.wav', volume=6)
            qa_status.set_text('Press B to ask again')
            qa_status.set_text_color(C_MID)
            led_set(LED_CYAN, 15)
        else:
            r.close()
            qa_status.set_text("I didn't catch that, retry")
            qa_status.set_text_color(C_RED)
            led_set(LED_RED)
            time.sleep(2)
            led_set(LED_CYAN, 15)

    except Exception as e:
        qa_status.set_text('Err: {}'.format(str(e)[:20]))
        qa_status.set_text_color(C_RED)
        led_set(LED_RED)
        time.sleep(2)
        led_set(LED_CYAN, 15)
    finally:
        is_recording = False
        gc.collect()
# ============================================================
#  ALERT HELPERS
# ============================================================
def _check_humidity_alert(hum):
    """Red alert if humidity below 40%."""
    if hum < 40:
        db_hum.set_text_color(C_RED)
        db_hum_alert.set_text('! LOW HUM')
        led_set(LED_RED)  # ← rouge = alerte
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
        _ask_question()
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
#  STARTUP  — LEDs bleues au démarrage
# ============================================================
led_set(LED_BLUE)  # ← bleu = démarrage
show_wifi_page()

if wlan.isconnected():
    led_set(LED_ORANGE)  # ← orange = reconnexion
    wf_status.set_text('Already connected')
    try:
        r = urequests.get('http://api.ipify.org/?format=text')
        device_public_ip = r.text; r.close()
    except:
        pass
    sync_ntp()
    _sync_from_bigquery()
    time.sleep(1)
    show_dashboard_page()
    _fetch_weather_img()

# ============================================================
#  MAIN LOOP
# ============================================================
data_last_sent       = time.time() - 250
weather_last_checked = time.time() - 115
time_last_updated    = time.time() - 55

while True:
    try:
        if current_page == "dashboard":
            temp = env3.temperature
            hum  = env3.humidity
            co2  = tvoc.eCO2

            db_temp.set_text('{:.1f}'.format(temp))
            db_hum.set_text('{:.0f}%'.format(hum))

            # ── Humidity alert ───────────────────────────────
            _check_humidity_alert(hum)

            # ── CO2 alert ────────────────────────────────────
            co2_color, co2_tag = co2_style(co2)
            db_co2.set_text('{}ppm'.format(co2))
            db_co2.set_text_color(co2_color)
            db_co2_tag.set_text(co2_tag)
            db_co2_tag.set_text_color(co2_color)
            if co2 >= 2000:
                led_set(LED_RED)  # ← rouge = air dangereux

            # ── Clock ────────────────────────────────────────
            now = time.time()
            if now - time_last_updated >= 60:
                db_time.set_text(fmt_time())
                time_last_updated = now

            # ── Network tasks ────────────────────────────────
            if wlan.isconnected():
                if pir.state == 1:
                    _play_weather_tts()
                if now - data_last_sent >= 300:
                    _send_data(temp, hum, co2)
                    data_last_sent = now
                if now - weather_last_checked >= 120:
                    _fetch_weather_img()
                    weather_last_checked = now
            else:
                db_status.set_text('No WiFi')
                db_status.set_text_color(C_RED)
                led_set(LED_RED)

    except Exception as e:
        if current_page == "dashboard":
            db_status.set_text('Err')
            db_status.set_text_color(C_RED)
            led_set(LED_RED)

    time.sleep(1)
    gc.collect()