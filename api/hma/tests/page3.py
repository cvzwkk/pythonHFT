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

#orderbookContainer {
  margin-top: 20px;
}

#orderbookTable {
  width: 100%;
  font-size: 13px;
}

.ask { color: red; }
.bid { color: green; }

.flash {
  animation: flashBg 0.4s ease-out;
}

@keyframes flashBg {
  from { background-color: #ffff99; }
  to { background-color: transparent; }
}

</style>
</head>

<body>
<div id="divResize2" style="position: absolute; left: 0%; top: 0%; height: 35%; width: 100%">
<script type="text/javascript">DukascopyApplet = {"type":"chart","params":{"showUI":true,"showTabs":true,"showParameterToolbar":true,"showOfferSide":true,"allowInstrumentChange":true,"allowPeriodChange":true,"allowOfferSideChange":true,"showAdditionalToolbar":true,"showExportImportWorkspace":true,"allowSocialSharing":true,"showUndoRedoButtons":true,"showDetachButton":false,"presentationType":"candle","axisX":true,"axisY":true,"legend":true,"timeline":true,"showDateSeparators":true,"showZoom":true,"showScrollButtons":true,"showAutoShiftButton":true,"crosshair":true,"borders":false,"freeMode":false,"theme":"Pastelle","uiColor":"#000","availableInstruments":"l:","instrument":"BTC/USD","period":"5","offerSide":"BID","timezone":0,"live":true,"allowPan":true,"indicators":"sDYURGRBVBCMBgvAnIDgCjpTCLOcLjECDsADqAYQEWCsgLADyABF2dzI2QENoGyPx-ABlAFgAJhNsE8b0CgkAMRjO0gsOgvALhOGWWNKturbIQGfhhugj4YThFyVi0E-br1tLTV2QLsBB7uJLxcxP7UgIYKCLJwsAJA.","width":"100%","height":"100%","adv":"popup","lang":"en"}};</script><script type="text/javascript" src="https://freeserv-static.dukascopy.com/2.0/core.js"></script>
</div>

<div id="divResize3" style="position: absolute; left: 0%; top: 35%; height: 100%; width: 100%">
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

<h2>Bitfinex Order Book (BTC/USD)</h2>
  <table id="orderbookTable">
    <thead>
      <tr>
        <th colspan="2" style="color:red">Asks</th>
        <th colspan="2" style="color:green">Bids</th>
      </tr>
      <tr>
        <th>Price</th>
        <th>Size</th>
        <th>Price</th>
        <th>Size</th>
      </tr>
    </thead>
    <tbody></tbody>
  </table>
</div>

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
</script>

<script>
/* =========================
   BITFINEX ORDER BOOK
========================= */

const ws = new WebSocket("wss://api-pub.bitfinex.com/ws/2");

let channelId = null;
let bids = new Map();
let asks = new Map();
const MAX_ROWS = 15;

ws.onopen = () => {
  ws.send(JSON.stringify({
    event: "subscribe",
    channel: "book",
    symbol: "tBTCUSD",
    prec: "P0",
    freq: "F0",
    len: 25
  }));
};

ws.onmessage = (msg) => {
  const data = JSON.parse(msg.data);

  if (data.event === "subscribed") {
    channelId = data.chanId;
    return;
  }

  if (!Array.isArray(data) || data[0] !== channelId) return;

  const payload = data[1];

  // Snapshot
  if (Array.isArray(payload[0])) {
    bids.clear();
    asks.clear();

    payload.forEach(([price, count, amount]) => {
      if (amount > 0) bids.set(price, amount);
      else asks.set(price, Math.abs(amount));
    });

    renderOrderBook();
    return;
  }

  // Updates
  const [price, count, amount] = payload;

  if (count === 0) {
    bids.delete(price);
    asks.delete(price);
  } else {
    if (amount > 0) bids.set(price, amount);
    else asks.set(price, Math.abs(amount));
  }

  renderOrderBook(true);
};

function renderOrderBook(flash = false) {
  const tbody = document.querySelector("#orderbookTable tbody");
  tbody.innerHTML = "";

  const bidRows = [...bids.entries()]
    .sort((a, b) => b[0] - a[0])
    .slice(0, MAX_ROWS);

  const askRows = [...asks.entries()]
    .sort((a, b) => a[0] - b[0])
    .slice(0, MAX_ROWS);

  for (let i = 0; i < MAX_ROWS; i++) {
    const tr = document.createElement("tr");

    const ask = askRows[i];
    const bid = bidRows[i];

    tr.innerHTML = `
      <td class="ask">${ask ? ask[0].toFixed(2) : ""}</td>
      <td class="ask">${ask ? ask[1].toFixed(4) : ""}</td>
      <td class="bid">${bid ? bid[0].toFixed(2) : ""}</td>
      <td class="bid">${bid ? bid[1].toFixed(4) : ""}</td>
    `;

    if (flash) tr.classList.add("flash");
    tbody.appendChild(tr);
  }
}
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

    uvicorn.run(app, host="0.0.0.0", port=LOCAL_PORT)
