#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np

# =========================
# SAFE RETURN FUNCTION
# =========================
def safe_return(x):
    return x if np.isfinite(x) else 0

# =========================
# LOAD DATA
# =========================
FILENAME = "bitstamp_data.csv"
df = pd.read_csv(FILENAME)
prices = df['close'].values.astype(float)
n = len(prices)

# =========================
# VECTORIZED ZLEMA
# =========================
def zlema_series(prices, period):
    """Compute ZLEMA over full price series"""
    if len(prices) < period * 2:
        return np.full_like(prices, np.nan)
    
    lag = (period - 1) // 2
    alpha = 2 / (period + 1)
    
    zlema = np.zeros_like(prices)
    zlema[0] = prices[0]
    
    for i in range(1, n):
        if i - lag - 1 >= 0:
            adj = prices[i] + (prices[i] - prices[i - lag - 1])
        else:
            adj = prices[i]
        zlema[i] = safe_return(alpha * adj + (1 - alpha) * zlema[i-1])
    return zlema

# =========================
# BACKTEST FUNCTION
# =========================
def backtest(prices, ma):
    position = 0
    cash = 10000
    holdings = 0
    for i in range(len(prices)):
        if np.isnan(ma[i]):
            continue
        # BUY
        if prices[i] > ma[i] and position == 0:
            holdings = cash / prices[i]
            cash = 0
            position = 1
        # SELL
        elif prices[i] < ma[i] and position == 1:
            cash = holdings * prices[i]
            holdings = 0
            position = 0
    if position == 1:
        cash = holdings * prices[-1]
    return cash

# =========================
# RUN BACKTEST FOR MULTIPLE PERIODS
# =========================
max_period = 100
results = []

for period in range(1, max_period + 1):
    ma = zlema_series(prices, period)
    final_balance = backtest(prices, ma)
    results.append((period, final_balance))

# Sort by performance
results.sort(key=lambda x: x[1], reverse=True)

# =========================
# PRINT TOP 10
# =========================
print("Top 10 ZLEMA periods by final balance:")
for period, balance in results[:10]:
    print(f"Period: {period}, Final Balance: {balance:.2f}")
