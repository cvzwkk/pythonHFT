import asyncio
import websockets
import json
from collections import deque
import numpy as np
import ctypes
import time

# =============================
# Load Rust SIMD library
# =============================
lib = ctypes.CDLL("./target/release/libsimd_model.so")

lib.sma_avx.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_size_t, ctypes.POINTER(ctypes.c_double)]
lib.ema_avx.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_size_t, ctypes.c_double, ctypes.POINTER(ctypes.c_double)]
lib.momentum.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_size_t, ctypes.c_size_t, ctypes.POINTER(ctypes.c_double)]

def sma(data):
    arr = np.ascontiguousarray(data, dtype=np.float64)
    out = np.zeros_like(arr)
    lib.sma_avx(arr.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), len(arr), out.ctypes.data_as(ctypes.POINTER(ctypes.c_double)))
    return out

def ema(data, alpha=0.2):
    arr = np.ascontiguousarray(data, dtype=np.float64)
    out = np.zeros_like(arr)
    lib.ema_avx(arr.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), len(arr), ctypes.c_double(alpha), out.ctypes.data_as(ctypes.POINTER(ctypes.c_double)))
    return out

def momentum(data, period=5):
    arr = np.ascontiguousarray(data, dtype=np.float64)
    out = np.zeros_like(arr)
    lib.momentum(arr.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), len(arr), period, out.ctypes.data_as(ctypes.POINTER(ctypes.c_double)))
    return out

# =============================
# Paper Trading Class
# =============================
# Paper Trading Class
# =============================
class PaperTrader:
    def __init__(self, symbol="tBTCUSD", candle_period="1m", balance=10000.0, max_orders=3):
        self.symbol = symbol
        self.candle_period = candle_period
        self.closes = deque(maxlen=100)
        self.uri = "wss://api-pub.bitfinex.com/ws/2"
        self.balance = balance
        self.max_orders = max_orders
        self.open_trades = []  # list of dicts: {'type': 'BUY'/'SELL', 'price': float, 'units': float}

        # Trade parameters
        self.add_loss_pct = 0.003   # 0.3%
        self.take_profit_pct = 0.009 # 0.9%

    async def _connect(self):
        while True:
            try:
                async with websockets.connect(self.uri) as ws:
                    await ws.send(json.dumps({
                        "event": "subscribe",
                        "channel": "candles",
                        "key": f"trade:{self.candle_period}:{self.symbol}"
                    }))
                    print(f"Subscribed to {self.symbol} {self.candle_period} candles.")

                    async for message in ws:
                        await self._handle_message(message)
            except Exception as e:
                print(f"Connection error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    async def _handle_message(self, message):
        try:
            msg = json.loads(message)
        except json.JSONDecodeError:
            return

        if not isinstance(msg, list) or len(msg) < 2:
            return

        data = msg[1]
        if data is None or data == "hb":
            return

        if isinstance(data, list) and len(data) > 0:
            if isinstance(data[0], list):
                candle = data[-1]
            elif len(data) >= 5:
                candle = data
            else:
                return
        else:
            return

        try:
            close = float(candle[4])
        except (ValueError, IndexError, TypeError):
            return

        self.closes.append(close)

        if len(self.closes) > 10:
            self._strategy(close)
            self._print_status(close)

    def _strategy(self, last_price):
        # Use simple Rust indicators
        arr = np.array(self.closes)
        sma_val = sma(arr)[-1]
        ema_val = ema(arr, alpha=0.2)[-1]
        mom_val = momentum(arr, period=5)[-1]

        # Decide trade direction
        signal = None
        if ema_val > sma_val and mom_val > 0:
            signal = "BUY"
        elif ema_val < sma_val and mom_val < 0:
            signal = "SELL"

        # Open new trade if we have signal and max orders not reached
        if signal and len(self.open_trades) < self.max_orders:
            self.open_trades.append({'type': signal, 'price': last_price, 'units': 1.0})

        # Update existing trades for scaling, take profit, or force close
        to_remove = []
        for trade in self.open_trades:
            if trade['type'] == "BUY":
                # Add units if price dropped by add_loss_pct
                if last_price <= trade['price'] * (1 - self.add_loss_pct):
                    trade['units'] += 1.0
                    trade['price'] = last_price  # update last entry price

                # Take profit
                elif last_price >= trade['price'] * (1 + self.take_profit_pct):
                    to_remove.append(trade)
                    self.balance += trade['units'] * (last_price - trade['price'])

                # Force close if profit > $1
                elif (last_price - trade['price']) * trade['units'] > 1.0:
                    to_remove.append(trade)
                    self.balance += trade['units'] * (last_price - trade['price'])

            elif trade['type'] == "SELL":
                # Add units if price increased by add_loss_pct
                if last_price >= trade['price'] * (1 + self.add_loss_pct):
                    trade['units'] += 1.0
                    trade['price'] = last_price

                # Take profit
                elif last_price <= trade['price'] * (1 - self.take_profit_pct):
                    to_remove.append(trade)
                    self.balance += trade['units'] * (trade['price'] - last_price)

                # Force close if profit > $1
                elif (trade['price'] - last_price) * trade['units'] > 1.0:
                    to_remove.append(trade)
                    self.balance += trade['units'] * (trade['price'] - last_price)

        # Remove closed trades
        for trade in to_remove:
            self.open_trades.remove(trade)

    def _print_status(self, last_price):
        # Compute unrealized PnL
        pnl = 0.0
        for trade in self.open_trades:
            if trade['type'] == "BUY":
                pnl += trade['units'] * (last_price - trade['price'])
            else:
                pnl += trade['units'] * (trade['price'] - last_price)

        print(f"[{time.strftime('%H:%M:%S')}] Price: {last_price:.2f} | Balance: {self.balance:.2f} | Open Trades: {len(self.open_trades)} | Unrealized PnL: {pnl:.2f}")
        for i, trade in enumerate(self.open_trades, 1):
            print(f"  Trade {i}: {trade['type']} {trade['units']} units at {trade['price']:.2f}")
        print("-"*60)

    def run(self):
        asyncio.run(self._connect())

# =============================
# Usage
# =============================
if __name__ == "__main__":
    trader = PaperTrader()
    trader.run()
