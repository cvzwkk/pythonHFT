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
import json
import logging

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

STATE_FILE = "trader_state.json"

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
        self.last_close_time = {e: 0 for e in ORDERBOOK_APIS}  # timestamp of last closed trade

    def open_trade(self, ex, side, price):
        now = datetime.now().timestamp()
        # Check 1-second delay since last close
        if now - self.last_close_time.get(ex, 0) < 1:
            return

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

            # Store timestamp of last close
            self.last_close_time[ex] = datetime.now().timestamp()

            # Dynamic size adjustments
            if pnl_pct >= 0.03 / 100:
                self.next_size = max(0.05, self.next_size * 0.65)
            elif pnl_pct <= -0.002 / 100:
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
# SAVE & LOAD STATE
# =========================
def save_state(trader):
    state = {
        "balance": trader.balance,
        "trade_history": list(trader.trade_history),
        "pnl": trader.pnl,
        "next_size": trader.next_size
    }
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def load_state(trader):
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            trader.balance = state.get("balance", trader.balance)
            trader.pnl = state.get("pnl", trader.pnl)
            trader.next_size = state.get("next_size", trader.next_size)
            trader.trade_history = deque(state.get("trade_history", []), maxlen=50)

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
load_state(trader)
latest_results = {}

# =========================
# TRADING PARAMETERS
# =========================
MAX_OPEN_TRADES = 4
TAKE_PROFIT_PCT = 0.02 / 100
STOP_LOSS_PCT = 0.0001 / 100
STOP_LOSS_USD = 1
TRAIL_START_PCT = 0.03 / 100
TRAIL_OFFSET_PCT = 0.015 / 100

# =========================
# TRADING LOOP
# =========================
async def update_prices():
    global latest_results
    async with aiohttp.ClientSession() as session:
        while True:
            # Fetch all prices
            results = await asyncio.gather(*[
                fetch_price(e, u, session) for e, u in ORDERBOOK_APIS.items()
            ])
            
            # First, update history and predictions
            for ex, price in results:
                if price is None:
                    continue
                history[ex].append(price)

                pred_hma = MODELS["HMA"](list(history[ex])) if len(history[ex]) >= 12 else None
                pred_hma2 = MODELS["HMA2"](list(history[ex])) if len(history[ex]) >= 12 else None

                latest_results[ex] = {
                    "price": price,
                    "prediction_hma": pred_hma,
                    "prediction_hma2": pred_hma2,
                    "position": trader.positions[ex]["side"].upper() if trader.positions[ex] else "-",
                    "pnl": trader.pnl[ex]
                }

            # Second, evaluate **all trades simultaneously**
            for ex, pos in list(trader.positions.items()):
                if pos is None:
                    continue

                price = latest_results[ex]["price"]
                entry = pos["entry"]
                side = pos["side"]
                size = pos.get("size", 1.0)

                pnl_usd = (price - entry) * size if side == "buy" else (entry - price) * size
                pnl_pct = (price - entry)/entry if side == "buy" else (entry - price)/entry

                # Take profit and stop-loss triggers
                tp_trigger = pnl_pct >= TAKE_PROFIT_PCT
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

                trail_hit = pos["trailing_stop"] is not None and (
                    (side == "buy" and price <= pos["trailing_stop"]) or
                    (side == "sell" and price >= pos["trailing_stop"])
                )

                # Close trade if any trigger occurs
                if tp_trigger or sl_trigger or trail_hit:
                    trader.close_trade(ex, price)
                    latest_results[ex]["position"] = "-"
            
            # Third, open new trades if allowed (after all closes)
            open_trades_count = sum(1 for p in trader.positions.values() if p is not None)
            for ex, price in results:
                if price is None:
                    continue
                pos = trader.positions[ex]
                pred_hma = latest_results[ex]["prediction_hma"]
                pred_hma2 = latest_results[ex]["prediction_hma2"]

                if pred_hma is not None and pos is None and open_trades_count < MAX_OPEN_TRADES:
                    # Buy
                    if pred_hma > price and price > min(pred_hma, pred_hma2):
                        trader.open_trade(ex, "buy", price)
                        latest_results[ex]["position"] = "BUY"
                        open_trades_count += 1
                    # Sell
                    elif pred_hma < price and price < max(pred_hma, pred_hma2):
                        trader.open_trade(ex, "sell", price)
                        latest_results[ex]["position"] = "SELL"
                        open_trades_count += 1

            # Persist state
            save_state(trader)
            await asyncio.sleep(1)

# =========================
# DASHBOARD
# =========================
async def dashboard_loop():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"⏱ {datetime.now().strftime('%H:%M:%S')}")
        print(f"💰 Balance: {trader.balance:.2f} USD | Total PnL: {trader.total_pnl():.2f} USD | Next Size: {trader.next_size:.4f} BTC")
        print("-"*70)
        print("Exchange | Price | Position | PnL | Prediction HMA | Prediction HMA2")
        for ex, data in latest_results.items():
            price = data.get("price", 0)
            pos = data.get("position", "-")
            pnl = data.get("pnl", 0)
            pred1 = data.get("prediction_hma", 0)
            pred2 = data.get("prediction_hma2", 0)
            print(f"{ex:<10} {price:>10.2f} {pos:^8} {pnl:>8.2f} {pred1:>12.2f} {pred2:>12.2f}")
        print("-"*70)
        print("Last 5 Trades:")
        for t in list(trader.trade_history)[-5:]:
            print(f"{t['time']} | {t['exchange']:<8} | {t['side']:<4} | {t['price']:.2f} | {t['size']:.4f} BTC | PnL: {t['pnl']}")
        await asyncio.sleep(0)

# =========================
# FASTAPI
# =========================
logging.getLogger("uvicorn").setLevel(logging.CRITICAL)  # suppress logs
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
# MAIN
# =========================
async def main():
    asyncio.create_task(update_prices())
    asyncio.create_task(dashboard_loop())

    public_url = ngrok.connect(8000, "http")
    print(f"🚀 Public URL: {public_url}")

    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000, log_level="critical")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
