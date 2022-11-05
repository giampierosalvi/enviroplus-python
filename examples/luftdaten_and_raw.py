import logging
import sys
import requests
import ST7735 # LCD display
import time
import colorsys
from subprocess import PIPE, Popen, check_output
from PIL import Image, ImageDraw, ImageFont
from fonts.ttf import RobotoMedium as UserFont
from collections import deque # to implement circular bufffer for moving average

# import sensors ========================================================
from bme280 import BME280
from pms5003 import PMS5003, ReadTimeoutError
from enviroplus import gas
try:
    from smbus2 import SMBus
except ImportError:
    from smbus import SMBus
try:
    # Transitional fix for breaking change in LTR559
    from ltr559 import LTR559
    sensors['ltr559'] = LTR559()
except ImportError:
    import ltr559
    sensors['ltr559'] = ltr559()

sensors['gas'] = gas()
bus = SMBus(1)
sensors['bme280'] = BME280(i2c_dev=bus)
sensors['pms5003'] = PMS5003()
# ========================================================================

print("""
luftdaten_and_raw.py - Uploads data to luftdaten and saves raw values to disk
=============================================================================
Luftdaten INFO
Reads temperature, pressure, humidity,
PM2.5, and PM10 from Enviro plus and sends data to Luftdaten,
the citizen science air quality project.

Note: you'll need to register with Luftdaten at:
https://meine.luftdaten.info/ and enter your Raspberry Pi
serial number that's displayed on the Enviro plus LCD along
with the other details before the data appears on the
Luftdaten map.

Press Ctrl+C to exit!

========================================================================

Combined Raw:
Saves raw data to disk

NOTE: temperature is not adjusted for CPU temperature (the sensor board
      is assumed to be connected to the raspberry pi via a cable)

Press Ctrl+C to exit!

""")

# prefix to the sensor ID for upload to luftdaten
id_prefix = 'esp8266-'

logging.basicConfig(
    format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

logging.info(""" """)

# Create a dictionary with variable names and units
units = {
    "cpu_temperature": "C",
    "temperature": "C",
    "compensated_temperature": "C"
    "pressure": "hPa",
    "humidity": "%",
    "light": "Lux",
    "oxidising": "kO",
    "reducing": "kO",
    "nh3": "kO",
    "pm1": "ug/m3",
    "pm25": "ug/m3",
    "pm10": "ug/m3"}
# list of variables
variables = units.keys()
# list of display variables
disp_vars = ['compensated_temperature', 'pressure', 'humidity', 'light',
             'oxidising', 'reducing', 'nh3', 'pm1', 'pm25', 'pm10']

# main dictionary to store values. Each value is stored in a cricular
# buffer so that averages can be returned as well as single values
bufferLen = 10
raw = dict()
for variable in variables:
    raw[variable] = deque(maxlen=bufferLen)

# Define your own warning limits
# The limits definition follows the order of the variables array
# Example limits explanation for temperature:
# [4,18,28,35] means
# [-273.15 .. 4] -> Dangerously Low
# (4 .. 18]      -> Low
# (18 .. 28]     -> Normal
# (28 .. 35]     -> High
# (35 .. MAX]    -> Dangerously High
# DISCLAIMER: The limits provided here are just examples and come
# with NO WARRANTY. The authors of this example code claim
# NO RESPONSIBILITY if reliance on the following values or this
# code in general leads to ANY DAMAGES or DEATH.
limits = {"compensated_temperature": [4, 18, 25, 35],
          "pressure": [250, 650, 1013.25, 1015],
          "humidity": [20, 30, 60, 70],
          "light": [-1, -1, 30000, 100000],
          "oxidised": [-1, -1, 40, 50],
          "reduced": [-1, -1, 450, 550],
          "nh3": [-1, -1, 200, 300],
          "pm1": [-1, -1, 50, 100],
          "pm25": [-1, -1, 50, 100],
          "pm10": [-1, -1, 50, 100]}

# RGB palette for values on the combined screen
palette = [(0, 0, 255),           # Dangerously Low
           (0, 255, 255),         # Low
           (0, 255, 0),           # Normal
           (255, 255, 0),         # High
           (255, 0, 0)]           # Dangerously High
values_lcd = {} # this holds the past values for graphs

# Get CPU temperature to use for compensation
def get_cpu_temperature():
    process = Popen(['vcgencmd', 'measure_temp'],
                    stdout=PIPE, universal_newlines=True)
    output, _error = process.communicate()
    return float(output[output.index('=') + 1:output.rindex("'")])


# Get Raspberry Pi serial number to use as ID
def get_serial_number():
    with open('/proc/cpuinfo', 'r') as f:
        for line in f:
            if line[0:6] == 'Serial':
                return line.split(":")[1].strip()


# Check for Wi-Fi connection
def check_wifi():
    if check_output(['hostname', '-I']):
        return True
    else:
        return False


# Create ST7735 LCD display class
lcd = ST7735.ST7735(
    port=0,
    cs=1,
    dc=9,
    backlight=12,
    rotation=270,
    spi_speed_hz=10000000
)

# Initialize display
lcd.begin()

# Set up canvas and font
img = Image.new('RGB', (lcd.width, lcd.height), color=(0, 0, 0))
draw = ImageDraw.Draw(img)
font_size_small = 10
font_size_large = 20
font = ImageFont.truetype(UserFont, font_size_large)
smallfont = ImageFont.truetype(UserFont, font_size_small)
x_offset = 2
y_offset = 2
message = ""

# The position of the top bar
top_pos = 25

# Displays data and text on the 0.96" LCD
def display_text(variable, data, unit):
    # Maintain length of list
    values_lcd[variable] = values_lcd[variable][1:] + [data]
    # Scale the values for the variable between 0 and 1
    vmin = min(values_lcd[variable])
    vmax = max(values_lcd[variable])
    colours = [(v - vmin + 1) / (vmax - vmin + 1)
               for v in values_lcd[variable]]
    # Format the variable name and value
    message = "{}: {:.1f} {}".format(variable[:4], data, unit)
    #logging.info(message)
    draw.rectangle((0, 0, lcd.width, lcd.height), (255, 255, 255))
    for i in range(len(colours)):
        # Convert the values to colours from red to blue
        colour = (1.0 - colours[i]) * 0.6
        r, g, b = [int(x * 255.0)
                   for x in colorsys.hsv_to_rgb(colour, 1.0, 1.0)]
        # Draw a 1-pixel wide rectangle of colour
        draw.rectangle((i, top_pos, i + 1, lcd.height), (r, g, b))
        # Draw a line graph in black
        line_y = lcd.height - \
            (top_pos + (colours[i] * (lcd.height - top_pos))) + top_pos
        draw.rectangle((i, line_y, i + 1, line_y + 1), (0, 0, 0))
    # Write the text at the top in black
    draw.text((0, 0), message, font=font, fill=(0, 0, 0))
    lcd.display(img)

# Displays all the text on the 0.96" LCD
def display_everything():
    draw.rectangle((0, 0, lcd.width, lcd.height), (0, 0, 0))
    column_count = 2
    row_count = (len(disp_vars) / column_count)
    for i in range(len(disp_vars)):
        variable = disp_vars[i]
        data_value = values_lcd[variable][-1]
        unit = units[i]
        x = x_offset + ((lcd.width // column_count) * (i // row_count))
        y = y_offset + ((lcd.height / row_count) * (i % row_count))
        message = "{}: {:.1f} {}".format(variable[:4], data_value, unit)
        lim = limits[i]
        rgb = palette[0]
        for j in range(len(lim)):
            if data_value > lim[j]:
                rgb = palette[j + 1]
        draw.text((x, y), message, font=smallfont, fill=rgb)
    lcd.display(img)

def send_to_luftdaten(sensor_id):
    # format values according to luftdaten requirements
    pm_values_json = [{"value_type": "P1", "value": np.mean(raw['pm10'])},
                      {"value_type": "P2", "value": np.mean(raw['pm25'])}]
    env_values_json = [{"value_type": t, "value": np.mean(raw[t])}
                       for t in ["temperature", "pressure", "humidity"]]

    resp_1 = requests.post(
        "https://api.luftdaten.info/v1/push-sensor-data/",
        json={
            "software_version": "enviro-plus 0.0.1",
            "sensordatavalues": pm_values_json
        },
        headers={
            "X-PIN": "1",
            "X-Sensor": sensor_id,
            "Content-Type": "application/json",
            "cache-control": "no-cache"
        }
    )

    resp_2 = requests.post(
        "https://api.luftdaten.info/v1/push-sensor-data/",
        json={
            "software_version": "enviro-plus 0.0.1",
            "sensordatavalues": env_values_json
        },
        headers={
            "X-PIN": "11",
            "X-Sensor": sensor_id,
            "Content-Type": "application/json",
            "cache-control": "no-cache"
        }
    )

    if resp_1.ok and resp_2.ok:
        return True
    else:
        return False

# updates both the raw and the values_lcd circular buffers
# the first are used for averages and the second for graphs
# could be simplified if we assume the same lenght for both
def update():
    try:
        val = get_cpu_temperature()
        raw['cpu_temperature'].append(val)
        val = sensors['bme280'].get_temperature()
        raw['temperature'].append(val)
        values_lcd['temperature'].append(val)
        if not compensate_temperature:
            comp_temp = val
        else:
            avg_cpu_temp = np.mean(raw['cpu_temperature'])
            comp_temp = val - ((avg_cpu_temp - val) / comp_factor)
        raw['compensated_temperature'].append(comp_temp)
        values_lcd['compensated_temperature'].append(comp_temp)
        val = sensors['bme280'].get_pressure()
        raw['pressure'].append(val)
        values_lcd['pressure'].append(val)
        val = sensors['bme280'].get_humidity()
        raw['humidity'].append(val)
        values_lcd['humidity'].append(val)
        val = sensors['ltr559'].get_lux()
        raw['light'].append(val)
        values_lcd['light'].append(val)
        gas_data = seonsors['gas'].read_all()
        val = gas_data.oxidising / 1000
        raw['oxidising'].append(val)
        values_lcd['oxidising'].append(val)
        val = gas_data.reducing / 1000
        raw['reducing'].append(val)
        values_lcd['reducing'].append(val)
        val = gas_data.nh3 / 1000
        raw['nh3'].append(val)
        values_lcd['nh3'].append(val)
        try:
            pm_values = pms5003.read()
        except ReadTimeoutError:
            pms5003.reset()
            pm_values = pms5003.read()
        val = pm_values.pm_ug_per_m3(1.0)
        raw['pm1'].append(val)
        values_lcd['pm1'].append(val)
        val = pm_values.pm_ug_per_m3(2.5)
        raw['pm25'].append(val)
        values_lcd['pm25'].append(val)
        val = pm_values.pm_ug_per_m3(10)
        raw['pm10'].append(val)
        values_lcd['pm10'].append(val)
    except Exception as e:
        print(e)

# Compensation factor for temperature
comp_factor = 1

# Raspberry Pi ID to send to Luftdaten
sensor_id = id_prefix + get_serial_number()


# Added for state
delay = 0.5  # Debounce the proximity tap
mode = 10     # The starting mode
last_page = 0
light = 1


for v in disp_vars:
    values_lcd[v] = deque(maxlen=lcd.width)


# Text settings
font_size = 16
font = ImageFont.truetype(UserFont, font_size)

# Display Raspberry Pi serial and Wi-Fi status
print("Raspberry Pi serial: {}".format(get_serial_number()))
print("Wi-Fi: {}\n".format("connected" if check_wifi() else "disconnected"))

time_since_update = 0
update_time = time.time()

# Main loop to read data, display, and send to Luftdaten
while True:
    try:
        curtime = time.time()
        time_since_update = curtime - update_time

        update()

        if time_since_update > 145:
            resp = send_to_luftdaten(sensor_id)
            update_time = curtime
            print("Response: {}\n".format("ok" if resp else "failed"))

        # Now comes the combined.py functionality:
        # If the proximity crosses the threshold, toggle the mode
        proximity = sensors['ltr559'].get_proximity()
        if proximity > 1500 and curtime - last_page > delay:
            mode = (mode + 1) % 11
            last_page = curtime
        var_name = disp_vars[mode]
        # first take care of exceptions
        if mode == 10:
            # Everything on one screen
            display_everything()
            continue

        # this is the normal case (pressure, humidity, oxidising,
        # reducing, nh3, pm1, pm25, pm10)
        display_text(var_name, raw[var_name][0], unit[var_name])

    except Exception as e:
        print(e)
