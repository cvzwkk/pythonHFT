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

#orderBookTable td.bid { color: green; }
#orderBookTable td.ask { color: red; }

#orderBookTable tbody tr {
  font-size: 13px;
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

<h2>Bitfinex Order Book (BTC/USD – Top 30)</h2>

<table id="orderBookTable">
<thead>
<tr>
<th colspan="3">BIDS</th>
<th colspan="3">ASKS</th>
</tr>
<tr>
<th>Price</th>
<th>Amount</th>
<th>Total</th>
<th>Price</th>
<th>Amount</th>
<th>Total</th>
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
</script>

<script>
/* =========================
   BITFINEX ORDER BOOK
========================= */
const OB_ROWS = 30;
const bids = new Map();
const asks = new Map();

const obBody = document.querySelector('#orderBookTable tbody');

function renderOrderBook() {
  obBody.innerHTML = '';

  const bidArr = [...bids.entries()]
    .sort((a,b) => b[0] - a[0])
    .slice(0, OB_ROWS);

  const askArr = [...asks.entries()]
    .sort((a,b) => a[0] - b[0])
    .slice(0, OB_ROWS);

  let bidTotal = 0;
  let askTotal = 0;

  for (let i = 0; i < OB_ROWS; i++) {
    const row = document.createElement('tr');

    if (bidArr[i]) bidTotal += bidArr[i][1];
    if (askArr[i]) askTotal += askArr[i][1];

    row.innerHTML = `
      <td class="bid">${bidArr[i]?.[0]?.toFixed(2) ?? ''}</td>
      <td class="bid">${bidArr[i]?.[1]?.toFixed(4) ?? ''}</td>
      <td class="bid">${bidTotal.toFixed(4)}</td>

      <td class="ask">${askArr[i]?.[0]?.toFixed(2) ?? ''}</td>
      <td class="ask">${askArr[i]?.[1]?.toFixed(4) ?? ''}</td>
      <td class="ask">${askTotal.toFixed(4)}</td>
    `;
    obBody.appendChild(row);
  }
}

const ws = new WebSocket("wss://api-pub.bitfinex.com/ws/2");

ws.onopen = () => {
  ws.send(JSON.stringify({
    event: "subscribe",
    channel: "book",
    symbol: "tBTCUSD",
    prec: "P0",
    freq: "F0",
    len: 100
  }));
};

ws.onmessage = (msg) => {
  const data = JSON.parse(msg.data);
  if (!Array.isArray(data)) return;

  const payload = data[1];
  if (!payload) return;

  // SNAPSHOT
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

  // UPDATE
  const [price, count, amount] = payload;

  if (count === 0) {
    bids.delete(price);
    asks.delete(price);
  } else if (amount > 0) {
    bids.set(price, amount);
  } else {
    asks.set(price, Math.abs(amount));
  }

  renderOrderBook();
};
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
