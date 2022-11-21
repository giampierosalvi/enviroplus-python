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
datafiles.sort()
first = True
for csvfile in datafiles:
    if first:
        data = pd.read_csv(csvfile, parse_dates=['time (iso)'], index_col=['time (iso)'])
        first = False
    else:
        data = pd.concat([data, pd.read_csv(csvfile, parse_dates=['time (iso)'], index_col=['time (iso)'])])

# setup date info for plotting
#data["datetime"] = pd.to_datetime(data["time (iso)"])
data['date'] = [elem.date() for elem in data.index]
data['year'] = pd.DatetimeIndex(data.index).year
data['month'] = pd.DatetimeIndex(data.index).month
data['dayofyear'] = pd.DatetimeIndex(data.index).dayofyear
data['hour'] = pd.DatetimeIndex(data.index).hour
data['timeofday'] = [elem.time() for elem in data.index]

# fix pressure outliers
p = np.array(data['pressure (hPa)'])
outlieridxs = [idx+1 for idx in np.where(p[1:]-p[:-1]<-5)]
for idx in outlieridxs:
    data.loc[data.index[idx], 'pressure (hPa)'] = (p[idx-1]+p[idx+1])/2
# calculate pressure at sea level
data['pressure sea level (hPa)'] = data['pressure (hPa)'] + 12 * 0.47
data

# check weather data against meteostat (https://dev.meteostat.net/)
from meteostat import Point, Hourly
from datetime import datetime
start = data.index.min()
end = data.index.max()
location = Point(63.43107136658, 10.421607421317301, 45) # Stadsing Dahls gate 21
# Get hourly data
meteostatdata = Hourly(location, start, end)
meteostatdf = meteostatdata.fetch()

meteostatdf

from meteostat import Stations
stations = Stations()
stations = stations.nearby(63.43107136658, 10.421607421317301)
station = stations.fetch()
station

# Compare measurements to meteostat data
# meteostat reports sea-level pressure. Compared to pressure at 100m there is
# a 12 hPa increase. Because Stadsing Dahls gate 21 is about 50m on the sea level,
# we expect a difference of 6 hPa which is exactly what we observe. 
fig, axs = plt.subplots(3, 1, figsize=(8, 18))
sns.lineplot(data=data, x='time (iso)', y='cpu_temperature (C)', label='cpu', ax=axs[0])
sns.lineplot(data=data, x='time (iso)', y='temperature (C)', label='home sensor', ax=axs[0])
sns.lineplot(data=meteostatdf, x='time', y='temp', label='meteostat', ax=axs[0])
sns.lineplot(data=data, x='time (iso)', y='humidity (%)', label='home sensor', ax=axs[1])
sns.lineplot(data=meteostatdf, x='time', y='rhum', label='meteostat', ax=axs[1])
sns.lineplot(data=data, x='time (iso)', y='pressure (hPa)', label='home sensor', ax=axs[2])
sns.lineplot(data=data, x='time (iso)', y='pressure sea level (hPa)', label='home sensor (sea level)', ax=axs[2])
sns.lineplot(data=meteostatdf, x='time', y='pres', label='meteostat (sea level)', ax=axs[2])

# complete series
#fig, axs = plt.subplots(2, 2, figsize=(16, 12))
fig = plt.figure(figsize=(12, 8))
sns.lineplot(data=data, x='time (iso)', y='pm1 (ug/m3)', label="PM1.0")
#axs[0][0].set_title('PM 1.0')
sns.lineplot(data=data, x='time (iso)', y='pm25 (ug/m3)', label="PM2.5")
#axs[0][1].set_title('PM 2.5')
sns.lineplot(data=data, x='time (iso)', y='pm10 (ug/m3)', label="PM10")
#axs[1][0].set_title('PM 10')
plt.ylabel('ug/m3')


# +
def plotVsTimeOfDay(df=None, var=None, ax=None):
    for date in df['date'].unique():
        bydate = df[df['date']==date]
        y = bydate[var].to_numpy()
        x = [t.hour*3600 + t.minute*60 + t.second for t in bydate['timeofday']]
        ax.plot(x, y, alpha=0.7, label=date)
        xticks = np.arange(25)*3600
        ax.set_xticks(xticks, labels = [str(int(xtick/3600)) for xtick in xticks])
        ax.set_title(var)
        ax.grid()
        ax.legend()

# series vs time of day
fig, axs = plt.subplots(3, 1, figsize=(8, 18))
plotVsTimeOfDay(data, 'pm1 (ug/m3)', axs[0])
plotVsTimeOfDay(data, 'pm25 (ug/m3)', axs[1])
plotVsTimeOfDay(data, 'pm10 (ug/m3)', axs[2])
#bydate = data.copy()
#bydate.set_index('timeofday')
#bydate = bydate.groupby('date')
#sns.lineplot(data=bydate, x='timeofday', y='pm1 (ug/m3)', hue='date', ax=axs[0][0])
#sns.lineplot(data=data, x='timeofday', y='pm1 (ug/m3)', hue='date', ax=axs[0][0])
#sns.lineplot(data=data, x='timeofday', y='pm1 (ug/m3)', ax=axs[0][0])
#axs[0][0].set_title('PM 1.0')
#sns.lineplot(data=data, x='timeofday', y='pm25 (ug/m3)', ax=axs[0][1])
#axs[0][1].set_title('PM 2.5')
#sns.lineplot(data=data, x='timeofday', y='pm10 (ug/m3)', ax=axs[1][0])
#axs[1][0].set_title('PM 10')
# -

# series vs hour (data from different minutes and days are mixed)
fig, axs = plt.subplots(3, 1, figsize=(8, 18))
sns.boxplot(data=data, x='hour', y='pm1 (ug/m3)', ax=axs[0])
axs[0].set_xticks(np.arange(24))
axs[0].grid()
axs[0].set_title('PM 1.0')
sns.boxplot(data=data, x='hour', y='pm25 (ug/m3)', ax=axs[1])
axs[1].set_xticks(np.arange(24))
axs[1].grid()
axs[1].set_title('PM 2.5')
sns.boxplot(data=data, x='hour', y='pm10 (ug/m3)', ax=axs[2])
axs[2].set_xticks(np.arange(24))
axs[2].grid()
axs[2].set_title('PM 10')

sns.lineplot(data=data, x='time (iso)', y='humidity (%)')




