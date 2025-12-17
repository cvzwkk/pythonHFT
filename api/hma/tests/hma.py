#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import aiohttp
import numpy as np
import pandas as pd
from collections import deque
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pyngrok import ngrok
import uvicorn
import os

# =========================
# NGROK
# =========================
NGROK_AUTHTOKEN = "36xhpiAn5cRi9ObeqeKYdJBZ13k_3z1GytiAf4Sn3czxWwNBm"
ngrok.set_auth_token(NGROK_AUTHTOKEN)

# =========================
# EXCHANGES & UTILS
# =========================
ORDERBOOK_APIS = {
    "Coinbase": "https://api.exchange.coinbase.com/products/BTC-USD/book?level=2",
    "Kraken": "https://api.kraken.com/0/public/Depth?pair=XBTUSD&count=10",
    "Bitstamp": "https://www.bitstamp.net/api/v2/order_book/btcusd/",
    "Bitfinex": "https://api.bitfinex.com/v1/book/btcusd"
}

def safe_return(v):
    return None if v is None or np.isnan(v) or np.isinf(v) else float(v)

def log_returns(prices):
    return np.diff(np.log(prices + 1e-8))

def micro_price(bid, ask, bid_sz, ask_sz):
    return (ask * bid_sz + bid * ask_sz) / (bid_sz + ask_sz + 1e-8)

# =========================
# HMA MODELS
# =========================
def predict_hma_robust(prices, period=58):
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

def predict_hma_robust2(prices, period=10):
    return predict_hma_robust(prices, period=period)

MODELS = {
    "HMA": predict_hma_robust,
    "HMA2": predict_hma_robust2,
}

# =========================
# PAPER TRADER
# =========================
class PaperTrader:
    def __init__(self, balance=1000):
        self.balance = balance
        self.positions = {e: None for e in ORDERBOOK_APIS}
        self.pnl = {e: 0.0 for e in ORDERBOOK_APIS}
        self.trade_history = deque(maxlen=50)
        self.trading_halted = False
        self.default_size = 0.5
        self.next_size = self.default_size

    def open_trade(self, ex, side, price):
        if self.balance <= 0 or self.trading_halted:
            return

        if self.positions[ex] is None:
            self.positions[ex] = {
                "side": side,
                "entry": price,
                "size": self.next_size,
                "trailing_stop": None
            }
            self.trade_history.append({
                "exchange": ex,
                "type": "ENTRY",
                "side": side.upper(),
                "price": price,
                "size": self.next_size,
                "pnl": None,
                "time": datetime.now().strftime("%H:%M:%S")
            })

    def close_trade(self, ex, price):
        pos = self.positions[ex]
        if pos:
            size = pos["size"]
            side = pos["side"]
            entry = pos["entry"]

            pnl = (price - entry) * size if side == "buy" else (entry - price) * size
            pnl_pct = (price - entry)/entry if side == "buy" else (entry - price)/entry

            self.balance += pnl
            self.pnl[ex] += pnl
            self.positions[ex] = None

            # Dynamic size adjustments
            if pnl_pct >= 0.03 / 100:
                self.next_size = max(0.05, self.next_size * 0.65)
            elif pnl_pct <= -0.02 / 100:
                self.next_size = self.next_size * 1.24
            else:
                self.next_size = self.default_size

            self.trade_history.append({
                "exchange": ex,
                "type": "EXIT",
                "side": side.upper(),
                "price": price,
                "size": size,
                "pnl": pnl,
                "time": datetime.now().strftime("%H:%M:%S")
            })

            if self.balance <= 0:
                self.trading_halted = True
                print(f"⚠️ Balance is negative ({self.balance}), trading halted.")

    def total_pnl(self):
        return sum(self.pnl.values())

# =========================
# FETCH ORDERBOOK
# =========================
async def fetch_price(ex, url, session):
    try:
        async with session.get(url, timeout=5) as r:
            d = await r.json()
            if ex == "Coinbase":
                bid, bid_sz = map(float, d["bids"][0])
                ask, ask_sz = map(float, d["asks"][0])
            elif ex == "Kraken":
                book = list(d["result"].values())[0]
                bid, bid_sz = map(float, book["bids"][0][:2])
                ask, ask_sz = map(float, book["asks"][0][:2])
            elif ex == "Bitstamp":
                bid, bid_sz = float(d["bids"][0][0]), float(d["bids"][0][1])
                ask, ask_sz = float(d["asks"][0][0]), float(d["asks"][0][1])
            else:  # Bitfinex
                bid = float(d["bids"][0]["price"])
                bid_sz = float(d["bids"][0]["amount"])
                ask = float(d["asks"][0]["price"])
                ask_sz = float(d["asks"][0]["amount"])
            return ex, micro_price(bid, ask, bid_sz, ask_sz)
    except:
        return ex, None

# =========================
# GLOBAL STATE
# =========================
history = {e: deque(maxlen=60) for e in ORDERBOOK_APIS}
trader = PaperTrader()
latest_results = {}

# =========================
# TRADING PARAMETERS
# =========================
MAX_OPEN_TRADES = 8
TAKE_PROFIT_PCT = 0.09 / 100
STOP_LOSS_PCT = 0.04 / 100
STOP_LOSS_USD = 40
TRAIL_START_PCT = 0.03 / 100
TRAIL_OFFSET_PCT = 0.015 / 100

# =========================
# PRICE UPDATES + TRADING LOGIC
# =========================
async def update_prices():
    global latest_results
    async with aiohttp.ClientSession() as session:
        while True:
            results = await asyncio.gather(*[
                fetch_price(e, u, session) for e, u in ORDERBOOK_APIS.items()
            ])
            for ex, price in results:
                if price is None:
                    continue

                history[ex].append(price)

                pred_hma = MODELS["HMA"](list(history[ex])) if len(history[ex]) >= 12 else None
                pred_hma2 = MODELS["HMA2"](list(history[ex])) if len(history[ex]) >= 12 else None

                pos = trader.positions[ex]
                status = pos["side"].upper() if pos else "-"

                open_trades_count = sum(1 for p in trader.positions.values() if p is not None)

                # Decision logic: model + last price
                if pred_hma is not None and open_trades_count < MAX_OPEN_TRADES:
                    if pos is None:
                        if pred_hma > price and price > min(pred_hma, pred_hma2):
                            trader.open_trade(ex, "buy", price)
                            status = "BUY"
                        elif pred_hma < price and price < max(pred_hma, pred_hma2):
                            trader.open_trade(ex, "sell", price)
                            status = "SELL"

                # Manage open trades: TP, SL, trailing stop
                if pos:
                    entry = pos["entry"]
                    side = pos["side"]
                    size = pos.get("size", 1.0)

                    pnl_usd = (price - entry) * size if side == "buy" else (entry - price) * size
                    pnl_pct = (price - entry)/entry if side == "buy" else (entry - price)/entry

                    # Take profit
                    tp_trigger = pnl_pct >= TAKE_PROFIT_PCT
                    # Stop loss
                    sl_trigger = pnl_pct <= -STOP_LOSS_PCT or pnl_usd <= -STOP_LOSS_USD

                    # Trailing stop
                    if pnl_pct >= TRAIL_START_PCT:
                        if side == "buy":
                            new_trail = price * (1 - TRAIL_OFFSET_PCT)
                            if pos["trailing_stop"] is None or new_trail > pos["trailing_stop"]:
                                pos["trailing_stop"] = new_trail
                        else:
                            new_trail = price * (1 + TRAIL_OFFSET_PCT)
                            if pos["trailing_stop"] is None or new_trail < pos["trailing_stop"]:
                                pos["trailing_stop"] = new_trail

                    trail_hit = False
                    if pos["trailing_stop"] is not None:
                        if (side == "buy" and price <= pos["trailing_stop"]) or (side == "sell" and price >= pos["trailing_stop"]):
                            trail_hit = True

                    if tp_trigger or sl_trigger or trail_hit:
                        trader.close_trade(ex, price)
                        status = "-"

                latest_results[ex] = {
                    "price": price,
                    "prediction_hma": pred_hma,
                    "prediction_hma2": pred_hma2,
                    "position": status,
                    "pnl": trader.pnl[ex]
                }

            await asyncio.sleep(1)

# =========================
# FASTAPI
# =========================
app = FastAPI(title="BTC Live Microprice API")

@app.get("/live")
async def live_data():
    trades = list(trader.trade_history)
    return JSONResponse({
        "timestamp": datetime.now().isoformat(),
        "balance": trader.balance,
        "total_pnl": trader.total_pnl(),
        "exchanges": latest_results,
        "last_trades": trades
    })

# =========================
# SILENT FASTAPI
# =========================
import logging
logging.getLogger("uvicorn").setLevel(logging.CRITICAL)  # suppress logs

# =========================
# CONSOLE DASHBOARD
# =========================
async def dashboard_loop():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"⏱ {datetime.now().strftime('%H:%M:%S')}")
        print(f"💰 Balance: {trader.balance:.2f} USD | Total PnL: {trader.total_pnl():.2f} USD | Next Size: {trader.next_size:.4f} BTC")
        print("-"*60)
        print("Exchange | Price | Position | PnL | Prediction HMA | Prediction HMA2")
        for ex, data in latest_results.items():
            price = data.get("price")
            pos = data.get("position")
            pnl = data.get("pnl")
            pred1 = data.get("prediction_hma")
            pred2 = data.get("prediction_hma2")
            print(f"{ex:<10} {price:>10.2f} {pos:^8} {pnl:>8.2f} {pred1:>12.2f} {pred2:>12.2f}")
        print("-"*60)
        print("Last 5 Trades:")
        for t in list(trader.trade_history)[-5:]:
            print(f"{t['time']} | {t['exchange']:<8} | {t['side']:<4} | {t['price']:.2f} | {t['size']:.4f} BTC | PnL: {t['pnl']}")
        await asyncio.sleep(1)

# =========================
# MAIN ENTRY
# =========================
async def main():
    # Start background tasks
    asyncio.create_task(update_prices())
    asyncio.create_task(dashboard_loop())

    # Start FastAPI silently
    public_url = ngrok.connect(8000, "http")
    print(f"🚀 Public URL: {public_url}")
    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000, log_level="critical")  # silent
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
