from m5stack_ui import M5Screen, M5Label, M5Img, FONT_MONT_14, FONT_MONT_34, FONT_MONT_10
from m5stack import btnA, btnB, btnC, speaker
import unit
from network import WLAN, STA_IF
import urequests
import utime as time
import socket
import struct
from machine import RTC
import gc

screen = M5Screen()
screen.clean_screen()
screen.set_screen_bg_color(0x000000)

env3 = unit.get(unit.ENV3, unit.PORTA)
pir = unit.get(unit.PIR, unit.PORTB)
tvoc = unit.get(unit.TVOC, unit.PORTC)

FLASK_URL = "https://weather-service-197991375095.europe-west6.run.app"
DEVICE_ID = "m5stack-Tesla"

NTP_DELTA = 3155673600
NTP_QUERY = b'\x1b' + 47 * b'\0'
NTP_SERVER = 'ch.pool.ntp.org'
TIMEZONE_OFFSET = 2 * 3600

try:
    from wifi_config import KNOWN_NETWORKS
except ImportError:
    KNOWN_NETWORKS = {"newyork": "", "iot-unil": "", "public-unil": ""}
NETWORK_NAMES = list(KNOWN_NETWORKS.keys())

wlan = WLAN(STA_IF)
wlan.active(True)
time.sleep(1)

device_public_ip = None
current_page = "wifi"
selected_network_index = 0
last_sound_played = 0
last_outdoor_temp = 0
last_outdoor_humidity = 0

# LABELS PAGE WIFI
wifi_title = M5Label('-- WiFi Setup --', x=60, y=5, color=0x00ffff, font=FONT_MONT_14)
wifi_hint = M5Label('A/C: select  B: connect', x=10, y=25, color=0xaaaaaa, font=FONT_MONT_10)
wifi_net0 = M5Label('', x=10, y=55, color=0xffffff, font=FONT_MONT_14)
wifi_net1 = M5Label('', x=10, y=80, color=0xffffff, font=FONT_MONT_14)
wifi_net2 = M5Label('', x=10, y=105, color=0xffffff, font=FONT_MONT_14)
wifi_status = M5Label('', x=10, y=135, color=0xffff00, font=FONT_MONT_10)

# LABELS PAGE DASHBOARD
datetime_label = M5Label('', x=5, y=2, color=0x888888, font=FONT_MONT_10)
status_label = M5Label('', x=220, y=2, color=0x00ff88, font=FONT_MONT_10)
indoor_title = M5Label('INDOOR', x=5, y=18, color=0x555555, font=FONT_MONT_10)
temp_label = M5Label('', x=5, y=30, color=0xcd8100, font=FONT_MONT_34)
hum_title = M5Label('HUM', x=175, y=18, color=0x555555, font=FONT_MONT_10)
hum_label = M5Label('', x=170, y=28, color=0x88ccff, font=FONT_MONT_34)
co2_title = M5Label('CO2', x=175, y=75, color=0x555555, font=FONT_MONT_10)
co2_label = M5Label('', x=170, y=85, color=0x00ff00, font=FONT_MONT_14)
co2_badge = M5Label('', x=170, y=100, color=0x00ff00, font=FONT_MONT_10)
sep1 = M5Label('________________________', x=5, y=118, color=0x333333, font=FONT_MONT_10)
weather_image = M5Img("/flash/res/default_current_weather.png", x=0, y=125)
page_hint = M5Label('', x=5, y=225, color=0x444444, font=FONT_MONT_10)

# LABELS PAGE FORECAST
forecast_title = M5Label('', x=90, y=2, color=0x00ffff, font=FONT_MONT_14)
forecast_hint = M5Label('', x=5, y=225, color=0x444444, font=FONT_MONT_10)
forecast_image = M5Img("/flash/res/default_future_weather.png", x=0, y=20)


def get_co2_color_and_quality(co2):
    if co2 < 600:
        return 0x00ff00, 'EXCELLENT'
    elif co2 < 1000:
        return 0xffff00, 'GOOD'
    elif co2 < 2000:
        return 0xff8800, 'POOR'
    else:
        return 0xff0000, 'DANGEROUS'

def sync_ntp():
    try:
        addr = socket.getaddrinfo(NTP_SERVER, 123)[0][-1]
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(10)
        s.sendto(NTP_QUERY, addr)
        msg, _ = s.recvfrom(48)
        s.close()
        ntp_time = struct.unpack('!I', msg[40:44])[0] - NTP_DELTA
        ntp_time += TIMEZONE_OFFSET
        local_time = time.localtime(ntp_time)
        rtc = RTC()
        rtc.datetime((local_time[0], local_time[1], local_time[2], 0,
                      local_time[3], local_time[4], local_time[5], 0))
        return True
    except:
        return False

def update_datetime():
    try:
        t = time.localtime()
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        day = days[t[6]]
        datetime_label.set_text('{} {:02d}.{:02d}  {:02d}:{:02d}'.format(
            day, t[2], t[1], t[3], t[4]))
    except:
        pass

def update_weather_image():
    try:
        url = FLASK_URL + "/get-weather-image?ip=" + (device_public_ip or "8.8.8.8")
        r = urequests.get(url)
        if r.status_code == 200:
            with open('/flash/res/current_weather.png', 'wb') as f:
                f.write(r.content)
            r.close()
            weather_image.set_img_src('/flash/res/current_weather.png')
        else:
            r.close()
    except:
        pass

def update_forecast_image():
    try:
        url = FLASK_URL + "/get-forecast-image?ip=" + (device_public_ip or "8.8.8.8")
        r = urequests.get(url)
        if r.status_code == 200:
            with open('/flash/res/forecast_weather.png', 'wb') as f:
                f.write(r.content)
            r.close()
            forecast_image.set_img_src('/flash/res/forecast_weather.png')
        else:
            r.close()
    except:
        pass

def hide_all_dashboard():
    datetime_label.set_text('')
    status_label.set_text('')
    indoor_title.set_text('')
    temp_label.set_text('')
    hum_title.set_text('')
    hum_label.set_text('')
    co2_title.set_text('')
    co2_label.set_text('')
    co2_badge.set_text('')
    sep1.set_text('')
    weather_image.set_hidden(True)
    page_hint.set_text('')

def hide_all_forecast():
    forecast_title.set_text('')
    forecast_hint.set_text('')
    forecast_image.set_hidden(True)

def hide_all_wifi():
    wifi_title.set_text('')
    wifi_hint.set_text('')
    wifi_net0.set_text('')
    wifi_net1.set_text('')
    wifi_net2.set_text('')
    wifi_status.set_text('')

def show_wifi_page():
    global current_page
    current_page = "wifi"
    screen.set_screen_bg_color(0x001133)
    hide_all_dashboard()
    hide_all_forecast()
    wifi_title.set_text('-- WiFi Setup --')
    wifi_hint.set_text('A/C: select  B: connect')
    wifi_status.set_text('Select a network')
    update_network_labels()

def show_dashboard_page():
    global current_page
    current_page = "dashboard"
    screen.set_screen_bg_color(0x000000)
    hide_all_wifi()
    hide_all_forecast()
    indoor_title.set_text('INDOOR')
    hum_title.set_text('HUM')
    co2_title.set_text('CO2')
    sep1.set_text('________________________')
    weather_image.set_hidden(False)
    page_hint.set_text('< WiFi  |  Forecast >')
    update_datetime()

def show_forecast_page():
    global current_page
    current_page = "forecast"
    screen.set_screen_bg_color(0x000000)
    hide_all_wifi()
    hide_all_dashboard()
    forecast_title.set_text('3-DAY FORECAST')
    forecast_image.set_hidden(False)
    forecast_hint.set_text('< Dashboard  |  WiFi >')
    if wlan.isconnected():
        update_forecast_image()

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
        sync_ntp()
        show_dashboard_page()
        update_weather_image()
    else:
        wifi_status.set_text('Failed! Try again.')

def play_weather_spoken():
    global last_sound_played
    current_time = time.time()
    if current_time - last_sound_played < 90:
        return
    try:
        status_label.set_text('TTS...')
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
            status_label.set_text('')
        else:
            r.close()
            status_label.set_text('TTS err')
    except:
        status_label.set_text('TTS err')


def get_outdoor_weather():
    global last_outdoor_temp, last_outdoor_humidity
    try:
        r = urequests.get(FLASK_URL + "/get-outdoor-weather?ip=" + (device_public_ip or "8.8.8.8"))
        if r.status_code == 200:
            d = r.json()
            last_outdoor_temp = d["current"]["main"]["temp"]
            last_outdoor_humidity = d["current"]["main"]["humidity"]
        r.close()
    except:
        pass

def send_data(temp, hum, co2):
    try:
        data = {
            "indoor_temp": temp,
            "indoor_humidity": hum,
            "indoor_air_quality": co2,
            "outdoor_temp": last_outdoor_temp,
            "outdoor_humidity": last_outdoor_humidity,
            "ip_address": device_public_ip or "unknown",
            "device_id": DEVICE_ID
        }
        r = urequests.post(FLASK_URL + "/send-to-bigquery", json=data)
        r.close()
        status_label.set_text('Sent!')
        time.sleep(2)
        status_label.set_text('')
    except:
        status_label.set_text('Err')

def btn_a_pressed():
    global selected_network_index
    if current_page == "wifi":
        selected_network_index = (selected_network_index - 1) % len(NETWORK_NAMES)
        update_network_labels()
    elif current_page == "forecast":
        show_dashboard_page()

def btn_b_pressed():
    if current_page == "wifi":
        connect_to_selected()
    elif current_page == "dashboard":
        show_wifi_page()
    elif current_page == "forecast":
        show_wifi_page()

def btn_c_pressed():
    global selected_network_index
    if current_page == "wifi":
        selected_network_index = (selected_network_index + 1) % len(NETWORK_NAMES)
        update_network_labels()
    elif current_page == "dashboard":
        show_forecast_page()

btnA.wasPressed(btn_a_pressed)
btnB.wasPressed(btn_b_pressed)
btnC.wasPressed(btn_c_pressed)

show_wifi_page()

if wlan.isconnected():
    wifi_status.set_text('Already connected!')
    try:
        r = urequests.get('http://api.ipify.org/?format=text')
        device_public_ip = r.text
        r.close()
    except:
        pass
    sync_ntp()
    time.sleep(1)
    show_dashboard_page()
    get_outdoor_weather()
    update_weather_image()  

data_last_sent = time.time() - 250
weather_last_checked = time.time() - 115
time_last_updated = time.time() - 55

while True:
    try:
        if current_page == "dashboard":
            temp = env3.temperature
            hum = env3.humidity
            co2 = tvoc.eCO2
            temp_label.set_text('{:.1f}'.format(temp))
            hum_label.set_text('{:.1f}%'.format(hum))
            co2_color, co2_quality = get_co2_color_and_quality(co2)
            co2_label.set_text('{}ppm'.format(co2))
            co2_label.set_text_color(co2_color)
            co2_badge.set_text(co2_quality)
            co2_badge.set_text_color(co2_color)
            now = time.time()
            if now - time_last_updated >= 60:
                update_datetime()
                time_last_updated = now
            if wlan.isconnected():
                if pir.state == 1:
                    play_weather_spoken()
                if now - data_last_sent >= 300:
                    send_data(temp, hum, co2)
                    data_last_sent = now
                if now - weather_last_checked >= 120:
                    update_weather_image()
                    weather_last_checked = now
            else:
                status_label.set_text('No WiFi')
    except Exception as e:
        if current_page == "dashboard":
            status_label.set_text('Err')
    time.sleep(1)
    gc.collect()