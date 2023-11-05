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
import glob

# read data from multiple files
dataroot = os.path.expanduser('~/MEGA/air_quality')
sensorID = 'esp8266-100000008faa2b38'
filepattern = '.*'+sensorID+r'.*\.csv(.gz)?$' # match both .csv and .csv.gz files
datafiles = [f for f in glob.glob(dataroot+'/**', recursive=True) if re.match(filepattern, f)]
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
data['dayofweek'] = pd.DatetimeIndex(data.index).dayofweek
data['dayofyear'] = pd.DatetimeIndex(data.index).dayofyear
data['hour'] = pd.DatetimeIndex(data.index).hour
data['timeofday'] = [elem.time() for elem in data.index]

# fix pressure outliers
p = np.array(data['pressure (hPa)'])
outlieridxs = [idx+1 for idx in np.where(p[1:]-p[:-1]<-5)]
for idx in outlieridxs:
    data.loc[data.index[idx], 'pressure (hPa)'] = (p[idx-1]+p[idx+1])/2
# calculate pressure at sea level
data['pressure sea level (hPa)'] = data['pressure (hPa)'] + 12 * 0.48
data

# check weather data against meteostat (https://dev.meteostat.net/)
from meteostat import Point, Hourly
from datetime import datetime
start = data.index.min()
end = data.index.max()
location = Point(63.43107136658, 10.421607421317301, 47) # Stadsing Dahls gate 21
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
#sns.lineplot(data=data, x='time (iso)', y='cpu_temperature (C)', label='cpu', ax=axs[0])
sns.lineplot(data=data, x='time (iso)', y='temperature (C)', label='home sensor', ax=axs[0])
sns.lineplot(data=meteostatdf, x='time', y='temp', label='meteostat', ax=axs[0])
sns.lineplot(data=data, x='time (iso)', y='humidity (%)', label='home sensor', ax=axs[1])
sns.lineplot(data=meteostatdf, x='time', y='rhum', label='meteostat', ax=axs[1])
sns.lineplot(data=data, x='time (iso)', y='pressure (hPa)', label='home sensor', ax=axs[2])
sns.lineplot(data=data, x='time (iso)', y='pressure sea level (hPa)', label='home sensor (sea level)', ax=axs[2])
sns.lineplot(data=meteostatdf, x='time', y='pres', label='meteostat (sea level)', ax=axs[2])

#t1 = data['temperature (C)'].to_numpy()
#t2 = meteostatdf['temp'].to_numpy()
#W_est = np.linalg.pinv(t1.T).dot(t2.T).T
plt.plot(data['temperature (C)']-3)
plt.plot(meteostatdf['temp'])

# complete series
#fig, axs = plt.subplots(2, 2, figsize=(16, 12))
fig, axs = plt.subplots(3, 1, figsize=(12, 12))
sns.lineplot(data=data, x='time (iso)', y='pm1 (ug/m3)', ax=axs[0])
axs[0].set_ylabel('ug/m3')
axs[0].set_xlabel('')
axs[0].set_title('PM 1.0')
sns.lineplot(data=data, x='time (iso)', y='pm25 (ug/m3)', ax=axs[1])
axs[1].set_ylabel('ug/m3')
axs[1].set_xlabel('')
axs[1].set_title('PM 2.5')
sns.lineplot(data=data, x='time (iso)', y='pm10 (ug/m3)', ax=axs[2])
axs[2].set_ylabel('ug/m3')
axs[2].set_title('PM 10')

# +
from scipy.signal import savgol_filter
def plotVsTimeOfDay(df=None, var=None, ax=None, smooth=False):
    lastday = df['date'][-1]
    for date in df['date'].unique():
        if (lastday-date).days > 7: # only show last week
            continue
        bydate = df[df['date']==date]
        y = bydate[var].to_numpy()
        if smooth:
            y = savgol_filter(y, 51, 3)
        x = [t.hour*3600 + t.minute*60 + t.second for t in bydate['timeofday']]
        if ax==None:
            ax = plt.gca()
        ax.plot(x, y, alpha=0.7, label=date)
        xticks = np.arange(25)*3600
        ax.set_xticks(xticks, labels = [str(int(xtick/3600)) for xtick in xticks])
        ax.set_title(var)
        ax.grid()
        ax.legend()

# series vs time of day
fig, axs = plt.subplots(3, 1, figsize=(12, 18))
smooth = True
plotVsTimeOfDay(data, 'pm1 (ug/m3)', axs[0], smooth)
plotVsTimeOfDay(data, 'pm25 (ug/m3)', axs[1], smooth)
plotVsTimeOfDay(data, 'pm10 (ug/m3)', axs[2], smooth)
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
fig, axs = plt.subplots(3, 1, figsize=(16, 18))
sns.boxplot(data=data, x='hour', y='pm1 (ug/m3)', ax=axs[0])
axs[0].set_xticks(np.arange(24))
axs[0].grid()
axs[0].set_title('PM 1.0')
axs[0].set_ylim([0, 50])
sns.boxplot(data=data, x='hour', y='pm25 (ug/m3)', ax=axs[1])
axs[1].set_xticks(np.arange(24))
axs[1].grid()
axs[1].set_title('PM 2.5')
axs[1].set_ylim([0, 100])
sns.boxplot(data=data, x='hour', y='pm10 (ug/m3)', ax=axs[2])
axs[2].set_xticks(np.arange(24))
axs[2].grid()
axs[2].set_title('PM 10')
axs[2].set_ylim([0, 100])

# series vs month (data from different minutes and days are mixed)
fig, axs = plt.subplots(3, 1, figsize=(16, 18))
sns.boxplot(data=data, x='month', y='pm1 (ug/m3)', ax=axs[0])
axs[0].set_xticks(np.arange(12))
axs[0].grid()
axs[0].set_title('PM 1.0')
axs[0].set_ylim([0, 100])
sns.boxplot(data=data, x='month', y='pm25 (ug/m3)', ax=axs[1])
axs[1].set_xticks(np.arange(12))
axs[1].grid()
axs[1].set_title('PM 2.5')
axs[1].set_ylim([0, 200])
sns.boxplot(data=data, x='month', y='pm10 (ug/m3)', ax=axs[2])
axs[2].set_xticks(np.arange(12))
axs[2].grid()
axs[2].set_title('PM 10')
axs[2].set_ylim([0, 200])

# series vs day of week (data from different minutes and days are mixed)
dayofweeknames = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']
fig, axs = plt.subplots(3, 1, figsize=(16, 18))
sns.violinplot(data=data, x='dayofweek', y='pm1 (ug/m3)', ax=axs[0], scale='width')
#axs[0].set_xticks(np.arange(24))
axs[0].set_xticklabels(dayofweeknames)
axs[0].grid()
axs[0].set_title('PM 1.0')
axs[0].set_ylim([0, 50])
sns.violinplot(data=data, x='dayofweek', y='pm25 (ug/m3)', ax=axs[1], scale='width')
#axs[1].set_xticks(np.arange(24))
axs[1].set_xticklabels(dayofweeknames)
axs[1].grid()
axs[1].set_title('PM 2.5')
axs[1].set_ylim([0, 100])
sns.violinplot(data=data, x='dayofweek', y='pm10 (ug/m3)', ax=axs[2], scale='width')
#axs[2].set_xticks(np.arange(24))
axs[2].set_xticklabels(dayofweeknames)
axs[2].grid()
axs[2].set_title('PM 10')
axs[2].set_ylim([0, 100])

# series vs hour (data from different minutes and days are mixed)
fig, axs = plt.subplots(3, 1, figsize=(16, 18))
sns.violinplot(data=data, x='hour', y='pm1 (ug/m3)', ax=axs[0], scale='width')
axs[0].set_xticks(np.arange(24))
axs[0].grid()
axs[0].set_title('PM 1.0')
axs[0].set_ylim([0, 50])
sns.violinplot(data=data, x='hour', y='pm25 (ug/m3)', ax=axs[1], scale='width')
axs[1].set_xticks(np.arange(24))
axs[1].grid()
axs[1].set_title('PM 2.5')
axs[1].set_ylim([0, 100])
sns.violinplot(data=data, x='hour', y='pm10 (ug/m3)', ax=axs[2], scale='width')
axs[2].set_xticks(np.arange(24))
axs[2].grid()
axs[2].set_title('PM 10')
axs[2].set_ylim([0, 100])

sns.lineplot(data=data, x='time (iso)', y='humidity (%)')

# PM2.5 vs temperature
plt.figure(figsize=(16,4))
ax1 = sns.lineplot(data=data, x='time (iso)', y='pm25 (ug/m3)')
ax1.set_ylim([0, 200])
ax2 = ax1.twinx()
sns.lineplot(data=data, x='time (iso)', y='temperature (C)', ax=ax2, color='r')

# PM2.5 vs temperature
plt.figure(figsize=(16,4))
ax1 = sns.lineplot(data=data, x='time (iso)', y='pm25 (ug/m3)')
ax1.set_ylim([0, 200])
ax2 = ax1.twinx()
sns.lineplot(data=meteostatdf, x='time', y='temp', ax=ax2, color='r')

# PM2.5 vs wind speed
plt.figure(figsize=(16,4))
ax1 = sns.lineplot(data=data, x='time (iso)', y='pm25 (ug/m3)')
ax1.set_ylim([0, 200])
ax2 = ax1.twinx()
sns.lineplot(data=meteostatdf, x='time', y='wspd', ax=ax2, color='r')
ax2.set_ylabel('wind speed (m/s)')

# PM2.5 vs wind direction
plt.figure(figsize=(16,4))
ax1 = sns.lineplot(data=data, x='time (iso)', y='pm25 (ug/m3)')
ax1.set_ylim([0, 200])
ax2 = ax1.twinx()
sns.lineplot(data=meteostatdf, x='time', y='wdir', ax=ax2, color='r')
ax2.set_ylabel('wind direction (degrees)')

meteostatdf_reindex = meteostatdf.reindex(index=data.index)
#data['wind speed (m/s)'] = meteostatdf['wspd'].interpolate('cubic')
#sns.kdeplot(data=data, x="waiting", y="duration")

#meteostatdf_reindex.interpolate('cubic')
meteostatdf


