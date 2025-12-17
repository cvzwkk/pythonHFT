
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np

# =========================
# SAFE RETURN FUNCTION
# =========================
def safe_return(x):
    return x if x is not None else 0.0

# =========================
# HMA ROBUST MODEL
# =========================
def predict_hma_robust(prices, period=16):
    if len(prices) < 4:
        return None
    prices = np.array(prices, dtype=np.float64)
    prices = pd.Series(prices).ffill().bfill().values

    def wma(arr, n):
        n = min(len(arr), n)
        weights = np.arange(1, n + 1)
        return np.dot(arr[-n:], weights) / weights.sum()

    half = max(2, period // 2)
    half = min(half, len(prices))
    period = min(period, len(prices))

    hma = 2 * wma(prices, half) - wma(prices, period)

    slope_len = min(half, len(prices)-1)
    slope = np.polyfit(np.arange(slope_len+1), prices[-slope_len-1:], 1)[0]

    returns = np.diff(np.log(prices + 1e-9))
    momentum = np.sum(np.exp(-np.linspace(0,3,len(returns))) * returns) if len(returns) > 1 else 0.0
    vol = np.std(returns[-half:]) + 1e-9
    vol_boost = np.tanh(vol * 80)
    log_prices = np.log(prices + 1e-9)
    z = (log_prices[-1] - log_prices.mean()) / (np.std(log_prices) + 1e-9)
    mr_factor = np.tanh(-0.3 * z)
    forecast = hma + slope * (1 + vol_boost) + momentum * 0.5 + mr_factor * vol * 0.3
    return safe_return(forecast)

# =========================
# LOAD DATA
# =========================
FILENAME = "bitstamp_data.csv"
df = pd.read_csv(FILENAME)
prices = df['close'].values.astype(float)
n = len(prices)

# =========================
# VECTORIZED HMA BACKTEST
# =========================
def backtest_hma(prices, periods=range(5, 101)):
    results = []
    for period in periods:
        ma = np.full(n, np.nan)
        for i in range(period, n+1):
            ma[i-1] = predict_hma_robust(prices[i-period:i], period)
        # simple trading logic
        cash, position, holdings = 10000, 0, 0
        for i in range(n):
            if np.isnan(ma[i]):
                continue
            # Buy
            if prices[i] > ma[i] and position == 0:
                holdings = cash / prices[i]
                cash = 0
                position = 1
            # Sell
            elif prices[i] < ma[i] and position == 1:
                cash = holdings * prices[i]
                holdings = 0
                position = 0
        if position == 1:
            cash = holdings * prices[-1]
        results.append((period, cash))
    # Sort by performance
    results.sort(key=lambda x: x[1], reverse=True)
    return results

# =========================
# RUN BACKTEST
# =========================
top_results = backtest_hma(prices, periods=range(5, 101))
print("Top 10 HMA periods by final balance:")
for period, balance in top_results[:10]:
    print(f"Period: {period}, Final Balance: {balance:.2f}")
