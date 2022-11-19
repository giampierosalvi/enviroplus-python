# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.14.1
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# # Tools to display data from luftdaten_and_raw.py
#

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
import seaborn as sns
import os
import re

# read data from multiple files
dataroot = os.path.expanduser('~/MEGA/air_quality')
sensorID = 'esp8266-100000008faa2b38'
# open either csv.gz or .csv files
datafiles = [os.path.join(dataroot, f) for f in os.listdir(dataroot) if re.match(sensorID+r'.*\.csv(.gz)?', f)]
first = True
for csvfile in datafiles:
    if first:
        data = pd.read_csv(csvfile)
        first = False
    else:
        data = pd.concat([data, pd.read_csv(csvfile)])
# setup date info for plotting
data["datetime"] = pd.to_datetime(data["time (iso)"])
data['year'] = pd.DatetimeIndex(data['datetime']).year
data['month'] = pd.DatetimeIndex(data['datetime']).month
data['dayofyear'] = pd.DatetimeIndex(data['datetime']).dayofyear
data['hour'] = pd.DatetimeIndex(data['datetime']).hour
data

# check weather data against meteostat (https://dev.meteostat.net/)
from meteostat import Point, Hourly
from datetime import datetime
start = data['datetime'].min()
end = data['datetime'].max()
location = Point(63.43107136658, 10.421607421317301, 45) # Stadsing Dahls gate 21
# Get hourly data
meteostatdata = Hourly(location, start, end)
meteostatdf = meteostatdata.fetch()

meteostatdf

from meteostat import Stations
stations = Stations()
stations = stations.nearby(63.43107136658, 10.421607421317301)
station = stations.fetch(1)
station

# Compare measurements to open weather data
fig, axs = plt.subplots(2, 2, figsize=(16, 12))
sns.lineplot(data=data, x='datetime', y='temperature (C)', label='home sensor', ax=axs[0][0])
sns.lineplot(data=meteostatdf, x='time', y='temp', label='meteostat', ax=axs[0][0])
sns.lineplot(data=data, x='datetime', y='humidity (%)', label='home sensor', ax=axs[0][1])
sns.lineplot(data=meteostatdf, x='time', y='rhum', label='meteostat', ax=axs[0][1])
sns.lineplot(data=data, x='datetime', y='pressure (hPa)', label='home sensor', ax=axs[1][0])
sns.lineplot(data=meteostatdf, x='time', y='pres', label='meteostat', ax=axs[1][0])

sns.lineplot(data=data, x='datetime', y='pm25 (ug/m3)')

sns.lineplot(data=data, x='hour', y='pm25 (ug/m3)')

sns.lineplot(data=data, x='hour', y='pm10 (ug/m3)')
plt.xticks(np.arange(24))
plt.grid()

sns.lineplot(data=data, x='hour', y='humidity (%)')
plt.xticks(np.arange(24))
plt.grid()

sns.lineplot(data=data, x='datetime', y='humidity (%)')


