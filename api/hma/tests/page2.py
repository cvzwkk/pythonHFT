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
   POSITION SIZE HEATMAP
========================= */
.position-cell {
  transition: background-color 0.4s ease;
}

/* =========================
   TRADE ANIMATIONS
========================= */
@keyframes addFlash {
  from { background-color: #ffffcc; }
  to   { background-color: transparent; }
}
.add-trade { animation: addFlash 0.8s ease-out; }

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
<th>Size (BTC)</th>
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

function heatColor(size, maxSize, side) {
  if (maxSize === 0) return 'transparent';

  const intensity = Math.min(Math.abs(size) / maxSize, 1);
  const alpha = 0.15 + intensity * 0.45;

  return side === 'LONG'
    ? `rgba(0, 200, 0, ${alpha})`
    : `rgba(200, 0, 0, ${alpha})`;
}

async function updateTable() {
  try {
    const res = await fetch('/data');
    const data = await res.json();

    /* =========================
       HEADER
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

    const sizes = Object.values(data.exchanges || {})
      .map(v => Math.abs(v.size ?? 0));
    const maxSize = Math.max(...sizes, 0.00000001);

    for (const [exchange, info] of Object.entries(data.exchanges || {})) {
      const pnl = Number(info.pnl ?? 0);
      const size = Number(info.size ?? 0);
      const side = size >= 0 ? 'LONG' : 'SHORT';

      let pnlFlash = '';
      if (lastExchangePnl[exchange] !== undefined) {
        pnlFlash = pnl > lastExchangePnl[exchange] ? 'pnl-up' : 'pnl-down';
      }
      lastExchangePnl[exchange] = pnl;

      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${exchange}</td>
        <td>${Number(info.price ?? 0).toFixed(2)}</td>
        <td>${info.prediction !== null ? Number(info.prediction).toFixed(2) : '-'}</td>
        <td>${side}</td>
        <td class="position-cell">${size.toFixed(8)}</td>
        <td class="${pnl >= 0 ? 'positive' : 'negative'} ${pnlFlash}">
          ${pnl.toFixed(6)}
        </td>
      `;

      const posCell = row.querySelector('.position-cell');
      posCell.style.backgroundColor = heatColor(size, maxSize, side);

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
