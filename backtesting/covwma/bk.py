#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import aiohttp
import websockets
import json
import numpy as np
import pandas as pd
from datetime import datetime
import os

# =========================
# SETTINGS
# =========================
SYMBOL = 'btcusd'
WS_URL = f"wss://ws.bitstamp.net"
HIST_FILE = f"{SYMBOL}_historical.csv"
MAX_PERIOD = 999

# =========================
# FUNCTIONS
# =========================

async def fetch_historical():
    """Fetch max available historical OHLC data from Bitstamp REST API or load from local CSV."""
    if os.path.exists(HIST_FILE):
        print(f"Loading historical data from {HIST_FILE}")
        df = pd.read_csv(HIST_FILE)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        return df

    print("Fetching historical data from Bitstamp...")
    all_data = []
    step = 1000
    offset = 0
    while True:
        url = f"https://www.bitstamp.net/api/v2/ohlc/{SYMBOL}/?step=60&limit={step}&offset={offset}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                ohlc = data['data']['ohlc']
                if not ohlc:
                    break
                all_data.extend(ohlc)
                offset += step

    df = pd.DataFrame(all_data)
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    df.sort_values('timestamp', inplace=True)
    df.reset_index(drop=True, inplace=True)

    # Save locally
    df.to_csv(HIST_FILE, index=False)
    print(f"Saved historical data to {HIST_FILE}")
    return df

def covwma(prices, volumes, period):
    """Compute CovWMA for a given period."""
    covwma_values = []
    for i in range(len(prices)):
        if i < period - 1:
            covwma_values.append(np.nan)
        else:
            price_slice = prices[i-period+1:i+1]
            volume_slice = volumes[i-period+1:i+1]
            covwma_values.append(np.sum(price_slice*volume_slice)/np.sum(volume_slice))
    return np.array(covwma_values)

def backtest(df):
    """Backtest CovWMA strategy for periods 1 → MAX_PERIOD."""
    results = {}
    prices = df['close'].values
    volumes = df['volume'].values
    
    for period in range(1, MAX_PERIOD+1):
        cvwma = covwma(prices, volumes, period)
        signals = np.where(prices > cvwma, 1, -1)  # Buy if price > CovWMA, sell otherwise
        pnl = np.diff(prices) * signals[:-1]       # Simple PnL calculation
        results[period] = np.nansum(pnl)
    return results

async def main():
    df = await fetch_historical()
    print(f"Data rows: {len(df)}")

    print("Starting backtest...")
    results = backtest(df)
    
    best_period = max(results, key=results.get)
    print(f"Best CovWMA period: {best_period}, PnL: {results[best_period]:.2f}")

    # =========================
    # OPTIONAL: LIVE WEBSOCKET
    # =========================
    async with websockets.connect(WS_URL) as ws:
        subscribe_msg = {
            "event": "bts:subscribe",
            "data": {"channel": f"live_trades_{SYMBOL}"}
        }
        await ws.send(json.dumps(subscribe_msg))
        print("Subscribed to live trades...")
        async for message in ws:
            data = json.loads(message)
            if 'data' in data and 'price' in data['data']:
                price = float(data['data']['price'])
                print(f"[LIVE] {datetime.utcnow()} Price: {price}")

# =========================
# RUN
# =========================
if __name__ == "__main__":
    asyncio.run(main())
