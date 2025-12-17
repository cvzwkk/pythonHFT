#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import pandas as pd
from datetime import datetime, timezone, timedelta

PAIR = "btcusd"
N = 1000  # Number of 1-second candles you want
FILENAME = "btcusd_1s.csv"

# =========================
# FETCH RECENT TRADES
# =========================
url = f"https://www.bitstamp.net/api/v2/transactions/{PAIR}/"
params = {"time": "minute"}  # Fetch last trades (Bitstamp returns last ~1000 trades)
response = requests.get(url, params=params)
data = response.json()

if not data:
    raise Exception("Failed to fetch trades")

# =========================
# BUILD 1-SECOND CANDLES
# =========================
candles = {}
for trade in data:
    ts = datetime.fromtimestamp(float(trade['date']), tz=timezone.utc)
    sec = ts.replace(microsecond=0)
    price = float(trade['price'])
    volume = float(trade['amount'])

    if sec not in candles:
        candles[sec] = {
            'open': price,
            'high': price,
            'low': price,
            'close': price,
            'volume': volume
        }
    else:
        c = candles[sec]
        c['high'] = max(c['high'], price)
        c['low'] = min(c['low'], price)
        c['close'] = price
        c['volume'] += volume

# =========================
# SORT AND KEEP LAST N
# =========================
df = pd.DataFrame([
    {'timestamp': k, **v} for k, v in candles.items()
])
df.sort_values('timestamp', inplace=True)
df = df.tail(N)  # Keep last N candles

# =========================
# SAVE TO CSV
# =========================
df.to_csv(FILENAME, index=False)
print(f"Saved {len(df)} 1-second candles to {FILENAME}")
