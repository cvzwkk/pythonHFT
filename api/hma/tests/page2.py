#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import requests
from pyngrok import ngrok, conf
import uvicorn

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

}

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Hull Live Trading Table</title>
<script src="https://cdn.plot.ly/plotly-2.30.0.min.js"></script>
<style>
body { 
    font-family: Arial; 
    margin: 20px; 
    background-color: #000; 
    color: #fff; 
}

table {
    border-collapse: collapse;
    width: 100%;
    margin-bottom: 30px;
    color: #fff;
}

th, td {
    border: 1px solid #555;
    padding: 8px;
    text-align: center;
}

th { 
    background-color: #222; 
    color: #fff;
}

td {
    background-color: #111;
}

.negative { color: #ff5555; }
.positive { color: #55ff55; }

/* =========================
   ADD TRADE ANIMATION
========================= */
@keyframes addFlash {
  from { background-color: #555500; }
  to   { background-color: #111; }
}

.add-trade {
  animation: addFlash 0.8s ease-out;
}

/* =========================
   CLOSE TRADE ANIMATION
========================= */
@keyframes closeWin {
  from { background-color: #005500; }
  to   { background-color: #111; }
}

@keyframes closeLoss {
  from { background-color: #550000; }
  to   { background-color: #111; }
}

.close-win  { animation: closeWin 1s ease-out; }
.close-loss { animation: closeLoss 1s ease-out; }

/* =========================
   PnL FLASH
========================= */
@keyframes pnlUp {
  from { background-color: #005500; }
  to   { background-color: #111; }
}

@keyframes pnlDown {
  from { background-color: #550000; }
  to   { background-color: #111; }
}

.pnl-up   { animation: pnlUp 0.6s ease-out; }
.pnl-down { animation: pnlDown 0.6s ease-out; }

#orderbookDepth {
    width: 100%;
    height: 420px;
    background-color: #000;
}
</style>
</head>
<body>

<h2>Live Trading Data</h2>
<p>Last updated: <span id="timestamp">-</span></p>
<p>
Balance: <span id="balance">-</span> |
Total PnL: <span id="total_pnl">-</span>
</p>

<table id="liveTable">
<thead>
<tr>
<th>Exchange</th>
<th>Price</th>
<th>Prediction</th>
<th>Position</th>
<th>PnL</th>
</tr>
</thead>
<tbody></tbody>
</table>

<h2>Last 50 Trades (Newest First)</h2>
<table id="tradeHistoryTable">
<thead>
<tr>
<th>Time</th>
<th>Exchange</th>
<th>Type</th>
<th>Side</th>
<th>Price</th>
<th>BTC Added</th>
<th>Total BTC</th>
<th>PnL</th>
</tr>
</thead>
<tbody></tbody>
</table>

<h2>Live Aggregated Orderbook Depth</h2>
<div id="orderbookDepth"></div>

<script>
let lastSeenTradeTime = null;
let lastTotalPnl = null;
let lastExchangePnl = {};
let depthReady = false;

function cumulative(levels) {
    let sum = 0;
    return levels.map(([p, s]) => { sum += s; return [p, sum]; });
}

function renderOrderbook(bids, asks) {
    const bidCum = cumulative(bids);
    const askCum = cumulative(asks);

    const bidTrace = { 
        x: bidCum.map(d=>d[0]), 
        y: bidCum.map(d=>d[1]),
        type:"scatter", mode:"lines", fill:"tozeroy", name:"Bids",
        line:{color:"rgb(0,180,0)", width:2}, fillcolor:"rgba(0,180,0,0.35)" 
    };

    const askTrace = { 
        x: askCum.map(d=>d[0]), 
        y: askCum.map(d=>d[1]),
        type:"scatter", mode:"lines", fill:"tozeroy", name:"Asks",
        line:{color:"rgb(220,0,0)", width:2}, fillcolor:"rgba(220,0,0,0.35)" 
    };

    const layout = { 
        margin:{l:60,r:20,t:20,b:40},
        xaxis:{title:"Price", color:"#fff"},
        yaxis:{title:"Cumulative BTC", color:"#fff"},
        legend:{orientation:"h", y:1.15},
        transition:{duration:400,easing:"cubic-in-out"},
        plot_bgcolor:"#000",
        paper_bgcolor:"#000",
    };

    if (!depthReady) {
        Plotly.newPlot("orderbookDepth",[bidTrace,askTrace],layout,{displayModeBar:false,responsive:true});
        depthReady = true;
    } else {
        Plotly.react("orderbookDepth",[bidTrace,askTrace],layout);
    }
}

async function updateTable() {
  try {
    const res = await fetch('/data');
    const data = await res.json();

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

@app.get("/", response_class=HTMLResponse)
def home():
    return HTML_PAGE

@app.get("/aggregated_data")
def aggregated_data():
    # Aggregate top 30 levels
    bids, asks = defaultdict(float), defaultdict(float)
    for book in ORDERBOOK.values():
        for p, s in book["bids"].items(): bids[p] += s
        for p, s in book["asks"].items(): asks[p] += s

    bids_sorted = sorted(bids.items(), key=lambda x: x[0], reverse=True)[:30]
    asks_sorted = sorted(asks.items(), key=lambda x: x[0])[:30]

    orderbook = [{"price": p, "total_bids": s, "total_asks": 0} for p, s in bids_sorted]
    for i, (p, s) in enumerate(asks_sorted):
        if i < len(orderbook):
            orderbook[i]["total_asks"] = s
        else:
            orderbook.append({"price": p, "total_bids": 0, "total_asks": s})

    trades_list = list(TRADES)

    return {"orderbook": orderbook, "trades": trades_list}

# =============================
# EXCHANGE WS FUNCTIONS
# =============================

async def binance_ws():
    url = "wss://stream.binance.com:9443/ws/btcusdt@depth@100ms"
    async with websockets.connect(url) as ws:
        async for msg in ws:
            d=json.loads(msg)
            book=ORDERBOOK["Binance"]
            for p,s in d.get("b",[]): p,s=float(p),float(s); book["bids"][p]=s if s!=0 else book["bids"].pop(p,None)
            for p,s in d.get("a",[]): p,s=float(p),float(s); book["asks"][p]=s if s!=0 else book["asks"].pop(p,None)

async def binance_trades_ws():
    url="wss://stream.binance.com:9443/ws/btcusdt@trade"
    async with websockets.connect(url) as ws:
        async for msg in ws:
            d=json.loads(msg)
            TRADES.appendleft({"time":d["T"],"exchange":"Binance","price":float(d["p"]),"quantity":float(d["q"]),"side":"BUY" if not d["m"] else "SELL"})


@app.get("/data")
def get_data():
    try:
        return requests.get(API_URL, timeout=5).json()
    except:
        return {
            "timestamp": "-",
            "balance": 0,
            "total_pnl": 0,
            "exchanges": {},
            "last_trades": []
        }

# =============================
# MAIN
# =============================
if __name__ == "__main__":
    public_url = ngrok.connect(addr=LOCAL_PORT, bind_tls=True)
    print(f"Public URL: {public_url}")
    print(f"Ngrok dashboard port: {NGROK_DASHBOARD_PORT}")
    loop = asyncio.get_event_loop()
    # Binance WS tasks
    loop.create_task(binance_ws())
    loop.create_task(binance_trades_ws())
    uvicorn.run(app, host="0.0.0.0", port=LOCAL_PORT)
