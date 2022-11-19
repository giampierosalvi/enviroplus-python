import logging
import sys
import os
import requests
import ST7735 # LCD display
import time
from datetime import datetime # to simplify iso format
import colorsys
from subprocess import PIPE, Popen, check_output
from PIL import Image, ImageDraw, ImageFont
from fonts.ttf import RobotoMedium as UserFont
from collections import deque # to implement circular bufffer for moving average
import numpy as np

# import sensors ========================================================
from bme280 import BME280
from pms5003 import PMS5003, ReadTimeoutError
from enviroplus import gas
try:
    from smbus2 import SMBus
except ImportError:
    from smbus import SMBus
sensors = dict() # holds sensor objects
try:
    # Transitional fix for breaking change in LTR559
    from ltr559 import LTR559
    sensors['ltr559'] = LTR559()
except ImportError:
    import ltr559
    sensors['ltr559'] = ltr559()

sensors['gas'] = gas # this is a module, copy module name
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
log_path = "/home/pi/MEGA/air_quality/"

logging.basicConfig(
    format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

logging.info(""" """)

# Create a dictionary with variable names and units
units = {
    "cpu_temperature": "C",
    "temperature": "C",
    "compensated_temperature": "C",
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

header = "time (iso),"+",".join(var+" ("+units[var]+")" for var in variables)

# main dictionary to store values. Each value is stored in a cricular
# buffer so that averages can be returned as well as single values
bufferLen = 60 # this roughly correspond to seconds
raw = dict()
for variable in variables:
    raw[variable] = deque(maxlen=bufferLen)

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

def send_to_luftdaten(sensor_id):
    # format values according to luftdaten requirements
    pm_values_json = [{"value_type": "P0", "value": np.mean(raw['pm1'])},
                      {"value_type": "P1", "value": np.mean(raw['pm10'])},
                      {"value_type": "P2", "value": np.mean(raw['pm25'])}]
    #env_values_json = [{"value_type": t, "value": np.mean(raw[t])}
    #                   for t in ["temperature", "pressure", "humidity"]]
    # luftdaten wants pressure in Pa instead of hPa
    env_values_json = [{"value_type": "temperature", "value": np.mean(raw["temperature"])},
                       {"value_type": "pressure", "value": np.mean(raw["pressure"])*100},
                       {"value_type": "humidity", "value": np.mean(raw["humidity"])}]

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

compensate_temperature = False
    
# collects data from sensors and updates raw circular buffers used for averages
# throws and exception if any of the sensors fails to return values.
def update():
    try:
        raw['cpu_temperature'].append(get_cpu_temperature())
        raw['temperature'].append(sensors['bme280'].get_temperature())
        if not compensate_temperature:
            comp_temp = raw['temperature'][-1] # <- check if this is the last index
        else:
            avg_cpu_temp = np.mean(raw['cpu_temperature'])
            comp_temp = val - ((avg_cpu_temp - val) / comp_factor)
        raw['compensated_temperature'].append(comp_temp)
        raw['pressure'].append(sensors['bme280'].get_pressure())
        raw['humidity'].append(sensors['bme280'].get_humidity())
        raw['light'].append(sensors['ltr559'].get_lux())
        gas_data = sensors['gas'].read_all()
        raw['oxidising'].append(gas_data.oxidising / 1000)
        raw['reducing'].append(gas_data.reducing / 1000)
        raw['nh3'].append(gas_data.nh3 / 1000)
        try:
            pm_values = sensors['pms5003'].read()
        except ReadTimeoutError:
            sensors['pms5003'].reset()
            pm_values = sensors['pms5003'].read()
        raw['pm1'].append(pm_values.pm_ug_per_m3(1.0))
        raw['pm25'].append(pm_values.pm_ug_per_m3(2.5))
        raw['pm10'].append(pm_values.pm_ug_per_m3(10))
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

        # update circular arrays
        print(datetime.now().isoformat(), ": updating")
        update()

        #print(datetime.now().isoformat())
        #for var in variables:
        #    print(var, raw[var][-1], units[var])
        #    #print(var, "{:.2f}".format(raw[var][-1]), units[var])
        
        if time_since_update > bufferLen: # 145:
            update_time = curtime # do first to make sure it's done
            print(datetime.now().isoformat(), ": saving to local file")
            # write to local file
            filename = log_path + sensor_id + '_' + time.strftime('%Y-%m-%d') + '.csv'
            if not os.path.exists(filename):
                with open(filename, 'w') as f:
                    f.write(header+'\n')
            # opening and closing ensures we write in the right file past midnight
            f = open(filename, 'a')
            data = [np.mean(raw[v]) for v in variables]
            f.write(datetime.now().isoformat()+',')
            f.write(','.join("{:.2f}".format(val) for val in data))
            f.write('\n')
            f.close()
            # upload values to luftdaten
            print(datetime.now().isoformat(), ": uploading to luftdaten")
            resp = send_to_luftdaten(sensor_id)
            print("Response: {}\n".format("ok" if resp else "failed"))
    except Exception as e:
        print(e)
