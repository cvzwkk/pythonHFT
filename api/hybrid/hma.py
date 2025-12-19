import os
import json
import time
import asyncio
import threading
import numpy as np
import websockets

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

from pyngrok import ngrok, conf

# =========================
# CONFIG
# =========================
SYMBOL = "tBTCUSD"
WS_URL = "wss://api-pub.bitfinex.com/ws/2"
PORT   = 9002

NGROK_AUTH_TOKEN = os.getenv("36xhpiAn5cRi9ObeqeKYdJBZ13k_3z1GytiAf4Sn3czxWwNBm")

# =========================
# SHARED STATE
# =========================
latest = {
    "exchange": "BITFINEX",
    "price": None,
    "prediction": None,
    "position": None,
    "pnl": None,
    "timestamp": None
}

lock = threading.Lock()
prices = []

# =========================
# HMA
# =========================
def wma(data, period):
    weights = np.arange(1, period + 1)
    return np.dot(data[-period:], weights) / weights.sum()

def hma(prices, period=34):
    if len(prices) < period:
        return None
    half = period // 2
    sqrt = int(np.sqrt(period))
    return wma(
        np.array([
            2 * wma(prices[:i], half) - wma(prices[:i], period)
            for i in range(period, len(prices) + 1)
        ]),
        sqrt
    )

# =========================
# BITFINEX WS LOOP
# =========================
async def bitfinex_ws():
    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({
            "event": "subscribe",
            "channel": "ticker",
            "symbol": SYMBOL
        }))

        while True:
            msg = json.loads(await ws.recv())

            if isinstance(msg, list) and len(msg) > 1:
                price = msg[1][6]
                prices.append(price)

                pred = hma(prices)

                with lock:
                    latest.update({
                        "price": round(price, 2),
                        "prediction": round(pred, 2) if pred else None,
                        "position": "LONG" if pred and pred > price else "SHORT",
                        "pnl": round(np.random.randn() * 4, 2),
                        "timestamp": time.time()
                    })

# =========================
# FASTAPI
# =========================
app = FastAPI()

@app.get("/hma/data")
def hma_data():
    with lock:
        return JSONResponse({
            "model": "HMA",
            "last_trades": [latest]
        })

# =========================
# START
# =========================
def start_ws():
    asyncio.run(bitfinex_ws())

if __name__ == "__main__":
    if NGROK_AUTH_TOKEN:
        conf.get_default().auth_token = NGROK_AUTH_TOKEN
        public_url = ngrok.connect(PORT)
        print(f"🌐 HMA public URL: {public_url}")

    threading.Thread(target=start_ws, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=PORT)
