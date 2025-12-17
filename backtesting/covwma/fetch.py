
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np

# =========================
# LOAD DATA
# =========================
FILENAME = "bitstamp_data.csv"
df = pd.read_csv(FILENAME)
prices = df['close'].values.astype(float)
n = len(prices)

# =========================
# VECTORIZE COVWMA
# =========================
def covwma_vectorized(prices, max_period=100):
    """Compute CovWMA for all periods 1..max_period"""
    all_ma = np.full((max_period, n), np.nan)  # rows=period, cols=time

    for period in range(1, max_period + 1):
        if n < period:
            continue
        # Create rolling windows
        shape = (n - period + 1, period)
        strides = prices.strides[0]
        windows = np.lib.stride_tricks.as_strided(prices, shape=shape, strides=(strides, strides))
        # Compute weights: abs deviation from mean + epsilon
        weights = np.abs(windows - windows.mean(axis=1, keepdims=True)) + 1e-8
        ma = np.sum(windows * weights, axis=1) / np.sum(weights, axis=1)
        # Pad NaN at the beginning
        all_ma[period-1, period-1:] = ma
    return all_ma

# =========================
# VECTOR BACKTEST
# =========================
def backtest_vectorized(prices, all_ma):
    """Backtest all periods at once. Returns final balances."""
    n_periods = all_ma.shape[0]
    final_balances = np.zeros(n_periods)
    initial_cash = 10000

    for p in range(n_periods):
        ma = all_ma[p]
        position = 0
        cash = initial_cash
        holdings = 0
        for i in range(len(prices)):
            if np.isnan(ma[i]):
                continue
            # Buy signal
            if prices[i] > ma[i] and position == 0:
                holdings = cash / prices[i]
                cash = 0
                position = 1
            # Sell signal
            elif prices[i] < ma[i] and position == 1:
                cash = holdings * prices[i]
                holdings = 0
                position = 0
        if position == 1:
            cash = holdings * prices[-1]
        final_balances[p] = cash
    return final_balances

# =========================
# RUN
# =========================
max_period = 100
all_ma = covwma_vectorized(prices, max_period)
balances = backtest_vectorized(prices, all_ma)

# Top 10 periods
top_indices = np.argsort(balances)[::-1][:10]
print("Top 10 CovWMA periods by final balance:")
for idx in top_indices:
    print(f"Period: {idx+1}, Final Balance: {balances[idx]:.2f}")
