# ============================================================
#  Project Weather - M5Stack Core2 (VITESSE ET STABILITÉ)
# ============================================================

from m5stack_ui import M5Screen, M5Label, M5Img, FONT_MONT_10, FONT_MONT_14, FONT_MONT_34
from m5stack import btnA, btnB, btnC, speaker
from m5stack import rgb
try:
    from m5stack import power as _power_module
    HAS_POWER = True
except Exception:
    try:
        from m5stack import axp as _power_module
        HAS_POWER = True
    except Exception:
        HAS_POWER = False
import unit
import MicrophonePDM as MIC
import uos
import ujson
from network import WLAN, STA_IF
import urequests
import utime as time
import socket
import struct
from machine import RTC
import gc

# INITIALISATION DE L'ÉCRAN
screen = M5Screen()
screen.clean_screen()
screen.set_screen_bg_color(0x0A0A0F)

env3 = unit.get(unit.ENV3, unit.PORTA)
pir  = unit.get(unit.PIR,  unit.PORTB)
tvoc = unit.get(unit.TVOC, unit.PORTC)

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

device_public_ip       = None
current_page           = "wifi"
_prev_page             = "dashboard"
selected_network_index = 0
last_tts_played        = 0
last_outdoor_temp      = 0
last_outdoor_humidity  = 0
is_recording           = False

# Variable pour suivre l'activation du micro
mic_initialized        = False 

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

LED_BLUE   = 0x0000FF
LED_ORANGE = 0xFF6600
LED_GREEN  = 0x00FF00
LED_RED    = 0xFF0000
LED_PURPLE = 0x9900FF
LED_WHITE  = 0xFFFFFF
LED_CYAN   = 0x00FFFF
LED_OFF    = 0x000000


def led_set(color, brightness=30):
    rgb.setColorAll(color)
    rgb.setBrightness(brightness)


def led_off():
    rgb.setColorAll(LED_OFF)


# ── Labels page WiFi ────────────────────────────────────────
wf_title  = M5Label('', x=65,  y=8,   color=C_ACCENT, font=FONT_MONT_14)
wf_hint   = M5Label('', x=12,  y=28,  color=C_MID,    font=FONT_MONT_10)
wf_line   = M5Label('', x=12,  y=44,  color=C_DIM,    font=FONT_MONT_10)
wf_net0   = M5Label('', x=12,  y=62,  color=C_WHITE,  font=FONT_MONT_14)
wf_net1   = M5Label('', x=12,  y=86,  color=C_WHITE,  font=FONT_MONT_14)
wf_net2   = M5Label('', x=12,  y=110, color=C_WHITE,  font=FONT_MONT_14)
wf_status = M5Label('', x=12,  y=150, color=C_YELLOW, font=FONT_MONT_10)

# ── Labels page Dashboard ───────────────────────────────────
db_time      = M5Label('', x=6,   y=3,   color=C_MID,   font=FONT_MONT_10)
db_clock     = M5Label('', x=88,  y=3,   color=C_WHITE, font=FONT_MONT_10)
db_status    = M5Label('', x=186, y=3,   color=C_GREEN, font=FONT_MONT_10)
# Persistent icon images — visible on ALL pages, never hidden by hide_*
sb_wifi      = M5Img("/flash/res/wifi_off.png", x=236, y=4)
sb_bat       = M5Img("/flash/res/bat_unk.png",  x=262, y=4)
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

# ── Labels page Forecast ────────────────────────────────────
fc_title = M5Label('', x=85, y=3,   color=C_ACCENT, font=FONT_MONT_14)
fc_img   = M5Img("/flash/res/default_future_weather.png", x=0, y=22)

# ── Labels page History ──────────────────────────────────────
hist_title = M5Label('', x=55, y=3,   color=C_ACCENT, font=FONT_MONT_14)
hist_img   = M5Img("/flash/res/default_future_weather.png", x=0, y=22)

# ── Labels page Q&A ─────────────────────────────────────────
qa_title  = M5Label('', x=85, y=8,   color=C_ACCENT, font=FONT_MONT_14)
qa_line   = M5Label('', x=12, y=28,  color=C_DIM,    font=FONT_MONT_10)
qa_info   = M5Label('', x=12, y=50,  color=C_WHITE,  font=FONT_MONT_14)
qa_info2  = M5Label('', x=12, y=75,  color=C_MID,    font=FONT_MONT_14)
qa_status = M5Label('', x=12, y=110, color=C_YELLOW, font=FONT_MONT_14)

# ── Labels page Reponse ───────────────────
ans_title    = M5Label('', x=12, y=8,   color=C_ACCENT, font=FONT_MONT_14)
ans_question = M5Label('', x=12, y=28,  color=C_MID,    font=FONT_MONT_10)
ans_line     = M5Label('', x=12, y=44,  color=C_DIM,    font=FONT_MONT_10)
ans_lbl_0 = M5Label('', x=12,  y=60,  color=C_MID,   font=FONT_MONT_14)
ans_val_0 = M5Label('', x=160, y=60,  color=C_WARM,  font=FONT_MONT_14)
ans_lbl_1 = M5Label('', x=12,  y=84,  color=C_MID,   font=FONT_MONT_14)
ans_val_1 = M5Label('', x=160, y=84,  color=C_WARM,  font=FONT_MONT_14)
ans_lbl_2 = M5Label('', x=12,  y=108, color=C_MID,   font=FONT_MONT_14)
ans_val_2 = M5Label('', x=160, y=108, color=C_WARM,  font=FONT_MONT_14)
ans_lbl_3 = M5Label('', x=12,  y=132, color=C_MID,   font=FONT_MONT_14)
ans_val_3 = M5Label('', x=160, y=132, color=C_WARM,  font=FONT_MONT_14)
ans_lbl_4 = M5Label('', x=12,  y=156, color=C_MID,   font=FONT_MONT_14)
ans_val_4 = M5Label('', x=160, y=156, color=C_WARM,  font=FONT_MONT_14)
ans_lbl_5 = M5Label('', x=12,  y=180, color=C_MID,   font=FONT_MONT_14)
ans_val_5 = M5Label('', x=160, y=180, color=C_WARM,  font=FONT_MONT_14)
ANS_LBL = [ans_lbl_0, ans_lbl_1, ans_lbl_2, ans_lbl_3, ans_lbl_4, ans_lbl_5]
ANS_VAL = [ans_val_0, ans_val_1, ans_val_2, ans_val_3, ans_val_4, ans_val_5]

ans_city_img = M5Img("/flash/res/default_current_weather.png", x=0, y=0)

# ── Tab bar persistante (jamais effacée par hide_*) ─────────
nav_line = M5Label('', x=0,   y=219, color=C_DIM, font=FONT_MONT_10)
nav_a    = M5Label('', x=5,   y=228, color=C_MID, font=FONT_MONT_10)
nav_b    = M5Label('', x=112, y=228, color=C_MID, font=FONT_MONT_10)
nav_c    = M5Label('', x=215, y=228, color=C_MID, font=FONT_MONT_10)


def _set_tabs(a, b, c):
    nav_line.set_text('- - - - - - - - - - - - - - - - - - - -')
    nav_a.set_text(a)
    nav_b.set_text(b)
    nav_c.set_text(c)


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


def fmt_date():
    try:
        t = time.localtime()
        days = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
        return '{} {:02d}.{:02d}'.format(days[t[6]], t[2], t[1])
    except:
        return ''


def fmt_clock():
    try:
        t = time.localtime()
        return '{:02d}:{:02d}'.format(t[3], t[4])
    except:
        return '--:--'


def _get_battery():
    """Return (level 0-100, is_charging). level=-1 if unknown."""
    if not HAS_POWER:
        return -1, False
    try:
        level    = _power_module.getBatteryLevel()
        charging = _power_module.isCharging()
        return int(level), bool(charging)
    except:
        return -1, False


def _cleanup_wav():
    for f in ['/flash/question.wav', '/flash/answer.wav', '/flash/weather.wav']:
        try:
            uos.remove(f)
        except:
            pass


# ── Hide helpers ────────────────────────────────────────────
def hide_wifi():
    wf_title.set_text(''); wf_hint.set_text(''); wf_line.set_text('')
    wf_net0.set_text(''); wf_net1.set_text(''); wf_net2.set_text('')
    wf_status.set_text('')


def hide_dashboard():
    db_time.set_text('');  db_clock.set_text(''); db_status.set_text('')
    db_in_lbl.set_text(''); db_temp.set_text('')
    db_hm_lbl.set_text(''); db_hum.set_text('')
    db_hum_alert.set_text('')
    db_co2_lbl.set_text(''); db_co2.set_text(''); db_co2_tag.set_text('')
    db_div.set_text('')
    db_wimg.set_hidden(True)


def hide_forecast():
    fc_title.set_text('')
    fc_img.set_hidden(True)


def hide_history():
    hist_title.set_text('')
    hist_img.set_hidden(True)


def hide_qa():
    qa_title.set_text(''); qa_line.set_text('')
    qa_info.set_text('');  qa_info2.set_text('')
    qa_status.set_text('')


def hide_answer():
    ans_title.set_text(''); ans_question.set_text(''); ans_line.set_text('')
    for lbl in ANS_LBL: lbl.set_text('')
    for val in ANS_VAL: val.set_text('')
    ans_city_img.set_hidden(True)


# ── Navigation Pages ────────────────────────────────────────
def _go_back_from_wifi():
    if _prev_page == "forecast":
        show_forecast_page()
    elif _prev_page == "history":
        show_history_page()
    elif _prev_page == "qa":
        show_qa_page()
    else:
        show_dashboard_page()


def show_wifi_confirm_page():
    global current_page, _prev_page
    _prev_page = current_page
    current_page = "wifi_confirm"
    screen.set_screen_bg_color(C_BG)
    hide_dashboard(); hide_forecast(); hide_qa(); hide_answer(); hide_history()
    wf_title.set_text('//  WiFi Setup')
    wf_line.set_text('________________________________')
    wf_hint.set_text('')
    wf_net0.set_text('Connecter au WiFi ?')
    wf_net0.set_text_color(C_WHITE)
    wf_net1.set_text('')
    wf_net2.set_text('')
    if wlan.isconnected():
        wf_status.set_text('Deja connecte')
        wf_status.set_text_color(C_GREEN)
    else:
        wf_status.set_text('Non connecte')
        wf_status.set_text_color(C_YELLOW)
    _set_tabs('< Back', 'OK', 'Back >')
    _update_status_bar()
    led_set(LED_BLUE)


def show_wifi_page():
    global current_page
    current_page = "wifi"
    screen.set_screen_bg_color(0x08080F)
    hide_dashboard(); hide_forecast(); hide_qa(); hide_answer(); hide_history()
    wf_title.set_text('//  WiFi Setup')
    wf_line.set_text('________________________________')
    if wlan.isconnected():
        wf_hint.set_text('Connected  —  B to go back')
        wf_status.set_text_color(C_GREEN)
        _set_tabs('< Prev', 'Dashboard', 'Next >')
    else:
        wf_hint.set_text('A/C : navigate      B : connect')
        wf_status.set_text('Select a network')
        wf_status.set_text_color(C_YELLOW)
        _set_tabs('< Prev', 'Connect', 'Next >')
    _update_status_bar()
    led_set(LED_BLUE)
    _render_networks()


def _update_wifi_indicator():
    if wlan.isconnected():
        sb_wifi.set_img_src('/flash/res/wifi_on.png')
    else:
        sb_wifi.set_img_src('/flash/res/wifi_off.png')


def _update_battery_display():
    level, charging = _get_battery()
    if level < 0:
        sb_bat.set_img_src('/flash/res/bat_unk.png')
    elif charging:
        sb_bat.set_img_src('/flash/res/bat_chg.png')
    elif level >= 75:
        sb_bat.set_img_src('/flash/res/bat_100.png')
    elif level >= 50:
        sb_bat.set_img_src('/flash/res/bat_60.png')
    elif level >= 25:
        sb_bat.set_img_src('/flash/res/bat_40.png')
    elif level >= 10:
        sb_bat.set_img_src('/flash/res/bat_20.png')
    else:
        sb_bat.set_img_src('/flash/res/bat_5.png')


def _update_status_bar():
    _update_wifi_indicator()
    _update_battery_display()


def show_dashboard_page():
    global current_page
    current_page = "dashboard"
    screen.set_screen_bg_color(C_BG)
    hide_wifi(); hide_forecast(); hide_qa(); hide_answer(); hide_history()
    db_in_lbl.set_text('INDOOR')
    db_hm_lbl.set_text('HUM')
    db_co2_lbl.set_text('CO2')
    db_div.set_text('____________________________')
    db_wimg.set_hidden(True)   # shown only after successful fetch
    _set_tabs('WiFi', 'Q&A', 'Forecast')
    db_time.set_text(fmt_date())
    db_clock.set_text(fmt_clock())
    _update_status_bar()
    led_set(LED_CYAN, 15)


def show_forecast_page():
    global current_page
    current_page = "forecast"
    screen.set_screen_bg_color(C_BG)
    hide_wifi(); hide_dashboard(); hide_qa(); hide_answer(); hide_history()
    fc_title.set_text('3-DAY FORECAST')
    fc_img.set_hidden(True)    # shown only after successful fetch
    _set_tabs('Q&A', 'History', 'WiFi')
    _update_status_bar()
    led_set(LED_CYAN, 15)
    if wlan.isconnected():
        _fetch_forecast_img()
    else:
        fc_img.set_hidden(False)  # no WiFi — show default placeholder


def show_history_page():
    global current_page
    current_page = "history"
    screen.set_screen_bg_color(C_BG)
    hide_wifi(); hide_dashboard(); hide_qa(); hide_answer(); hide_forecast()
    hist_title.set_text('// 24H HISTORY')
    hist_img.set_hidden(True)   # shown only after successful fetch
    _set_tabs('Forecast', 'WiFi', 'Dashboard')
    _update_status_bar()
    led_set(LED_CYAN, 15)
    if wlan.isconnected():
        _fetch_history_img()
    else:
        hist_img.set_hidden(False)  # no WiFi — show default placeholder


def _fetch_history_img():
    try:
        gc.collect()
        led_set(LED_ORANGE, 10)
        r = urequests.get(FLASK_URL + '/get-history-image?hours=24')
        if r.status_code == 200:
            data = r.content
            r.close()
            with open('/flash/res/history_data.png', 'wb') as f:
                f.write(data)
            del data; gc.collect()
            hist_img.set_hidden(True)
            hist_img.set_img_src('/flash/res/history_data.png')
            hist_img.set_hidden(False)
        else:
            r.close()
            hist_img.set_hidden(False)
        led_set(LED_CYAN, 15)
    except Exception as e:
        print("History err:", str(e))
        hist_img.set_hidden(False)
        led_set(LED_CYAN, 15)


def show_qa_page():
    global current_page
    current_page = "qa"
    screen.set_screen_bg_color(C_BG)
    hide_wifi(); hide_dashboard(); hide_forecast(); hide_answer(); hide_history()
    qa_title.set_text('//  Ask Me')
    qa_line.set_text('________________________________')
    qa_info.set_text('Press B to record')
    qa_info2.set_text('Speak clearly for 5 seconds')
    qa_status.set_text('Ready !')
    qa_status.set_text_color(C_GREEN)
    _set_tabs('Dashboard', 'Record', 'Forecast')
    _update_status_bar()
    led_set(LED_CYAN, 15)


def show_answer_text(question, lines):
    global current_page
    current_page = "answer"
    screen.set_screen_bg_color(C_BG)
    hide_wifi(); hide_dashboard(); hide_forecast(); hide_qa()
    ans_title.set_text('//  Answer')
    ans_question.set_text(question[:48])
    ans_line.set_text('________________________________')
    for i in range(6):
        if i < len(lines):
            ANS_LBL[i].set_text(str(lines[i][0])[:14])
            ANS_VAL[i].set_text(str(lines[i][1])[:18])
        else:
            ANS_LBL[i].set_text('')
            ANS_VAL[i].set_text('')
    _set_tabs('< Back', 'New quest.', 'Back >')
    _update_status_bar()
    led_set(LED_CYAN, 15)


def show_answer_image(image_path):
    global current_page
    current_page = "answer"
    screen.set_screen_bg_color(C_BG)
    hide_wifi(); hide_dashboard(); hide_forecast(); hide_qa()
    ans_title.set_text(''); ans_question.set_text(''); ans_line.set_text('')
    for lbl in ANS_LBL: lbl.set_text('')
    for val in ANS_VAL: val.set_text('')
    ans_city_img.set_img_src(image_path)
    ans_city_img.set_hidden(False)
    _set_tabs('< Back', 'New quest.', 'Back >')
    _update_status_bar()
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


def connect_selected():
    global device_public_ip
    ssid     = NETWORK_NAMES[selected_network_index]
    password = KNOWN_NETWORKS[ssid]
    wf_status.set_text('Connecting to {}...'.format(ssid))
    led_set(LED_ORANGE)
    if wlan.isconnected():
        wlan.disconnect(); time.sleep(1)
    wlan.connect(ssid, password)
    t0 = time.time()
    while not wlan.isconnected() and time.time() - t0 < 15:
        time.sleep(1)
    if wlan.isconnected():
        led_set(LED_GREEN)
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
        led_set(LED_RED)
        wf_status.set_text('Failed - try again')


def _sync_from_bigquery():
    global last_outdoor_temp, last_outdoor_humidity
    try:
        led_set(LED_ORANGE)
        r = urequests.get(FLASK_URL + '/sync-from-bigquery')
        if r.status_code == 200:
            d = r.json()
            last_outdoor_temp     = d.get('outdoor_temp', 0)
            last_outdoor_humidity = d.get('outdoor_humidity', 0)
        r.close()
    except:
        pass


def _fetch_weather_img():
    try:
        gc.collect()
        led_set(LED_ORANGE, 10)
        r = urequests.get(
            FLASK_URL + '/get-weather-image?ip=' + (device_public_ip or '8.8.8.8'))
        if r.status_code == 200:
            data = r.content
            r.close()
            with open('/flash/res/current_weather.png', 'wb') as f:
                f.write(data)
            del data; gc.collect()
            db_wimg.set_hidden(True)
            db_wimg.set_img_src('/flash/res/current_weather.png')
            db_wimg.set_hidden(False)
        else:
            r.close()
        led_set(LED_CYAN, 15)
    except:
        led_set(LED_CYAN, 15)


def _fetch_forecast_img():
    try:
        gc.collect()
        led_set(LED_ORANGE, 10)
        r = urequests.get(
            FLASK_URL + '/get-forecast-image?ip=' + (device_public_ip or '8.8.8.8'))
        if r.status_code == 200:
            data = r.content
            r.close()
            with open('/flash/res/forecast_weather.png', 'wb') as f:
                f.write(data)
            del data; gc.collect()
            fc_img.set_hidden(True)
            fc_img.set_img_src('/flash/res/forecast_weather.png')
            fc_img.set_hidden(False)
        else:
            r.close()
            fc_img.set_hidden(False)
        led_set(LED_CYAN, 15)
    except:
        fc_img.set_hidden(False)
        led_set(LED_CYAN, 15)


def _send_data(temp, hum, co2):
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


def _play_weather_tts():
    global last_tts_played, mic_initialized
    if is_recording:
        return
    # SÉCURITÉ PRÉSENTATION : Si le micro a été activé, on bloque l'audio pour éviter le crash I2S
    if mic_initialized:
        return
        
    now = time.time()
    if now - last_tts_played < 3600:
        return
    try:
        led_set(LED_WHITE)
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
            try:
                uos.remove('/flash/weather.wav')
            except:
                pass
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
#  Q&A REQUÊTES EN BOUCLE
# ============================================================
def _ask_question():
    global is_recording, mic_initialized

    print("=== _ask_question CALLED ===")
    print("RAM dispo au debut:", gc.mem_free())

    if not wlan.isconnected():
        led_set(LED_RED)
        time.sleep(2)
        led_set(LED_CYAN, 15)
        return

    try:
        is_recording = True

        # Countdown 2s, LED orange
        print("[STEP 1] Countdown")
        led_set(LED_ORANGE)
        time.sleep(2)

        # Enregistrement 5s, LED violette
        print("[STEP 2] LED purple, gc.collect")
        led_set(LED_PURPLE)
        gc.collect()
        print("[STEP 3] RAM apres gc:", gc.mem_free())

        # --- LE MICRO S'ACTIVE SEULEMENT ICI À LA PREMIÈRE QUESTION ---
        if not mic_initialized:
            print("[STEP 4] Initialisation unique du microphone permanent")
            MIC.begin(pin_ws=0, pin_data=34, sample_rate_hz=16000,
                      buffer_length_ms=1000, block_length_ms=100)
            mic_initialized = True
        else:
            print("[STEP 4] Reutilisation du microphone permanent")

        f_mic = open('/flash/question.wav', 'wb')
        MIC.recordStart(f_mic, 5000)
        MIC.waitRecordDone(7000)
        f_mic.close()

        print("[STEP 5] Fin enregistrement, pas de deinit")
        time.sleep_ms(200)
        gc.collect()

        led_set(LED_ORANGE)

        with open('/flash/question.wav', 'rb') as f:
            wav_data = f.read()
        print("Question size:", len(wav_data), "bytes")

        r = urequests.post(
            FLASK_URL + '/ask-question?ip=' + (device_public_ip or '8.8.8.8'),
            data=wav_data,
            headers={
                'Content-Type': 'audio/wav',
                'Content-Length': str(len(wav_data))
            }
        )
        del wav_data
        gc.collect()

        if r.status_code != 200:
            print("Server error:", r.status_code)
            r.close()
            _cleanup_wav()
            led_set(LED_RED)
            time.sleep(2)
            led_set(LED_CYAN, 15)
            return

        response_text = r.text
        r.close()
        del r
        gc.collect()
        print("Response received:", response_text[:200])

        try:
            data = ujson.loads(response_text)
        except Exception as e:
            print("JSON parse error:", str(e))
            led_set(LED_RED)
            time.sleep(2)
            led_set(LED_CYAN, 15)
            return

        response_type = data.get('type', 'text')
        transcription = data.get('transcription', '(empty)')

        if response_type == 'image':
            city = data.get('city', 'Unknown')
            print("Fetching image for city:", city)
            led_set(LED_WHITE)

            gc.collect()
            print("RAM avant download:", gc.mem_free())

            r2 = urequests.get(
                FLASK_URL + '/get-weather-image-large?city=' + city
            )
            if r2.status_code == 200:
                with open('/flash/res/city_weather.png', 'wb') as f:
                    while True:
                        chunk = r2.raw.read(1024)
                        if not chunk:
                            break
                        f.write(chunk)
                r2.close()
                del r2
                gc.collect()
                print("Image telechargee, RAM apres:", gc.mem_free())
                show_answer_image('/flash/res/city_weather.png')
            else:
                r2.close()
                show_answer_text(transcription, [['Error', 'Image not loaded']])

        else:
            lines = data.get('lines', [['Answer', 'No data']])
            print("Showing", len(lines), "text lines")
            show_answer_text(transcription, lines)

        _cleanup_wav()

    except Exception as e:
        print("EXCEPTION:", type(e).__name__, str(e))
        _cleanup_wav()
        led_set(LED_RED)
        time.sleep(2)
        led_set(LED_CYAN, 15)
    finally:
        is_recording = False
        gc.collect()


def _check_humidity_alert(hum):
    if hum < 40:
        db_hum.set_text_color(C_RED)
        db_hum_alert.set_text('! LOW HUM')
        led_set(LED_RED)
    else:
        db_hum.set_text_color(C_COOL)
        db_hum_alert.set_text('')


# ── Callbacks boutons ───────────────────────────────────────
def _btn_a():
    global selected_network_index
    if current_page == "wifi":
        selected_network_index = (selected_network_index - 1) % len(NETWORK_NAMES)
        _render_networks()
    elif current_page == "wifi_confirm":
        _go_back_from_wifi()
    elif current_page == "dashboard":
        show_wifi_confirm_page()
    elif current_page == "qa":
        show_dashboard_page()
    elif current_page == "forecast":
        show_qa_page()
    elif current_page == "history":
        show_forecast_page()
    elif current_page == "answer":
        show_qa_page()


def _btn_b():
    if current_page == "wifi":
        if wlan.isconnected():
            show_dashboard_page()
        else:
            connect_selected()
    elif current_page == "wifi_confirm":
        show_wifi_page()
    elif current_page == "dashboard":
        show_qa_page()
    elif current_page == "qa":
        _ask_question()
    elif current_page == "forecast":
        show_history_page()
    elif current_page == "history":
        show_wifi_confirm_page()
    elif current_page == "answer":
        show_qa_page()
        time.sleep_ms(200)
        _ask_question()


def _btn_c():
    global selected_network_index
    if current_page == "wifi":
        selected_network_index = (selected_network_index + 1) % len(NETWORK_NAMES)
        _render_networks()
    elif current_page == "wifi_confirm":
        _go_back_from_wifi()
    elif current_page == "dashboard":
        show_forecast_page()
    elif current_page == "qa":
        show_forecast_page()
    elif current_page == "forecast":
        show_wifi_confirm_page()
    elif current_page == "history":
        show_dashboard_page()
    elif current_page == "answer":
        show_qa_page()


btnA.wasPressed(_btn_a)
btnB.wasPressed(_btn_b)
btnC.wasPressed(_btn_c)


# ── STARTUP ─────────────────────────────────────────────────
_cleanup_wav()

# PLUS DE MICROPHONE ICI ! Le démarrage est propre et laisse le haut-parleur libre au début.

led_set(LED_BLUE)
show_wifi_page()

if wlan.isconnected():
    led_set(LED_ORANGE)
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


# ── Boucle principale ───────────────────────────────────────
data_last_sent       = time.time() - 250
weather_last_checked = time.time() - 30
time_last_updated    = time.time() - 55

while True:
    try:
        if current_page == "dashboard":
            temp = env3.temperature
            hum  = env3.humidity
            co2  = tvoc.eCO2

            db_temp.set_text('{:.1f}'.format(temp))
            db_hum.set_text('{:.0f}%'.format(hum))
            _check_humidity_alert(hum)

            co2_color, co2_tag = co2_style(co2)
            db_co2.set_text('{}ppm'.format(co2))
            db_co2.set_text_color(co2_color)
            db_co2_tag.set_text(co2_tag)
            db_co2_tag.set_text_color(co2_color)
            if co2 >= 2000:
                led_set(LED_RED)

            now = time.time()
            if now - time_last_updated >= 60:
                db_time.set_text(fmt_date())
                db_clock.set_text(fmt_clock())
                _update_status_bar()
                time_last_updated = now

            if wlan.isconnected():
                if pir.state == 1:
                    _play_weather_tts()
                if now - data_last_sent >= 300:
                    _send_data(temp, hum, co2)
                    data_last_sent = now
                if now - weather_last_checked >= 30:
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