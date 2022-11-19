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
datafiles = [os.path.join(dataroot, f) for f in os.listdir(dataroot) if re.match(sensorID+r'.*\.csv', f)]
first = True
for csvfile in datafiles:
    if first:
        data = pd.read_csv(csvfile)
        first = False
    else:
        data = pd.concat([data, pd.read_csv(csvfile)])
data["datetime"] = pd.to_datetime(data["time (iso)"])
data

corrtempdf = pd.read_csv(os.path.join(dataroot, 'correct_temperature.csv'))
corrtempdf['datetime'] = pd.to_datetime(corrtempdf["time (iso)"])

sns.lineplot(data=data, x='datetime', y='temperature (C)')
sns.lineplot(data=corrtempdf, x='datetime', y='temperature (C)')

sns.lineplot(data=data, x='datetime', y='pm25 (ug/m3)')

sns.lineplot(data=data, x='datetime', y='pm10 (ug/m3)')


