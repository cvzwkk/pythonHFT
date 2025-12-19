import asyncio
import json
import time
import requests
import threading
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn

from pyngrok import ngrok, conf

# =========================
# CONFIG
# =========================
NGROK_AUTH_TOKEN = "36xkALQDnxGLwLU3o1CIo2SKsvt_7cUEHiQnMbNC2Snv5bfKk"

PORT = 8080

ZLEMA_API = "http://127.0.0.1:9001/zlema/data"
HMA_API   = "http://127.0.0.1:9002/hma/data"

PUSH_INTERVAL = 1  # seconds

# =========================
# FASTAPI
# =========================
app = FastAPI()
clients = set()

# =========================
# HELPERS
# =========================
def fetch(url):
    try:
        return requests.get(url, timeout=0.8).json()
    except Exception as e:
        return {"error": str(e)}

def normalize(model):
    t = model.get("last_trades", [{}])[0]
    return {
        "model": model.get("model"),
        "exchange": t.get("exchange"),
        "price": t.get("price"),
        "prediction": t.get("prediction"),
        "position": t.get("position"),
        "pnl": t.get("pnl"),
        "time": time.strftime("%H:%M:%S", time.localtime(t.get("timestamp", 0)))
    }

# =========================
# PUSH LOOP
# =========================
async def broadcaster():
    while True:
        payload = {
            "zlema": normalize(fetch(ZLEMA_API)),
            "hma":   normalize(fetch(HMA_API))
        }

        dead = []
        for ws in clients:
            try:
                await ws.send_text(json.dumps(payload))
            except:
                dead.append(ws)

        for ws in dead:
            clients.discard(ws)

        await asyncio.sleep(PUSH_INTERVAL)

# =========================
# ROUTES
# =========================
@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """
<!DOCTYPE html>
<html>
<head>
<title>HFT Live Dashboard</title>
<style>
body {
    background:#0b0b0b;
    color:#e0e0e0;
    font-family: monospace;
}
table {
    border-collapse: collapse;
    width:100%;
}
th, td {
    border:1px solid #333;
    padding:6px;
    text-align:center;
}
th {
    background:#111;
}
.long { color:#00ff99; }
.short { color:#ff4d4d; }
</style>
</head>
<body>
<h2>📡 Live Trading Models (WebSocket)</h2>

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

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    row("zlema", data.zlema);
    row("hma", data.hma);
};
</script>
</body>
</html>
"""

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
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
async def startup_event():
    asyncio.create_task(broadcaster())

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    conf.get_default().auth_token = NGROK_AUTH_TOKEN
    public_url = ngrok.connect(PORT, bind_tls=True)
    print(f"🌐 Public Dashboard: {public_url}")

    uvicorn.run(app, host="0.0.0.0", port=PORT)
