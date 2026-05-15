from m5stack_ui import M5Screen, M5Label, FONT_MONT_14, FONT_MONT_34, FONT_MONT_10
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

# Labels écran
status_label = M5Label('Starting...', x=10, y=0, color=0xffffff, font=FONT_MONT_10)
temp_label = M5Label('Temp: --', x=10, y=20, color=0xcd8100, font=FONT_MONT_34)
hum_label = M5Label('Humidity: --', x=10, y=75, color=0xffffff, font=FONT_MONT_14)
outdoor_temp_label = M5Label('Outdoor: --', x=10, y=100, color=0x00ffff, font=FONT_MONT_14)
outdoor_desc_label = M5Label('--', x=10, y=120, color=0xaaaaaa, font=FONT_MONT_10)

# Config
FLASK_URL = "https://weather-service-197991375095.europe-west6.run.app"
DEVICE_ID = "m5stack-tesla"

# WiFi check
wlan = WLAN(STA_IF)
wlan.active(True)

device_public_ip = None

def get_public_ip():
    global device_public_ip
    try:
        response = urequests.get('http://api.ipify.org/?format=text')
        device_public_ip = response.text
        response.close()
        return True
    except:
        return False

def send_data():
    global device_public_ip
    try:
        temp = env3.temperature
        hum = env3.humidity
        data = {
            "indoor_temp": temp,
            "indoor_humidity": hum,
            "indoor_air_quality": 0,
            "outdoor_temp": 0,
            "outdoor_humidity": 0,
            "ip_address": device_public_ip or "unknown",
            "device_id": DEVICE_ID
        }
        response = urequests.post(FLASK_URL + "/send-to-bigquery", json=data)
        response.close()
        status_label.set_text('Data sent!')
        return True
    except Exception as e:
        status_label.set_text('Error: {}'.format(str(e)[:20]))
        return False

def get_outdoor_weather():
    global device_public_ip
    try:
        url = FLASK_URL + "/get-outdoor-weather?ip=" + (device_public_ip or "8.8.8.8")
        response = urequests.get(url)
        if response.status_code == 200:
            data = response.json()
            temp = data["current"]["main"]["temp"]
            desc = data["current"]["weather"][0]["description"]
            outdoor_temp_label.set_text('Out: {:.1f} C'.format(temp))
            outdoor_desc_label.set_text(desc[:25])
        response.close()
        return True
    except Exception as e:
        outdoor_temp_label.set_text('Weather error')
        return False

def update_display():
    temp = env3.temperature
    hum = env3.humidity
    temp_label.set_text('{:.1f} C'.format(temp))
    hum_label.set_text('Humidity: {:.1f}%'.format(hum))

# Démarrage
status_label.set_text('Connecting...')
if wlan.isconnected():
    get_public_ip()
    status_label.set_text('Connected!')

# Timing
data_last_sent = time.time() - 290
weather_last_checked = time.time() - 115

# Boucle principale
while True:
    try:
        update_display()
        
        if wlan.isconnected():
            now = time.time()
            
            if now - data_last_sent >= 300:
                send_data()
                data_last_sent = now
                
            if now - weather_last_checked >= 120:
                get_outdoor_weather()
                weather_last_checked = now
        else:
            status_label.set_text('No WiFi')
            
    except Exception as e:
        status_label.set_text('Err: {}'.format(str(e)[:20]))
    
    time.sleep(5)
    gc.collect()