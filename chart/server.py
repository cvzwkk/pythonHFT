import asyncio
import json
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from collections import deque
import aiohttp
import uvicorn

app = FastAPI()

# Serve static HTML
app.mount("/web", StaticFiles(directory="web"), name="web")

# Store live trades
live_trades = deque(maxlen=500)
clients = []

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.append(websocket)
    try:
        while True:
            await asyncio.sleep(1)
    except:
        clients.remove(websocket)

async def broadcast_trade(trade):
    for ws in clients:
        if ws.client_state == ws.CONNECTED:
            await ws.send_text(json.dumps(trade))

async def fetch_binance_trades():
    url = "wss://stream.binance.com:9443/ws/btcusdt@aggTrade"
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(url) as ws:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    trade = {
                        "price": float(data["p"]),
                        "qty": float(data["q"]),
                        "side": "BUY" if not data["m"] else "SELL",
                        "time": data["T"]
                    }
                    live_trades.append(trade)
                    await broadcast_trade(trade)

async def main_loop():
    await fetch_binance_trades()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(main_loop())
    uvicorn.run(app, host="0.0.0.0", port=6060)
