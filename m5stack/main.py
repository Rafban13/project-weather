from m5stack_ui import M5Screen, M5Label, FONT_MONT_14, FONT_MONT_34, FONT_MONT_10
from m5stack import btnA, btnB, btnC, speaker
import unit
from network import WLAN, STA_IF
import urequests
import utime as time
import gc

# Setup écran
screen = M5Screen()
screen.clean_screen()
screen.set_screen_bg_color(0x000000)

# Capteurs
env3 = unit.get(unit.ENV3, unit.PORTA)
pir = unit.get(unit.PIR, unit.PORTB)

# Config
FLASK_URL = "https://weather-service-197991375095.europe-west6.run.app"
DEVICE_ID = "m5stack-Tesla"

# Réseaux connus
KNOWN_NETWORKS = {
    "newyork": "e4yt-dahf-zok7-2098",
    "iot-unil": "4u6uch4hpY9pJ2f9",
    "public-unil": ""
}
NETWORK_NAMES = list(KNOWN_NETWORKS.keys())

# WiFi
wlan = WLAN(STA_IF)
wlan.active(True)
time.sleep(1)

device_public_ip = None
current_page = "wifi"
selected_network_index = 0
last_sound_played = 0

# ─── LABELS PAGE WIFI ───
wifi_title = M5Label('-- WiFi Setup --', x=60, y=5, color=0x00ffff, font=FONT_MONT_14)
wifi_hint = M5Label('A/C: select  B: connect', x=10, y=25, color=0xaaaaaa, font=FONT_MONT_10)
wifi_net0 = M5Label('', x=10, y=55, color=0xffffff, font=FONT_MONT_14)
wifi_net1 = M5Label('', x=10, y=80, color=0xffffff, font=FONT_MONT_14)
wifi_net2 = M5Label('', x=10, y=105, color=0xffffff, font=FONT_MONT_14)
wifi_status = M5Label('', x=10, y=135, color=0xffff00, font=FONT_MONT_10)

# ─── LABELS PAGE DASHBOARD ───
status_label = M5Label('', x=10, y=0, color=0xffffff, font=FONT_MONT_10)
temp_label = M5Label('', x=10, y=18, color=0xcd8100, font=FONT_MONT_34)
hum_label = M5Label('', x=10, y=73, color=0xffffff, font=FONT_MONT_14)
outdoor_temp_label = M5Label('', x=10, y=98, color=0x00ffff, font=FONT_MONT_14)
outdoor_desc_label = M5Label('', x=10, y=118, color=0xaaaaaa, font=FONT_MONT_10)
page_hint = M5Label('', x=10, y=138, color=0x555555, font=FONT_MONT_10)

def show_wifi_page():
    global current_page
    current_page = "wifi"
    screen.set_screen_bg_color(0x001133)
    wifi_title.set_text('-- WiFi Setup --')
    wifi_hint.set_text('A/C: select  B: connect')
    wifi_status.set_text('Select a network')
    update_network_labels()
    status_label.set_text('')
    temp_label.set_text('')
    hum_label.set_text('')
    outdoor_temp_label.set_text('')
    outdoor_desc_label.set_text('')
    page_hint.set_text('')

def update_network_labels():
    labels = [wifi_net0, wifi_net1, wifi_net2]
    for i, lbl in enumerate(labels):
        if i < len(NETWORK_NAMES):
            name = NETWORK_NAMES[i]
            if i == selected_network_index:
                lbl.set_text('>>> ' + name)
                lbl.set_text_color(0x00ff00)
            else:
                lbl.set_text('    ' + name)
                lbl.set_text_color(0xffffff)
        else:
            lbl.set_text('')

def show_dashboard_page():
    global current_page
    current_page = "dashboard"
    screen.set_screen_bg_color(0x000000)
    wifi_title.set_text('')
    wifi_hint.set_text('')
    wifi_net0.set_text('')
    wifi_net1.set_text('')
    wifi_net2.set_text('')
    wifi_status.set_text('')
    page_hint.set_text('B: WiFi page')

def connect_to_selected():
    global device_public_ip
    ssid = NETWORK_NAMES[selected_network_index]
    password = KNOWN_NETWORKS[ssid]
    wifi_status.set_text('Connecting to {}...'.format(ssid))
    if wlan.isconnected():
        wlan.disconnect()
        time.sleep(1)
    wlan.connect(ssid, password)
    start = time.time()
    while not wlan.isconnected() and time.time() - start < 15:
        time.sleep(1)
    if wlan.isconnected():
        wifi_status.set_text('Connected!')
        time.sleep(0.5)
        try:
            r = urequests.get('http://api.ipify.org/?format=text')
            device_public_ip = r.text
            r.close()
        except:
            pass
        show_dashboard_page()
    else:
        wifi_status.set_text('Failed! Try again.')

def play_weather_spoken():
    global last_sound_played
    current_time = time.time()
    if current_time - last_sound_played < 90:
        return
    try:
        status_label.set_text('Getting weather voice...')
        r = urequests.post(
            FLASK_URL + "/generate-current-weather-spoken",
            json={"ip": device_public_ip or "8.8.8.8"}
        )
        if r.status_code == 200:
            with open('/flash/weather.wav', 'wb') as f:
                f.write(r.content)
            r.close()
            speaker.playWAV('/flash/weather.wav', volume=6)
            last_sound_played = current_time
            status_label.set_text('Playing weather!')
        else:
            r.close()
            status_label.set_text('TTS error')
    except Exception as e:
        status_label.set_text('TTS err: {}'.format(str(e)[:15]))

def get_outdoor_weather():
    try:
        r = urequests.get(FLASK_URL + "/get-outdoor-weather?ip=" + (device_public_ip or "8.8.8.8"))
        if r.status_code == 200:
            d = r.json()
            outdoor_temp_label.set_text('Out: {:.1f} C'.format(d["current"]["main"]["temp"]))
            outdoor_desc_label.set_text(d["current"]["weather"][0]["description"][:25])
        r.close()
    except:
        outdoor_temp_label.set_text('Weather error')

def send_data(temp, hum):
    try:
        data = {
            "indoor_temp": temp,
            "indoor_humidity": hum,
            "indoor_air_quality": 0,
            "outdoor_temp": 0,
            "outdoor_humidity": 0,
            "ip_address": device_public_ip or "unknown",
            "device_id": DEVICE_ID
        }
        r = urequests.post(FLASK_URL + "/send-to-bigquery", json=data)
        r.close()
        status_label.set_text('Data sent!')
    except:
        status_label.set_text('Send error')

# ─── BOUTONS ───
def btn_a_pressed():
    global selected_network_index
    if current_page == "wifi":
        selected_network_index = (selected_network_index - 1) % len(NETWORK_NAMES)
        update_network_labels()

def btn_b_pressed():
    if current_page == "wifi":
        connect_to_selected()
    elif current_page == "dashboard":
        show_wifi_page()

def btn_c_pressed():
    global selected_network_index
    if current_page == "wifi":
        selected_network_index = (selected_network_index + 1) % len(NETWORK_NAMES)
        update_network_labels()

btnA.wasPressed(btn_a_pressed)
btnB.wasPressed(btn_b_pressed)
btnC.wasPressed(btn_c_pressed)

# ─── DÉMARRAGE ───
show_wifi_page()

if wlan.isconnected():
    wifi_status.set_text('Already connected!')
    try:
        r = urequests.get('http://api.ipify.org/?format=text')
        device_public_ip = r.text
        r.close()
    except:
        pass
    time.sleep(1)
    show_dashboard_page()

# Timing
data_last_sent = time.time() - 290
weather_last_checked = time.time() - 115

# ─── BOUCLE PRINCIPALE ───
while True:
    try:
        if current_page == "dashboard":
            temp = env3.temperature
            hum = env3.humidity
            temp_label.set_text('{:.1f} C'.format(temp))
            hum_label.set_text('Humidity: {:.1f}%'.format(hum))

            if wlan.isconnected():
                now = time.time()

                # PIR → voix TTS
                if pir.state == 1:
                    play_weather_spoken()

                if now - data_last_sent >= 300:
                    send_data(temp, hum)
                    data_last_sent = now

                if now - weather_last_checked >= 120:
                    get_outdoor_weather()
                    weather_last_checked = now
            else:
                status_label.set_text('No WiFi')

    except Exception as e:
        if current_page == "dashboard":
            status_label.set_text('Err: {}'.format(str(e)[:20]))

    time.sleep(1)
    gc.collect()