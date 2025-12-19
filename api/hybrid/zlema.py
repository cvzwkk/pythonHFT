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
PORT   = 9001

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
# ZLEMA
# =========================
def zlema(prices, period=20):
    if len(prices) < period:
        return None
    lag = (period - 1) // 2
    adjusted = np.array(prices[-period:]) + (
        np.array(prices[-period:]) - np.array(prices[-period-lag:-lag])
    )
    return adjusted.mean()

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

                pred = zlema(prices)

                with lock:
                    latest.update({
                        "price": round(price, 2),
                        "prediction": round(pred, 2) if pred else None,
                        "position": "LONG" if pred and pred > price else "SHORT",
                        "pnl": round(np.random.randn() * 5, 2),
                        "timestamp": time.time()
                    })

# =========================
# FASTAPI
# =========================
app = FastAPI()

@app.get("/zlema/data")
def zlema_data():
    with lock:
        return JSONResponse({
            "model": "ZLEMA",
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
        print(f"🌐 ZLEMA public URL: {public_url}")

    threading.Thread(target=start_ws, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=PORT)
