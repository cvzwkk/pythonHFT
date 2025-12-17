
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import pandas as pd
from datetime import datetime

# =========================
# PARAMETERS
# =========================
PAIR = "btcusd"           # Trading pair
INTERVAL = "60"           # Candle interval in seconds (60 = 1m, 3600 = 1h, etc.)
LIMIT = 1000              # Number of candles to fetch
FILENAME = "bitstamp_data.csv"

# =========================
# FETCH DATA
# =========================
url = f"https://www.bitstamp.net/api/v2/ohlc/{PAIR}/"
params = {
    "step": INTERVAL,
    "limit": LIMIT
}

response = requests.get(url, params=params)
data = response.json()

if "data" in data and "ohlc" in data["data"]:
    ohlc = data["data"]["ohlc"]

    # Convert to DataFrame
    df = pd.DataFrame(ohlc)
    df['timestamp'] = pd.to_datetime(df['timestamp'].astype(float), unit='s')
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    df = df.astype({'open': float, 'high': float, 'low': float, 'close': float, 'volume': float})

    # Save to CSV
    df.to_csv(FILENAME, index=False)
    print(f"Saved {len(df)} candles to {FILENAME}")
else:
    print("Failed to fetch data:", data)
