#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# =========================
# IMPORTS
# =========================
import asyncio
import aiohttp
import numpy as np
import pandas as pd
from collections import deque
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
import os
import json
import logging
from numba import njit

import nest_asyncio
nest_asyncio.apply()

# =========================
# UTILS
# =========================
def safe_return(v):
    if v is None or np.isnan(v) or np.isinf(v):
        return None
    return float(v)

def log_returns(prices):
    return np.diff(np.log(prices + 1e-8))

# =========================
# NUMBA HELPERS
# =========================
@njit(fastmath=True)
def wma_numba(arr, n):
    n = min(arr.shape[0], n)
    weights_sum = n * (n + 1) / 2
    acc = 0.0
    w = 1.0
    for i in range(arr.shape[0] - n, arr.shape[0]):
        acc += arr[i] * w
        w += 1.0
    return acc / weights_sum

@njit(fastmath=True)
def slope_numba(arr, n):
    n = min(n, arr.shape[0] - 1)
    x_mean = n * 0.5
    y_mean = 0.0
    for i in range(n + 1):
        y_mean += arr[arr.shape[0] - 1 - i]
    y_mean /= (n + 1)
    num = 0.0
    den = 0.0
    for i in range(n + 1):
        x = i - x_mean
        y = arr[arr.shape[0] - 1 - i] - y_mean
        num += x * y
        den += x * x
    return num / (den + 1e-12)

@njit(fastmath=True)
def momentum_numba(returns):
    s = 0.0
    decay = 1.0
    for i in range(returns.shape[0] - 1, -1, -1):
        s += returns[i] * decay
        decay *= 0.95
    return s

# =========================
# COVEMA MODEL
# =========================
@njit(fastmath=True)
def covema_core(prices, period, cov_factor=0.3):
    length = prices.shape[0]
    period = min(period, length)
    alpha = 2.0 / (period + 1)
    ema = prices[0]
    for i in range(1, length):
        ema = alpha * prices[i] + (1 - alpha) * ema
    returns = np.empty(length - 1)
    for i in range(length - 1):
        returns[i] = np.log(prices[i + 1] + 1e-9) - np.log(prices[i] + 1e-9)
    cov_adj = 0.0
    if len(returns) >= 2:
        mean_r = np.mean(returns[-period:])
        cov = 0.0
        for i in range(len(returns) - period, len(returns)):
            cov += (returns[i] - mean_r) * (prices[i + 1] - ema)
        cov /= period
        cov_adj = cov_factor * cov
    return ema + cov_adj

def predict_covema(prices, period=58):
    if len(prices) < 4:
        return None
    prices = np.asarray(prices, dtype=np.float64)
    val = covema_core(prices, period)
    if np.isnan(val) or np.isinf(val):
        return None
    return float(val)

def predict_covema_fast(prices, period=10):
    return predict_covema(prices, period)

# =========================
# REGISTER HMA MODELS
# =========================
MODELS = {
    "HMA": predict_covema,       # main HMA model
    "HMA2": predict_covema_fast  # fast HMA
}

# =========================
# JUNX PARMA (adaptive EMA)
# =========================
@njit(fastmath=True)
def junx_parma_core(prices, period):
    alpha = 2.0 / (period + 1)
    ema = prices[0]
    for i in range(1, prices.shape[0]):
        delta = prices[i] - ema
        alpha_adapt = alpha * (1 + 0.5 * np.tanh(delta))
        ema = alpha_adapt * prices[i] + (1 - alpha_adapt) * ema
    return ema

def predict_junx(prices, period=20):
    if len(prices) < 4:
        return None
    return float(junx_parma_core(np.asarray(prices, np.float64), period))


# =========================
# ICHIMOKU (Tenkan/Kijun cross)
# =========================
@njit(fastmath=True)
def ichimoku_core(prices, tenkan=9, kijun=26):
    n = prices.shape[0]
    if n < kijun:
        return prices[-1]
    high_t = np.max(prices[-tenkan:])
    low_t = np.min(prices[-tenkan:])
    tenkan_sen = 0.5 * (high_t + low_t)
    high_k = np.max(prices[-kijun:])
    low_k = np.min(prices[-kijun:])
    kijun_sen = 0.5 * (high_k + low_k)
    return tenkan_sen + (tenkan_sen - kijun_sen)

def predict_ichimoku(prices):
    return float(ichimoku_core(np.asarray(prices, np.float64)))


# =========================
# HZLOG (log-price slope)
# =========================
@njit(fastmath=True)
def hzlog_core(prices, period=20):
    n = min(period, prices.shape[0])
    logp = np.log(prices[-n:])
    x = np.arange(n)
    x_mean = np.mean(x)
    y_mean = np.mean(logp)
    num = 0.0
    den = 0.0
    for i in range(n):
        num += (x[i] - x_mean) * (logp[i] - y_mean)
        den += (x[i] - x_mean) ** 2
    slope = num / (den + 1e-12)
    return np.exp(logp[-1] + slope)

def predict_hzlog(prices, period=20):
    return float(hzlog_core(np.asarray(prices, np.float64), period))


# =========================
# RIBBON AVERAGES (multiple EMAs)
# =========================
@njit(fastmath=True)
def ribbon_core(prices, periods=np.array([8, 13, 21, 34])):
    ema_sum = 0.0
    n = len(periods)
    for i in range(n):
        p = periods[i]
        alpha = 2.0 / (p + 1)
        ema = prices[0]
        for j in range(1, prices.shape[0]):
            ema = alpha * prices[j] + (1 - alpha) * ema
        ema_sum += ema
    return ema_sum / n

def predict_ribbon(prices):
    return float(ribbon_core(np.asarray(prices, np.float64)))


# =========================
# T3 TILSON (triple EMA smoothing)
# =========================
@njit(fastmath=True)
def t3_core(prices, period=10, vfactor=0.7):
    n = prices.shape[0]
    alpha = 2.0 / (period + 1)
    e1 = e2 = e3 = e4 = e5 = e6 = prices[0]
    for i in range(1, n):
        p = prices[i]
        e1 = alpha * p + (1 - alpha) * e1
        e2 = alpha * e1 + (1 - alpha) * e2
        e3 = alpha * e2 + (1 - alpha) * e3
        e4 = alpha * e3 + (1 - alpha) * e4
        e5 = alpha * e4 + (1 - alpha) * e5
        e6 = alpha * e5 + (1 - alpha) * e6
    c1 = -vfactor ** 3
    c2 = 3 * vfactor ** 2 + 3 * vfactor ** 3
    c3 = -6

# =========================
# PAPER TRADER (DCA ENGINE)
# =========================
class PaperTrader:
    def __init__(self, balance=1000):
        self.initial_balance = balance
        self.balance = balance
        self.positions = {e: None for e in ORDERBOOK_APIS}
        self.pnl = {e: 0.0 for e in ORDERBOOK_APIS}
        self.trade_history = deque(maxlen=200)

        # ---- risk controls ----
        self.trading_halted = False
        self.max_adds = 9
        self.global_equity_stop_pct = -0.25  # -25%

        # ---- DCA params ----
        self.entry_size = 0.00039370  # BTC
        self.add_ratio = 0.289         # 28.9% of total BTC
        self.adjust_step_pct = 0.068 / 100  # 0.001%
        self.take_profit_pct = 0.0035 / 100  # 0.0035%

    # =========================
    # FORCE CLOSE
    # =========================
    def force_close(self, ex, price, reason):
        pos = self.positions[ex]
        if pos is None:
            return

        side = pos["side"]
        size = pos["total_btc"]
        avg = pos["avg_entry"]

        pnl = (price - avg) * size if side == "buy" else (avg - price) * size

        self.balance += pnl
        self.pnl[ex] += pnl
        self.positions[ex] = None

        self.trade_history.append({
            "exchange": ex,
            "type": f"FORCE_EXIT_{reason}",
            "side": side.upper(),
            "price": price,
            "btc": size,
            "pnl": pnl,
            "time": datetime.now().strftime("%H:%M:%S")
        })

    # =========================
    # GLOBAL EQUITY STOP
    # =========================
    def check_global_equity_stop(self, prices):
        equity = self.balance
        for ex, pos in self.positions.items():
            if pos is None or ex not in prices:
                continue
            price = prices[ex]
            side = pos["side"]
            size = pos["total_btc"]
            avg = pos["avg_entry"]
            unreal = (price - avg) * size if side == "buy" else (avg - price) * size
            equity += unreal

        drawdown = (equity - self.initial_balance) / self.initial_balance
        if drawdown <= self.global_equity_stop_pct:
            for ex, pos in list(self.positions.items()):
                if pos is not None and ex in prices:
                    self.force_close(ex, prices[ex], "GLOBAL_EQUITY_STOP")
            self.trading_halted = True
            return True
        return False

    # =========================
    # OPEN / ADD TRADE
    # =========================
    def open_trade(self, ex, side, price):
        if self.trading_halted:
            return

        pos = self.positions[ex]

        # ---- NEW ENTRY ----
        if pos is None:
            btc = self.entry_size
            self.positions[ex] = {
                "side": side,
                "avg_entry": price,
                "total_btc": btc,
                "adds": 0,
                "entries": 1,
                "tp_price": price * (1 + self.take_profit_pct) if side == "buy" else price * (1 - self.take_profit_pct),
                "next_add_price": price * (1 - self.adjust_step_pct) if side == "buy" else price * (1 + self.adjust_step_pct)
            }
            self.trade_history.append({
                "exchange": ex,
                "type": "ENTRY",
                "side": side.upper(),
                "price": price,
                "btc": btc,
                "pnl": None,
                "time": datetime.now().strftime("%H:%M:%S")
            })
            return

        # ---- HARD ADD LIMIT ----
        if pos["adds"] >= self.max_adds:
            self.force_close(ex, price, "MAX_ADDS")
            return

        side = pos["side"]
        should_add = (side == "buy" and price <= pos["next_add_price"]) or (side == "sell" and price >= pos["next_add_price"])
        if not should_add:
            return

        # ---- SCALE-IN ----
        added_btc = pos["total_btc"] * self.add_ratio
        new_total_btc = pos["total_btc"] + added_btc
        new_avg = (pos["avg_entry"] * pos["total_btc"] + price * added_btc) / new_total_btc

        pos["avg_entry"] = new_avg
        pos["total_btc"] = new_total_btc
        pos["adds"] += 1
        pos["entries"] += 1
        pos["tp_price"] = new_avg * (1 + self.take_profit_pct) if side == "buy" else new_avg * (1 - self.take_profit_pct)
        pos["next_add_price"] = price * (1 - self.adjust_step_pct) if side == "buy" else price * (1 + self.adjust_step_pct)

        self.trade_history.append({
            "exchange": ex,
            "type": "ADD",
            "side": side.upper(),
            "price": price,
            "btc_added": added_btc,
            "total_btc": new_total_btc,
            "pnl": None,
            "time": datetime.now().strftime("%H:%M:%S")
        })

    # =========================
    # TAKE PROFIT
    # =========================
    def check_close_trade(self, ex, price):
        pos = self.positions[ex]
        if pos is None:
            return

        side = pos["side"]
        tp = pos["tp_price"]
        hit_tp = price >= tp if side == "buy" else price <= tp
        if hit_tp:
            self.force_close(ex, price, "TP")

    # =========================
    # TOTAL PNL
    # =========================
    def total_pnl(self):
        return sum(self.pnl.values())

# =========================
# GLOBAL STATE
# =========================
history = {e: deque(maxlen=60) for e in ORDERBOOK_APIS}
latest_results = {}

trader = PaperTrader()
load_state(trader)

MAX_OPEN_TRADES = 3

# =========================
# FETCH MICROPRICE
# =========================
async def fetch_price(ex, url, session):
    try:
        async with session.get(url, timeout=5) as r:
            data = await r.json()
            if ex == "Bitfinex":
                bid = float(data["bids"][0]["price"])
                bid_sz = abs(float(data["bids"][0]["amount"]))
                ask = float(data["asks"][0]["price"])
                ask_sz = abs(float(data["asks"][0]["amount"]))
            else:
                # Extend here for other exchanges if needed
                bid = ask = bid_sz = ask_sz = 0.0
            price = micro_price(bid, ask, bid_sz, ask_sz)
            return ex, price
    except Exception:
        return ex, None

# =========================
# TRADING LOOP WITH AGGREGATED SIGNAL
# =========================
async def update_prices():
    global latest_results
    async with aiohttp.ClientSession() as session:
        while True:
            results = await asyncio.gather(*[
                fetch_price(ex, url, session)
                for ex, url in ORDERBOOK_APIS.items()
            ])

            prices = {}

            for ex, price in results:
                if price is None:
                    continue
                prices[ex] = price
                history[ex].append(price)

                # ----- Compute all model predictions -----
                preds = {}
                for name, func in MODELS.items():
                    preds[f"pred_{name.lower()}"] = func(list(history[ex])) if len(history[ex]) >= 12 else None

                pos = trader.positions[ex]

                # ----- Aggregated Signal -----
                # Simple system: count bullish vs bearish signals
                bullish = 0
                bearish = 0
                for k, v in preds.items():
                    if v is None:
                        continue
                    if v > price:
                        bullish += 1
                    elif v < price:
                        bearish += 1

                # Primary signal: +1 buy, -1 sell, 0 no action
                if bullish > bearish:
                    primary_signal = "buy"
                elif bearish > bullish:
                    primary_signal = "sell"
                else:
                    primary_signal = None

                latest_results[ex] = {
                    "price": price,
                    **preds,
                    "primary_signal": primary_signal,
                    "position": pos["side"].upper() if pos else "-",
                    "entries": pos["entries"] if pos else 0,
                    "adds": pos["adds"] if pos else 0,
                    "pnl": trader.pnl[ex]
                }

            # ----- Global Equity Stop -----
            if trader.check_global_equity_stop(prices):
                save_state(trader)
                await asyncio.sleep(1)
                continue

            # ----- Take Profit Check -----
            for ex, pos in trader.positions.items():
                if pos is not None and ex in prices:
                    trader.check_close_trade(ex, prices[ex])

            # ----- Open / Scale Trades -----
            open_trades = sum(1 for p in trader.positions.values() if p is not None)
            for ex, price in prices.items():
                pos = trader.positions[ex]
                signal = latest_results[ex]["primary_signal"]

                # New Entry Logic: only open if primary signal exists and slots available
                if pos is None and signal is not None and open_trades < MAX_OPEN_TRADES:
                    trader.open_trade(ex, signal, price)
                    open_trades += 1

                # Scale-in existing trades using same logic
                elif pos is not None:
                    trader.open_trade(ex, pos["side"], price)

            save_state(trader)
            await asyncio.sleep(1)

import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pyngrok import ngrok
import uvicorn
from datetime import datetime

logging.getLogger("uvicorn").setLevel(logging.CRITICAL)

app = FastAPI(title="BTC Live Microprice API with Aggregated Signals")


# =========================
# COMPUTE TOTALS
# =========================
def compute_trade_totals():
    """
    Counts ENTRY + ADD only (no exits).
    Returns BTC + USD totals per exchange.
    """
    totals = {}
    for t in trader.trade_history:
        ex = t["exchange"]
        if t["type"] not in ("ENTRY", "ADD"):
            continue
        btc = t.get("btc") or t.get("btc_added") or 0.0
        usd = btc * t["price"]
        if ex not in totals:
            totals[ex] = {"btc_total": 0.0, "usd_total": 0.0, "entries": 0, "adds": 0}
        totals[ex]["btc_total"] += btc
        totals[ex]["usd_total"] += usd
        if t["type"] == "ENTRY":
            totals[ex]["entries"] += 1
        else:
            totals[ex]["adds"] += 1
    return totals


# =========================
# FASTAPI ENDPOINT
# =========================
@app.get("/live")
async def live_data():
    return JSONResponse({
        "timestamp": datetime.now().isoformat(),
        "balance": trader.balance,
        "total_pnl": trader.total_pnl(),
        "totals": compute_trade_totals(),
        "exchanges": latest_results,
        "last_trades": list(trader.trade_history)[-20:]
    })


# =========================
# MAIN ASYNC RUNNER
# =========================
async def main():
    # Start trading loop
    asyncio.create_task(update_prices())

    # Expose public URL (ngrok)
    public_url = ngrok.connect(8003, "http")
    print(f"🌐 Public URL: {public_url}")

    # Start FastAPI server
    config = uvicorn.Config(app=app, host="0.0.0.0", port=8003, log_level="critical")
    server = uvicorn.Server(config)
    await server.serve()


# =========================
# ENTRY POINT
# =========================
if __name__ == "__main__":
    asyncio.run(main())
