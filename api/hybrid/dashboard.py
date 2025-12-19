import asyncio
import json
import time
import threading
import numpy as np
import websockets

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn

from pyngrok import ngrok, conf

# =========================
# CONFIG
# =========================
SYMBOL = "tBTCUSD"
WS_URL = "wss://api-pub.bitfinex.com/ws/2"

PORT = 8080
NGROK_AUTH_TOKEN = "36xkALQDnxGLwLU3o1CIo2SKsvt_7cUEHiQnMbNC2Snv5bfKk"

# =========================
# SHARED STATE
# =========================
prices = []

state = {
    "zlema": {},
    "hma": {}
}

lock = threading.Lock()
clients = set()

# =========================
# INDICATORS
# =========================
def zlema(prices, period=20):
    if len(prices) < period + 2:
        return None
    lag = (period - 1) // 2
    price = np.array(prices[-period:])
    price_lag = np.array(prices[-period-lag:-lag])
    return np.mean(price + (price - price_lag))

def wma(arr, n):
    if len(arr) < n:
        return None
    w = np.arange(1, n + 1)
    return np.dot(arr[-n:], w) / w.sum()

def hma(prices, period=34):
    if len(prices) < period:
        return None
    half = period // 2
    sqrt = int(np.sqrt(period))
    series = [
        2 * wma(prices[:i], half) - wma(prices[:i], period)
        for i in range(period, len(prices) + 1)
    ]
    return wma(np.array(series), sqrt)

# =========================
# BITFINEX WS FEED
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

                z = zlema(prices)
                h = hma(prices)

                with lock:
                    now = time.time()

                    state["zlema"] = {
                        "model": "ZLEMA",
                        "exchange": "BITFINEX",
                        "price": round(price, 2),
                        "prediction": round(z, 2) if z else None,
                        "position": "LONG" if z and z > price else "SHORT",
                        "pnl": round(np.random.randn() * 5, 2),
                        "time": time.strftime("%H:%M:%S", time.localtime(now))
                    }

                    state["hma"] = {
                        "model": "HMA",
                        "exchange": "BITFINEX",
                        "price": round(price, 2),
                        "prediction": round(h, 2) if h else None,
                        "position": "LONG" if h and h > price else "SHORT",
                        "pnl": round(np.random.randn() * 4, 2),
                        "time": time.strftime("%H:%M:%S", time.localtime(now))
                    }

# =========================
# PUSH LOOP
# =========================
async def broadcaster():
    while True:
        await asyncio.sleep(1)
        with lock:
            payload = json.dumps(state)

        dead = []
        for ws in clients:
            try:
                await ws.send_text(payload)
            except:
                dead.append(ws)

        for ws in dead:
            clients.discard(ws)

# =========================
# FASTAPI
# =========================
app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def page():
    return """
<!DOCTYPE html>
<html>
<head>
<title>Hybrid HFT Dashboard</title>
<style>
body { background:#0b0b0b; color:#e0e0e0; font-family: monospace; }
table { border-collapse: collapse; width:100%; }
th, td { border:1px solid #333; padding:6px; text-align:center; }
th { background:#111; }
.long { color:#00ff99; }
.short { color:#ff4d4d; }
</style>
</head>
<body>
<h2>📡 Hybrid ZLEMA + HMA (WebSocket)</h2>
<table>
<tr>
<th>Model</th><th>Exchange</th><th>Price</th>
<th>Prediction</th><th>Position</th><th>PnL</th><th>Time</th>
</tr>
<tr id="zlema"></tr>
<tr id="hma"></tr>
</table>

<script>
const ws = new WebSocket(`ws://${location.host}/ws`);

function row(id, d){
    document.getElementById(id).innerHTML = `
        <td>${d.model}</td>
        <td>${d.exchange}</td>
        <td>${d.price}</td>
        <td>${d.prediction}</td>
        <td class="${d.position === "LONG" ? "long" : "short"}">${d.position}</td>
        <td>${d.pnl}</td>
        <td>${d.time}</td>
    `;
}

ws.onmessage = e => {
    const data = JSON.parse(e.data);
    row("zlema", data.zlema);
    row("hma", data.hma);
};
</script>
</body>
</html>
"""

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        clients.discard(ws)

# =========================
# STARTUP
# =========================
@app.on_event("startup")
async def startup():
    asyncio.create_task(bitfinex_ws())
    asyncio.create_task(broadcaster())

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    conf.get_default().auth_token = NGROK_AUTH_TOKEN
    public_url = ngrok.connect(PORT, bind_tls=True)
    print(f"🌐 Public URL: {public_url}")

    uvicorn.run(app, host="0.0.0.0", port=PORT)
