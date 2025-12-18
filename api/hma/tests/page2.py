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
  margin-bottom: 30
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
exchange}</td>
        <td>${Number(info.price ?? 0).toFixed(2)}</td>
        <td>${info.prediction !== null ? Number(info.prediction).toFixed(2) : '-'}</td>
        <td>${side}</td>
        <td class="position-cell">${size.toFixed(8)}</td>
        <td class="${pnl >= 0 ? 'positive' : 'negative'} ${pnlFlash}">
          ${pnl.toFixed(6)}
        </td>
      `;

<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>BTC Microprice DCA Dashboard</title>

<style>
body {
  font-family: Arial, sans-serif;
  margin: 20px;
}

table {
  border-collapse: collapse;
  width: 100%;
  margin-bottom: 30px;
}

th, td {
  border: 1px solid #ccc;
  padding: 6px;
  text-align: center;
  font-size: 13px;
}

th {
  background: #f4f4f4;
}

.positive { color: green; }
.negative { color: red; }

/* ========= ANIMATIONS ========= */
@keyframes addFlash {
  from { background-color: #e0f7ff; }
  to { background-color: transparent; }
}

@keyframes closeFlash {
  from { background-color: #ffe0e0; }
  to { background-color: transparent; }
}

.add-trade { animation: addFlash 0.8s ease-out; }
.close-trade { animation: closeFlash 0.8s ease-out; }

@keyframes pnlUp {
  from { background-color: #ccffcc; }
  to { background-color: transparent; }
}
@keyframes pnlDown {
  from { background-color: #ffcccc; }
  to { background-color: transparent; }
}

.pnl-up { animation: pnlUp 0.6s ease-out; }
.pnl-down { animation: pnlDown 0.6s ease-out; }
</style>
</head>

<body>

<h2>BTC Microprice DCA Engine</h2>

<p>
<b>Last Update:</b> <span id="timestamp">-</span><br>
<b>Balance (USD):</b> <span id="balance">-</span><br>
<b>Total PnL:</b> <span id="total_pnl">-</span>
</p>

<!-- ================= LIVE EXCHANGES ================= -->
<h3>Live Exchanges</h3>

<table id="liveTable">
<thead>
<tr>
  <th>Exchange</th>
  <th>Price</th>
  <th>HMA</th>
  <th>HMA2</th>
  <th>Position</th>
  <th>Entries</th>
  <th>Adds</th>
  <th>PnL</th>
</tr>
</thead>
<tbody></tbody>
</table>

<!-- ================= TRADE HISTORY ================= -->
<h3>Last Trades (Newest First)</h3>

<table id="tradeTable">
<thead>
<tr>
  <th>Time</th>
  <th>Exchange</th>
  <th>Type</th>
  <th>Side</th>
  <th>Price</th>
  <th>BTC</th>
  <th>Total BTC</th>
  <th>PnL</th>
</tr>
</thead>
<tbody></tbody>
</table>

<script>
let lastPnl = {};
let lastTradeTime = null;

async function updateDashboard() {
  try {
    const res = await fetch("/live");
    const data = await res.json();

    /* ========= HEADER ========= */
    document.getElementById("timestamp").textContent =
      new Date(data.timestamp).toLocaleTimeString();

    document.getElementById("balance").textContent =
      Number(data.balance_usd).toFixed(2);

    const pnlEl = document.getElementById("total_pnl");
    pnlEl.textContent = Number(data.total_pnl_usd).toFixed(6);
    pnlEl.className =
      data.total_pnl_usd >= 0 ? "positive" : "negative";

    /* ========= LIVE TABLE ========= */
    const liveBody = document.querySelector("#liveTable tbody");
    liveBody.innerHTML = "";

    for (const [ex, info] of Object.entries(data.exchanges || {})) {
      let pnlClass = "";
      if (lastPnl[ex] !== undefined) {
        pnlClass = info.pnl > lastPnl[ex] ? "pnl-up" : "pnl-down";
      }
      lastPnl[ex] = info.pnl;

      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${ex}</td>
        <td>${Number(info.price).toFixed(2)}</td>
        <td>${info.prediction_hma !== null ? info.prediction_hma.toFixed(2) : "-"}</td>
        <td>${info.prediction_hma2 !== null ? info.prediction_hma2.toFixed(2) : "-"}</td>
        <td>${info.position}</td>
        <td>${info.entries}</td>
        <td>${info.adds}</td>
        <td class="${info.pnl >= 0 ? "positive" : "negative"} ${pnlClass}">
          ${info.pnl.toFixed(6)}
        </td>
      `;
      liveBody.appendChild(row);
    }

    /* ========= TRADE HISTORY ========= */
    const tradeBody = document.querySelector("#tradeTable tbody");
    tradeBody.innerHTML = "";

    const trades = [...(data.last_trades || [])].reverse();

    for (const t of trades) {
      const row = document.createElement("tr");

      let anim = "";
      if (lastTradeTime && t.time > lastTradeTime) {
        if (t.type === "ADD") anim = "add-trade";
        if (t.type.startsWith("FORCE_EXIT") || t.type === "TP")
          anim = "close-trade";
      }

      row.className = anim;

      const btc =
        t.btc ?? t.btc_added ?? "-";

      row.innerHTML = `
        <td>${t.time}</td>
        <td>${t.exchange}</td>
        <td>${t.type}</td>
        <td>${t.side}</td>
        <td>${Number(t.price).toFixed(2)}</td>
        <td>${btc !== "-" ? Number(btc).toFixed(8) : "-"}</td>
        <td>${t.total_btc !== undefined ? Number(t.total_btc).toFixed(8) : "-"}</td>
        <td class="${t.pnl >= 0 ? "positive" : "negative"}">
          ${t.pnl !== null ? Number(t.pnl).toFixed(6) : "-"}
        </td>
      `;

      tradeBody.appendChild(row);
    }

    if (trades.length > 0) {
      lastTradeTime = trades[0].time;
    }

  } catch (err) {
    console.error("DASHBOARD ERROR:", err);
  }
}

setInterval(updateDashboard, 1000);
updateDashboard();
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
