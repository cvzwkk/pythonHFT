#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import requests
from pyngrok import ngrok, conf
import uvicorn
import asyncio
import json
import websockets
from collections import defaultdict

# =========================
# GLOBAL ORDERBOOK STORAGE
# =========================
ORDERBOOK = defaultdict(lambda: {"bids": {}, "asks": {}})

# =========================
# COINBASE WS
# =========================
async def coinbase_ws():
    async with websockets.connect("wss://ws-feed.exchange.coinbase.com") as ws:
        await ws.send(json.dumps({
            "type": "subscribe",
            "channels": [{"name": "level2", "product_ids": ["BTC-USD"]}]
        }))
        async for msg in ws:
            data = json.loads(msg)
            book = ORDERBOOK["Coinbase"]
            if data.get("type") == "snapshot":
                book["bids"] = {float(p): float(s) for p, s in data.get("bids", [])}
                book["asks"] = {float(p): float(s) for p, s in data.get("asks", [])}
            elif data.get("type") == "l2update":
                for side, p, s in data.get("changes", []):
                    p, s = float(p), float(s)
                    side_str = side + "s"
                    if s == 0:
                        book[side_str].pop(p, None)
                    else:
                        book[side_str][p] = s

# =========================
# KRAKEN WS
# =========================
async def kraken_ws():
    async with websockets.connect("wss://ws.kraken.com") as ws:
        await ws.send(json.dumps({
            "event": "subscribe",
            "pair": ["XBT/USD"],
            "subscription": {"name": "book", "depth": 10}
        }))
        async for msg in ws:
            data = json.loads(msg)
            if isinstance(data, list):
                book = ORDERBOOK["Kraken"]
                for item in data:
                    if isinstance(item, dict):
                        for side in ("b", "a"):
                            if side in item:
                                for p, s, *_ in item[side]:
                                    book["bids" if side == "b" else "asks"][float(p)] = float(s)

# =========================
# BITSTAMP WS
# =========================
async def bitstamp_ws():
    async with websockets.connect("wss://ws.bitstamp.net") as ws:
        await ws.send(json.dumps({
            "event": "bts:subscribe",
            "data": {"channel": "order_book_btcusd"}
        }))
        async for msg in ws:
            data = json.loads(msg)
            if data.get("event") == "data":
                book = ORDERBOOK["Bitstamp"]
                book["bids"] = {float(p): float(s) for p, s in data["data"]["bids"]}
                book["asks"] = {float(p): float(s) for p, s in data["data"]["asks"]}

# =========================
# BITFINEX WS
# =========================
async def bitfinex_ws():
    async with websockets.connect("wss://api-pub.bitfinex.com/ws/2") as ws:
        await ws.send(json.dumps({
            "event": "subscribe",
            "channel": "book",
            "symbol": "tBTCUSD",
            "prec": "P0",
            "len": 25
        }))
        async for msg in ws:
            data = json.loads(msg)
            if isinstance(data, list) and len(data) > 1:
                book = ORDERBOOK["Bitfinex"]
                payload = data[1]
                if isinstance(payload[0], list):
                    for p, c, s in payload:
                        (book["bids"] if s > 0 else book["asks"])[float(p)] = abs(s)
                else:
                    p, c, s = payload
                    (book["bids"] if s > 0 else book["asks"])[float(p)] = abs(s)

# =========================
# RUN ALL WS
# =========================
async def run_ws():
    await asyncio.gather(
        coinbase_ws(),
        kraken_ws(),
        bitstamp_ws(),
        bitfinex_ws()
    )

# =============================
# CONFIG
# =============================
NGROK_AUTH_TOKEN = "36xkALQDnxGLwLU3o1CIo2SKsvt_7cUEHiQnMbNC2Snv5bfKk"
NGROK_DASHBOARD_PORT = 4041
LOCAL_PORT = 8080

API_URL = "https://tiesha-nonfissile-jarvis.ngrok-free.dev/live"

if NGROK_AUTH_TOKEN:
    conf.get_default().auth_token = NGROK_AUTH_TOKEN
conf.get_default().ngrok_port = NGROK_DASHBOARD_PORT

# =============================
# FASTAPI
# =============================
app = FastAPI()

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Hull Live Trading Table</title>
<script src="https://cdn.plot.ly/plotly-2.30.0.min.js"></script>
<style>
body { font-family: Arial; margin: 20px; }
table { border-collapse: collapse; width: 100%; margin-bottom: 30px; }
th, td { border: 1px solid #ccc; padding: 8px; text-align: center; }
th { background-color: #f4f4f4; }
.negative { color: red; }
.positive { color: green; }
@keyframes addFlash { from { background-color: #ffffcc; } to { background-color: transparent; } }
.add-trade { animation: addFlash 0.8s ease-out; }
@keyframes closeWin { from { background-color: #ccffcc; } to { background-color: transparent; } }
@keyframes closeLoss { from { background-color: #ffcccc; } to { background-color: transparent; } }
.close-win { animation: closeWin 1s ease-out; }
.close-loss { animation: closeLoss 1s ease-out; }
@keyframes pnlUp { from { background-color: #ccffcc; } to { background-color: transparent; } }
@keyframes pnlDown { from { background-color: #ffcccc; } to { background-color: transparent; } }
.pnl-up { animation: pnlUp 0.6s ease-out; }
.pnl-down { animation: pnlDown 0.6s ease-out; }
</style>
</head>
<body>

<h2>Live Trading Data</h2>
<p>Last updated: <span id="timestamp">-</span></p>
<p>Balance: <span id="balance">-</span> | Total PnL: <span id="total_pnl">-</span></p>

<table id="liveTable">
<thead>
<tr><th>Exchange</th><th>Price</th><th>Prediction</th><th>Position</th><th>PnL</th></tr>
</thead>
<tbody></tbody>
</table>

<h2>Last 50 Trades (Newest First)</h2>
<table id="tradeHistoryTable">
<thead>
<tr><th>Time</th><th>Exchange</th><th>Type</th><th>Side</th><th>Price</th><th>BTC Added</th><th>Total BTC</th><th>PnL</th></tr>
</thead>
<tbody></tbody>
</table>

<h2>Live Orderbook Depth (Aggregated)</h2>
<h2>Live Orderbook Depth (Aggregated)</h2>
<div id="orderbookDepth" style="width:100%;height:420px;"></div>

<script>
let depthReady = false;
let lastBids = [];
let lastAsks = [];

// Compute cumulative volume
function cumulative(levels) {
    let sum = 0;
    return levels.map(([p, s]) => { sum += s; return [p, sum]; });
}

// Compare old vs new levels and mark updated points
function highlightChanges(oldLevels, newLevels) {
    let colors = new Array(newLevels.length).fill('rgba(0,0,0,0)'); // default transparent
    const oldMap = new Map(oldLevels.map(([p,s]) => [p,s]));

    newLevels.forEach(([p,s], idx) => {
        if(!oldMap.has(p) || oldMap.get(p) !== s){
            colors[idx] = 'yellow'; // highlight updated points
        }
    });
    return colors;
}

// Render orderbook with flash for changes
function renderOrderbook(bids, asks) {
    const bidCum = cumulative(bids);
    const askCum = cumulative(asks);

    const bidColors = highlightChanges(lastBids, bids);
    const askColors = highlightChanges(lastAsks, asks);

    const bidTrace = { 
        x: bidCum.map(d=>d[0]), 
        y: bidCum.map(d=>d[1]),
        type:"scatter", mode:"lines+markers", fill:"tozeroy", name:"Bids",
        line:{color:"rgb(0,180,0)", width:2}, 
        marker:{color:bidColors, size:6},
        fillcolor:"rgba(0,180,0,0.35)" 
    };

    const askTrace = { 
        x: askCum.map(d=>d[0]), 
        y: askCum.map(d=>d[1]),
        type:"scatter", mode:"lines+markers", fill:"tozeroy", name:"Asks",
        line:{color:"rgb(220,0,0)", width:2}, 
        marker:{color:askColors, size:6},
        fillcolor:"rgba(220,0,0,0.35)" 
    };

    const layout = { 
        margin:{l:60,r:20,t:20,b:40},
        xaxis:{title:"Price"}, 
        yaxis:{title:"Cumulative BTC"},
        legend:{orientation:"h", y:1.15},
        transition:{duration:400,easing:"cubic-in-out"} 
    };

    if(!depthReady){
        Plotly.newPlot("orderbookDepth",[bidTrace, askTrace], layout, {displayModeBar:false,responsive:true});
        depthReady = true;
    } else {
        Plotly.react("orderbookDepth",[bidTrace, askTrace], layout);
    }

    // Remove flash after 400ms
    setTimeout(()=>{
        bidTrace.marker.color = new Array(bids.length).fill('rgb(0,180,0)');
        askTrace.marker.color = new Array(asks.length).fill('rgb(220,0,0)');
        Plotly.react("orderbookDepth",[bidTrace, askTrace], layout);
    }, 400);

    lastBids = bids;
    lastAsks = asks;
}

// Fetch /orderbook from backend
async function updateOrderbook() {
    try{
        const obRes = await fetch('/orderbook'); 
        const obData = await obRes.json();

        let bids=[], asks=[];
        for(const ex of Object.values(obData)){
            if(ex.bids) bids.push(...ex.bids);
            if(ex.asks) asks.push(...ex.asks);
        }

        bids = bids.sort((a,b)=>b[0]-a[0]).slice(0,30);
        asks = asks.sort((a,b)=>a[0]-b[0]).slice(0,30);

        if(bids.length && asks.length) renderOrderbook(bids, asks);

    }catch(e){ console.error("ORDERBOOK ERROR:", e); }
}

// Update every 500ms for smooth animation
setInterval(updateOrderbook, 500);
updateOrderbook();
</script>

<script>
async function updateTable() {
    try {
        const res = await fetch('/data'); const data = await res.json();

        // Header
        document.getElementById('timestamp').textContent = data.timestamp ?? '-';
        document.getElementById('balance').textContent = Number(data.balance ?? 0).toFixed(2);
        const totalPnlEl = document.getElementById('total_pnl');
        const totalPnl = Number(data.total_pnl ?? 0);
        totalPnlEl.textContent = totalPnl.toFixed(6);
        totalPnlEl.className = totalPnl>=0?'positive':'negative';
        if(lastTotalPnl!==null){ totalPnlEl.classList.add(totalPnl>lastTotalPnl?'pnl-up':'pnl-down'); }
        lastTotalPnl = totalPnl;

        // Live positions
        const liveBody = document.querySelector('#liveTable tbody'); liveBody.innerHTML='';
        for(const [exchange, info] of Object.entries(data.exchanges||{})){
            const pnl = Number(info.pnl??0);
            const row = document.createElement('tr');
            let pnlFlash = ''; if(lastExchangePnl[exchange]!==undefined){ pnlFlash = pnl>lastExchangePnl[exchange]? 'pnl-up':'pnl-down';}
            lastExchangePnl[exchange] = pnl;
            row.innerHTML = `<td>${exchange}</td><td>${Number(info.price??0).toFixed(2)}</td><td>${info.prediction!==null?Number(info.prediction).toFixed(2):'-'}</td><td>${info.position??'-'}</td><td class="${pnl>=0?'positive':'negative'} ${pnlFlash}">${pnl.toFixed(6)}</td>`;
            liveBody.appendChild(row);
        }

        // Trade history
        const thBody = document.querySelector('#tradeHistoryTable tbody'); thBody.innerHTML='';
        const trades = [...(data.last_trades||[])].reverse();
        for(const trade of trades){
            const row = document.createElement('tr');
            if(lastSeenTradeTime && trade.time>lastSeenTradeTime){
                row.classList.add(trade.type==='CLOSE'? (trade.pnl>=0?'close-win':'close-loss'):'add-trade');
            }
            row.innerHTML = `<td>${trade.time}</td><td>${trade.exchange}</td><td>${trade.type}</td><td>${trade.side}</td><td>${Number(trade.price??0).toFixed(2)}</td><td>${trade.btc_added?.toFixed(8)||'-'}</td><td>${trade.total_btc?.toFixed(8)||'-'}</td><td class="${trade.pnl>=0?'positive':'negative'}">${trade.pnl?.toFixed(6)||'-'}</td>`;
            thBody.appendChild(row);
        }
        if(trades.length>0) lastSeenTradeTime = trades[0].time;

        // Orderbook depth
        try{
            const obRes = await fetch('/orderbook'); const obData = await obRes.json();
            let bids=[], asks=[];
            for(const ex of Object.values(obData)){
                bids.push(...(ex.bids||[]));
                asks.push(...(ex.asks||[]));
            }
            bids = bids.sort((a,b)=>b[0]-a[0]).slice(0,30);
            asks = asks.sort((a,b)=>a[0]-b[0]).slice(0,30);
            if(bids.length && asks.length) renderOrderbook(bids, asks);
        }catch(e){console.error("ORDERBOOK ERROR:",e);}

    }catch(err){console.error("LIVE UPDATE ERROR:",err);}
}

setInterval(updateTable,1000);
updateTable();
</script>
</body>
</html>
"""

# =============================
# ROUTES
# =============================
@app.get("/", response_class=HTMLResponse)
def home():
    return HTML_PAGE

@app.get("/data")
def get_data():
    try:
        return requests.get(API_URL, timeout=5).json()
    except:
        return {"timestamp":"-","balance":0,"total_pnl":0,"exchanges":{},"last_trades":[]}

@app.get("/orderbook")
def orderbook():
    out = {}
    for ex, book in ORDERBOOK.items():
        out[ex] = {
            "bids": sorted(book["bids"].items(), reverse=True)[:30],
            "asks": sorted(book["asks"].items())[:30]
        }
    return out

# =============================
# MAIN
# =============================
if __name__ == "__main__":
    public_url = ngrok.connect(addr=LOCAL_PORT, bind_tls=True)
    print(f"Public URL: {public_url}")
    print(f"Ngrok dashboard port: {NGROK_DASHBOARD_PORT}")

    # Start websocket aggregation in background
    loop = asyncio.get_event_loop()
    loop.create_task(run_ws())

    uvicorn.run(app, host="0.0.0.0", port=LOCAL_PORT)
