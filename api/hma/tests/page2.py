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

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Hull Live Trading Table</title>

<style>
body { font-family: Arial; margin: 20px; }

table {
  border-collapse: collapse;
  width: 100%;
  margin-bottom: 30px;
}

th, td {
  border: 1px solid #ccc;
  padding: 8px;
  text-align: center;
}

th { background-color: #f4f4f4; }

.negative { color: red; }
.positive { color: green; }

/* =========================
   ADD TRADE ANIMATION
========================= */
@keyframes addFlash {
  from { background-color: #ffffcc; }
  to   { background-color: transparent; }
}

.add-trade {
  animation: addFlash 0.8s ease-out;
}

/* =========================
   CLOSE TRADE ANIMATION
========================= */
@keyframes closeWin {
  from { background-color: #ccffcc; }
  to   { background-color: transparent; }
}

@keyframes closeLoss {
  from { background-color: #ffcccc; }
  to   { background-color: transparent; }
}

.close-win  { animation: closeWin 1s ease-out; }
.close-loss { animation: closeLoss 1s ease-out; }

/* =========================
   PnL FLASH
========================= */
@keyframes pnlUp {
  from { background-color: #ccffcc; }
  to   { background-color: transparent; }
}

@keyframes pnlDown {
  from { background-color: #ffcccc; }
  to   { background-color: transparent; }
}

.pnl-up   { animation: pnlUp 0.6s ease-out; }
.pnl-down { animation: pnlDown 0.6s ease-out; }
</style>
</head>

<body>

<h2>Live Trading Data</h2>

<p>Last updated: <span id="timestamp">-</span></p>
<p>
Balance: <span id="balance">-</span> |
Total PnL: <span id="total_pnl">-</span>
</p>

<!-- LIVE POSITIONS -->
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

<script>
let lastSeenTradeTime = null;
let lastTotalPnl = null;
let lastExchangePnl = {};

async function updateTable() {
  try {
    const res = await fetch('/data');
    const data = await res.json();

    /* =========================
       HEADER PnL FLASH
    ========================= */
    document.getElementById('timestamp').textContent = data.timestamp ?? '-';
    document.getElementById('balance').textContent =
      Number(data.balance ?? 0).toFixed(2);

    const totalPnlEl = document.getElementById('total_pnl');
    const totalPnl = Number(data.total_pnl ?? 0);

    totalPnlEl.textContent = totalPnl.toFixed(6);
    totalPnlEl.className = totalPnl >= 0 ? 'positive' : 'negative';

    if (lastTotalPnl !== null) {
      totalPnlEl.classList.add(
        totalPnl > lastTotalPnl ? 'pnl-up' : 'pnl-down'
      );
    }

    lastTotalPnl = totalPnl;

    /* =========================
       LIVE POSITIONS
    ========================= */
    const liveBody = document.querySelector('#liveTable tbody');
    liveBody.innerHTML = '';

    for (const [exchange, info] of Object.entries(data.exchanges || {})) {
      const pnl = Number(info.pnl ?? 0);
      const row = document.createElement('tr');

      let pnlClass = pnl >= 0 ? 'positive' : 'negative';
      let pnlFlash = '';

      if (lastExchangePnl[exchange] !== undefined) {
        pnlFlash = pnl > lastExchangePnl[exchange] ? 'pnl-up' : 'pnl-down';
      }

      lastExchangePnl[exchange] = pnl;

      row.innerHTML = `
        <td>${exchange}</td>
        <td>${Number(info.price ?? 0).toFixed(2)}</td>
        <td>${info.prediction !== null ? Number(info.prediction).toFixed(2) : '-'}</td>
        <td>${info.position ?? '-'}</td>
        <td class="${pnlClass} ${pnlFlash}">
          ${pnl.toFixed(6)}
        </td>
      `;
      liveBody.appendChild(row);
    }

    /* =========================
       TRADE HISTORY
    ========================= */
    const thBody = document.querySelector('#tradeHistoryTable tbody');
    thBody.innerHTML = '';

    const trades = [...(data.last_trades || [])].reverse();

    for (const trade of trades) {
      const row = document.createElement('tr');

      if (lastSeenTradeTime && trade.time > lastSeenTradeTime) {
        if (trade.type === 'CLOSE') {
          row.classList.add(
            (trade.pnl ?? 0) >= 0 ? 'close-win' : 'close-loss'
          );
        } else {
          row.classList.add('add-trade');
        }
      }

      row.innerHTML = `
        <td>${trade.time}</td>
        <td>${trade.exchange}</td>
        <td>${trade.type}</td>
        <td>${trade.side}</td>
        <td>${Number(trade.price ?? 0).toFixed(2)}</td>
        <td>${trade.btc_added !== null ? Number(trade.btc_added).toFixed(8) : '-'}</td>
        <td>${trade.total_btc !== null ? Number(trade.total_btc).toFixed(8) : '-'}</td>
        <td class="${(trade.pnl ?? 0) >= 0 ? 'positive' : 'negative'}">
          ${trade.pnl !== null ? Number(trade.pnl).toFixed(6) : '-'}
        </td>
      `;
      thBody.appendChild(row);
    }

    if (trades.length > 0) {
      lastSeenTradeTime = trades[0].time;
    }

  } catch (err) {
    console.error("LIVE UPDATE ERROR:", err);
  }
}

setInterval(updateTable, 1000);
updateTable();

<h2>Aggregated Orderbook</h2>
<table id="orderbookTable">
<thead>
<tr><th>Price</th><th>Total Bids</th><th>Total Asks</th></tr>
</thead>
<tbody></tbody>
</table>

<h2>Last 50 Trades</h2>
<table id="tradeHistoryTable">
<thead>
<tr>
<th>Time</th><th>Exchange</th><th>Side</th><th>Price</th><th>Quantity</th>
</tr>
</thead>
<tbody></tbody>
</table>

<script>
let lastBids = {}, lastAsks = {};

async function updateTables() {
    try {
        const res = await fetch('/aggregated_data');
        const data = await res.json();

        // ==================== ORDERBOOK ====================
        const obBody = document.querySelector('#orderbookTable tbody');
        obBody.innerHTML = '';
        data.orderbook.forEach(row=>{
            const tr = document.createElement('tr');

            let bidClass='', askClass='';
            if(lastBids[row.price]!==undefined){
                bidClass = row.total_bids>lastBids[row.price] ? 'flash-up' : row.total_bids<lastBids[row.price] ? 'flash-down' : '';
            }
            if(lastAsks[row.price]!==undefined){
                askClass = row.total_asks>lastAsks[row.price] ? 'flash-up' : row.total_asks<lastAsks[row.price] ? 'flash-down' : '';
            }

            lastBids[row.price]=row.total_bids;
            lastAsks[row.price]=row.total_asks;

            tr.innerHTML=`<td>${row.price.toFixed(2)}</td>
                          <td class="${bidClass}">${row.total_bids.toFixed(6)}</td>
                          <td class="${askClass}">${row.total_asks.toFixed(6)}</td>`;
            obBody.appendChild(tr);
        });

        // ==================== TRADES ====================
        const thBody = document.querySelector('#tradeHistoryTable tbody');
        thBody.innerHTML='';
        data.trades.forEach(t=>{
            const tr=document.createElement('tr');
            const sideClass = t.side=="BUY" ? 'positive flash-up' : 'negative flash-down';
            tr.innerHTML=`<td>${new Date(t.time).toLocaleTimeString()}</td>
                          <td>${t.exchange}</td>
                          <td class="${sideClass}">${t.side}</td>
                          <td>${t.price.toFixed(2)}</td>
                          <td>${t.quantity.toFixed(6)}</td>`;
            thBody.appendChild(tr);
        });

    } catch(e){console.error("ERROR", e);}
}

setInterval(updateTables, 200);  // updates every 200ms
updateTables();
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
