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


/* =========================
   🔥 ADDED: AGGREGATED BOOK
========================= */
#aggBookTable {
  width: 100%;
  font-size: 13px;
  margin-top: 10px;
}

.agg-flash {
  animation: aggFlash 0.6s ease-out;
}

@keyframes aggFlash {
  from { background-color: #ffff99; }
  to   { background-color: transparent; }
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


<!-- =========================
     🔥 ADDED: AGGREGATED BOOK
     BELOW BITFINEX ONLY
========================= -->

<h2>Aggregated Order Book (Top / Mid / Deep)</h2>

<table id="aggBookTable">
<thead>
<tr>
<th>Depth</th>
<th style="color:red">Ask Liquidity (BTC)</th>
<th style="color:green">Bid Liquidity (BTC)</th>
<th>Imbalance</th>
</tr>
</thead>
<tbody>
<tr data-level="top">
<td>Top</td>
<td>-</td>
<td>-</td>
<td>-</td>
</tr>
<tr data-level="mid">
<td>Mid</td>
<td>-</td>
<td>-</td>
<td>-</td>
</tr>
<tr data-level="deep">
<td>Deep</td>
<td>-</td>
<td>-</td>
<td>-</td>
</tr>
</tbody>
</table>

<h2>Aggregated VWAP & Volume Profile</h2>
<table id="vwapTable">
<thead>
<tr><th>Timeframe</th><th>VWAP</th><th>±1 Std</th><th>±2 Std</th><th>HVN</th><th>LVN</th></tr>
</thead>
<tbody>
<tr data-tf="1m"><td>1m</td><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td></tr>
<tr data-tf="15m"><td>15m</td><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td></tr>
<tr data-tf="4h"><td>4h</td><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td></tr>
<tr data-tf="1d"><td>1d</td><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td></tr>
<tr data-tf="1w"><td>1w</td><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td></tr>
<tr data-tf="1M"><td>1M</td><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td></tr>
</tbody>
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

    const trades = [...(data.last_trades || [])]
  .slice(-10)
  .reverse();

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
   BITFINEX ORDER BOOK (FIXED)
========================= */
const BIG_SIZE_THRESHOLD = 5.0;   // BTC size to flash
const RENDER_INTERVAL_MS = 100;   // 10 FPS max
const ws = new WebSocket("wss://api-pub.bitfinex.com/ws/2");

let chanId = null;
let bids = new Map();
let asks = new Map();
let needsRender = false;
let lastBigUpdate = false;

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
    chanId = data.chanId;
    return;
  }

  if (!Array.isArray(data) || data[0] !== chanId) return;

  const payload = data[1];

  /* SNAPSHOT */
  if (Array.isArray(payload[0])) {
    bids.clear();
    asks.clear();

    payload.forEach(([price, count, amount]) => {
      if (amount > 0) bids.set(price, amount);
      else asks.set(price, Math.abs(amount));
    });

    needsRender = true;
    return;
  }

  /* INCREMENTAL UPDATE */
  const [price, count, amount] = payload;

  let size = Math.abs(amount);

  if (count === 0) {
    bids.delete(price);
    asks.delete(price);
  } else {
    if (amount > 0) bids.set(price, size);
    else asks.set(price, size);
  }

  if (size >= BIG_SIZE_THRESHOLD) {
    lastBigUpdate = true;
  }

  needsRender = true;
};

/* =========================
   RENDER LOOP (THROTTLED)
========================= */

setInterval(() => {
  if (!needsRender) return;

  renderOrderBook(lastBigUpdate);
  needsRender = false;
  lastBigUpdate = false;
}, RENDER_INTERVAL_MS);

/* =========================
   RENDER FUNCTION
========================= */

function renderOrderBook(flash) {
  const tbody = document.querySelector("#orderbookTable tbody");
  tbody.innerHTML = "";

  const bidRows = [...bids.entries()]
    .sort((a, b) => b[0] - a[0])
    .slice(0, 15);

  const askRows = [...asks.entries()]
    .sort((a, b) => a[0] - b[0])
    .slice(0, 15);

  for (let i = 0; i < 15; i++) {
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

<script>
/* =========================
   AGGREGATED ORDERBOOK CORE
   (STATE ONLY – NO WS YET)
========================= */

/*
Depth buckets:
Top   = best 0.1%
Mid   = 0.1% → 0.5%
Deep  = 0.5% → 1.5%
*/

const AGG_DEPTHS = {
  top: 0.001,
  mid: 0.005,
  deep: 0.015
};

/* =========================
   EXCHANGE REGISTRY
========================= */

const AGG_EXCHANGES = [
  "bitfinex",
  "binance",
  "kraken",
  "bitstamp",
  "okx",
  "huobi",
  "coinbase"
];

/* =========================
   ORDERBOOK STORAGE
========================= */

const aggBooks = {};
AGG_EXCHANGES.forEach(ex => {
  aggBooks[ex] = {
    bids: new Map(),
    asks: new Map(),
    mid: null
  };
});

/* =========================
   AGGREGATION RESULT STATE
========================= */

const aggResult = {
  top: { bid: 0, ask: 0 },
  mid: { bid: 0, ask: 0 },
  deep:{ bid: 0, ask: 0 }
};

/* =========================
   UTILS
========================= */

function calcMid(bids, asks) {
  if (!bids.size || !asks.size) return null;
  const bestBid = Math.max(...bids.keys());
  const bestAsk = Math.min(...asks.keys());
  return (bestBid + bestAsk) / 2;
}

function resetAggResult() {
  for (const lvl in aggResult) {
    aggResult[lvl].bid = 0;
    aggResult[lvl].ask = 0;
  }
}

/* =========================
   AGGREGATE ALL EXCHANGES
========================= */

function aggregateBooks() {
  resetAggResult();

  AGG_EXCHANGES.forEach(ex => {
    const book = aggBooks[ex];
    if (!book.mid) return;

    for (const [price, size] of book.bids) {
      const d = (book.mid - price) / book.mid;
      if (d <= AGG_DEPTHS.deep) {
        if (d <= AGG_DEPTHS.top) aggResult.top.bid += size;
        else if (d <= AGG_DEPTHS.mid) aggResult.mid.bid += size;
        else aggResult.deep.bid += size;
      }
    }

    for (const [price, size] of book.asks) {
      const d = (price - book.mid) / book.mid;
      if (d <= AGG_DEPTHS.deep) {
        if (d <= AGG_DEPTHS.top) aggResult.top.ask += size;
        else if (d <= AGG_DEPTHS.mid) aggResult.mid.ask += size;
        else aggResult.deep.ask += size;
      }
    }
  });
}

/* =========================
   RENDER AGG TABLE
========================= */

function renderAggTable() {
  const rows = document.querySelectorAll("#aggBookTable tbody tr");

  rows.forEach(row => {
    const lvl = row.dataset.level;
    const bid = aggResult[lvl].bid;
    const ask = aggResult[lvl].ask;
    const imb = (bid - ask) / Math.max(bid + ask, 1e-6);

    row.cells[1].textContent = ask.toFixed(2);
    row.cells[2].textContent = bid.toFixed(2);
    row.cells[3].textContent = imb.toFixed(3);

    row.cells[3].className =
      imb > 0 ? "positive" : imb < 0 ? "negative" : "";
  });
}

/* =========================
   THROTTLED UPDATE LOOP
========================= */

setInterval(() => {
  aggregateBooks();
  renderAggTable();
}, 250); // 4 FPS, ultra light
</script>

<script>
/* =========================
   BINANCE (BTCUSDT)
========================= */
(() => {
  const ws = new WebSocket("wss://stream.binance.com:9443/ws/btcusdt@depth@100ms");
  ws.onmessage = e => {
    const d = JSON.parse(e.data);
    const book = aggBooks.binance;
    book.bids.clear();
    book.asks.clear();

    d.b.forEach(([p, s]) => book.bids.set(+p, +s));
    d.a.forEach(([p, s]) => book.asks.set(+p, +s));

    book.mid = calcMid(book.bids, book.asks);
  };
})();

/* =========================
   KRAKEN (XBT/USD)
========================= */
(() => {
  const ws = new WebSocket("wss://ws.kraken.com");
  ws.onopen = () => ws.send(JSON.stringify({
    event: "subscribe",
    pair: ["XBT/USD"],
    subscription: { name: "book", depth: 25 }
  }));

  ws.onmessage = e => {
    const d = JSON.parse(e.data);
    if (!Array.isArray(d)) return;

    const book = aggBooks.kraken;

    if (d[1]?.as || d[1]?.bs) {
      if (d[1].bs) d[1].bs.forEach(([p, s]) => book.bids.set(+p, +s));
      if (d[1].as) d[1].as.forEach(([p, s]) => book.asks.set(+p, +s));
    }

    book.mid = calcMid(book.bids, book.asks);
  };
})();

/* =========================
   COINBASE (BTC-USD)
========================= */
(() => {
  const ws = new WebSocket("wss://ws-feed.exchange.coinbase.com");
  ws.onopen = () => ws.send(JSON.stringify({
    type: "subscribe",
    product_ids: ["BTC-USD"],
    channels: ["level2"]
  }));

  ws.onmessage = e => {
    const d = JSON.parse(e.data);
    const book = aggBooks.coinbase;

    if (d.type === "snapshot") {
      book.bids.clear();
      book.asks.clear();
      d.bids.forEach(([p, s]) => book.bids.set(+p, +s));
      d.asks.forEach(([p, s]) => book.asks.set(+p, +s));
    }

    if (d.type === "l2update") {
      d.changes.forEach(([side, p, s]) => {
        const map = side === "buy" ? book.bids : book.asks;
        if (+s === 0) map.delete(+p);
        else map.set(+p, +s);
      });
    }

    book.mid = calcMid(book.bids, book.asks);
  };
})();

/* =========================
   OKX (BTC-USDT)
========================= */
(() => {
  const ws = new WebSocket("wss://ws.okx.com:8443/ws/v5/public");
  ws.onopen = () => ws.send(JSON.stringify({
    op: "subscribe",
    args: [{ channel: "books", instId: "BTC-USDT" }]
  }));

  ws.onmessage = e => {
    const d = JSON.parse(e.data);
    if (!d.data) return;

    const book = aggBooks.okx;
    book.bids.clear();
    book.asks.clear();

    d.data[0].bids.forEach(([p, s]) => book.bids.set(+p, +s));
    d.data[0].asks.forEach(([p, s]) => book.asks.set(+p, +s));

    book.mid = calcMid(book.bids, book.asks);
  };
})();

/* =========================
   HUOBI (BTCUSDT)
========================= */
(() => {
  const ws = new WebSocket("wss://api.huobi.pro/ws");
  ws.binaryType = "arraybuffer";

  ws.onopen = () => ws.send(JSON.stringify({
    sub: "market.btcusdt.depth.step0",
    id: "huobi"
  }));

  ws.onmessage = e => {
    const d = JSON.parse(pako.inflate(e.data, { to: "string" }));
    if (!d.tick) return;

    const book = aggBooks.huobi;
    book.bids.clear();
    book.asks.clear();

    d.tick.bids.forEach(([p, s]) => book.bids.set(+p, +s));
    d.tick.asks.forEach(([p, s]) => book.asks.set(+p, +s));

    book.mid = calcMid(book.bids, book.asks);
  };
})();

/* =========================
   BITSTAMP (BTC/USD)
========================= */
(() => {
  const ws = new WebSocket("wss://ws.bitstamp.net");
  ws.onopen = () => ws.send(JSON.stringify({
    event: "bts:subscribe",
    data: { channel: "order_book_btcusd" }
  }));

  ws.onmessage = e => {
    const d = JSON.parse(e.data);
    if (!d.data) return;

    const book = aggBooks.bitstamp;
    book.bids.clear();
    book.asks.clear();

    d.data.bids.forEach(([p, s]) => book.bids.set(+p, +s));
    d.data.asks.forEach(([p, s]) => book.asks.set(+p, +s));

    book.mid = calcMid(book.bids, book.asks);
  };
})();
</script>

<script>
/* =========================
   AGG BOOK – FLASH LOGIC
========================= */

const AGG_FLASH_THRESHOLD = 25.0; // BTC delta to flash

const lastAggSnapshot = {
  top: { bid: 0, ask: 0 },
  mid: { bid: 0, ask: 0 },
  deep:{ bid: 0, ask: 0 }
};

function shouldFlash(level) {
  const prev = lastAggSnapshot[level];
  const curr = aggResult[level];

  const delta =
    Math.abs(curr.bid - prev.bid) +
    Math.abs(curr.ask - prev.ask);

  return delta >= AGG_FLASH_THRESHOLD;
}

function updateAggSnapshot() {
  ["top","mid","deep"].forEach(lvl => {
    lastAggSnapshot[lvl].bid = aggResult[lvl].bid;
    lastAggSnapshot[lvl].ask = aggResult[lvl].ask;
  });
}

/* =========================
   PATCH RENDER WITH FLASH
========================= */

const _renderAggTable = renderAggTable;
renderAggTable = function () {
  const rows = document.querySelectorAll("#aggBookTable tbody tr");

  rows.forEach(row => {
    const lvl = row.dataset.level;
    const bid = aggResult[lvl].bid;
    const ask = aggResult[lvl].ask;
    const imb = (bid - ask) / Math.max(bid + ask, 1e-6);

    row.cells[1].textContent = ask.toFixed(2);
    row.cells[2].textContent = bid.toFixed(2);
    row.cells[3].textContent = imb.toFixed(3);

    row.cells[3].className =
      imb > 0 ? "positive" : imb < 0 ? "negative" : "";

    if (shouldFlash(lvl)) {
      row.classList.add("flash");
      setTimeout(() => row.classList.remove("flash"), 300);
    }
  });

  updateAggSnapshot();
};
</script>

<script>
// =========================
// Exchanges & Aggregated Orderbooks
// =========================
const EXCHANGES = ["binance","bitfinex","bitstamp","coinbase","okx","huobi"];
const aggBooks = {};
EXCHANGES.forEach(e => aggBooks[e] = { bids: new Map(), asks: new Map(), mid: null });

// =========================
// Depth Buckets
// =========================
const AGG_DEPTHS = { top:0.001, mid:0.005, deep:0.015 };
const aggResult = { top:{bid:0,ask:0}, mid:{bid:0,ask:0}, deep:{bid:0,ask:0} };

// =========================
// VWAP / Volume Profile
// =========================
const VWAP_TFS=["1m","15m","4h","1d","1w","1M"];
const tradeBuffers={}; VWAP_TFS.forEach(tf=>tradeBuffers[tf]=[]);

const ROLLING_MS={"1m":60000,"15m":900000,"4h":14400000,"1d":86400000,"1w":604800000,"1M":2592000000};
const AGG_VWAP={}; VWAP_TFS.forEach(tf=>AGG_VWAP[tf]=new Map());

// =========================
// UTIL FUNCTIONS
// =========================
function calcMid(bids, asks){
    if(!bids.size||!asks.size) return null;
    const bestBid = Math.max(...bids.keys());
    const bestAsk = Math.min(...asks.keys());
    return (bestBid+bestAsk)/2;
}

function addTrade(tf, price, volume, timestamp){
    tradeBuffers[tf].push({price,volume,ts:timestamp});
    AGG_VWAP[tf].set(price,(AGG_VWAP[tf].get(price)||0)+volume);
    const cutoff=Date.now()-ROLLING_MS[tf];
    while(tradeBuffers[tf].length && tradeBuffers[tf][0].ts < cutoff){
        const old = tradeBuffers[tf].shift();
        const prev = AGG_VWAP[tf].get(old.price) || 0;
        const newVol = prev - old.volume;
        if(newVol<=0) AGG_VWAP[tf].delete(old.price);
        else AGG_VWAP[tf].set(old.price,newVol);
    }
}

function computeVWAP(tf){
    const priceMap = AGG_VWAP[tf];
    if(priceMap.size===0) return null;
    let totalVol=0, volPrice=0;
    priceMap.forEach((vol,price)=>{totalVol+=vol; volPrice+=vol*price;});
    const vwap = volPrice/totalVol;
    let variance = 0;
    priceMap.forEach((vol,price)=>{variance+=vol*Math.pow(price-vwap,2);});
    variance/=totalVol;
    const std=Math.sqrt(variance);
    const hvn=[...priceMap.entries()].reduce((a,b)=>a[1]>b[1]?a:b)[0];
    const lvn=[...priceMap.entries()].reduce((a,b)=>a[1]<b[1]?a:b)[0];
    return {vwap,std1:std,std2:std*2,hvn,lvn};
}

// =========================
// AGGREGATE BOOKS
// =========================
function aggregateBooks(){
    ["top","mid","deep"].forEach(lvl=>{aggResult[lvl].bid=0;aggResult[lvl].ask=0;});
    EXCHANGES.forEach(ex=>{
        const book = aggBooks[ex];
        if(!book.mid) return;
        book.bids.forEach((size, price)=>{
            const d=(book.mid-price)/book.mid;
            if(d<=AGG_DEPTHS.deep){
                if(d<=AGG_DEPTHS.top) aggResult.top.bid+=size;
                else if(d<=AGG_DEPTHS.mid) aggResult.mid.bid+=size;
                else aggResult.deep.bid+=size;
            }
        });
        book.asks.forEach((size, price)=>{
            const d=(price-book.mid)/book.mid;
            if(d<=AGG_DEPTHS.deep){
                if(d<=AGG_DEPTHS.top) aggResult.top.ask+=size;
                else if(d<=AGG_DEPTHS.mid) aggResult.mid.ask+=size;
                else aggResult.deep.ask+=size;
            }
        });
    });
}

// =========================
// RENDER FUNCTIONS
// =========================
function renderAggTable(){
    const rows=document.querySelectorAll("#aggBookTable tbody tr");
    rows.forEach(row=>{
        const lvl=row.dataset.level;
        const bid=aggResult[lvl].bid;
        const ask=aggResult[lvl].ask;
        const imb=(bid-ask)/Math.max(bid+ask,1e-6);
        row.cells[1].textContent=ask.toFixed(2);
        row.cells[2].textContent=bid.toFixed(2);
        row.cells[3].textContent=imb.toFixed(3);
        row.cells[3].className=imb>0?"positive":imb<0?"negative":"";
    });
}

function renderVWAPTable(){
    VWAP_TFS.forEach(tf=>{
        const row=document.querySelector(`#vwapTable tr[data-tf="${tf}"]`);
        const d=computeVWAP(tf);
        if(!d) return;
        row.cells[1].textContent=d.vwap.toFixed(2);
        row.cells[2].textContent=(d.vwap-d.std1).toFixed(2)+" / "+(d.vwap+d.std1).toFixed(2);
        row.cells[3].textContent=(d.vwap-d.std2).toFixed(2)+" / "+(d.vwap+d.std2).toFixed(2);
        row.cells[4].textContent=d.hvn.toFixed(2);
        row.cells[5].textContent=d.lvn.toFixed(2);
    });
}

// =========================
// BINANCE WS
// =========================
(() => {
    const ws = new WebSocket("wss://stream.binance.com:9443/ws/btcusdt@trade");
    ws.onmessage = e => {
        const d = JSON.parse(e.data);
        addTrade("1m", parseFloat(d.p), parseFloat(d.q), d.T);
    };
})();

// =========================
// BITFINEX WS
// =========================
(() => {
    const ws = new WebSocket("wss://api-pub.bitfinex.com/ws/2");
    let chanId = null;
    ws.onopen = () => ws.send(JSON.stringify({event:"subscribe",channel:"trades",symbol:"tBTCUSD"}));
    ws.onmessage = e => {
        const d = JSON.parse(e.data);
        if(d.event==="subscribed"){ chanId=d.chanId; return; }
        if(!Array.isArray(d)||d[0]!==chanId) return;
        const trades = d[1];
        if(Array.isArray(trades[0])) trades.forEach(([id,ts,price,amount])=>{
            addTrade("1m", price, Math.abs(amount), ts);
        });
    };
})();

// =========================
// COINBASE WS
// =========================
(() => {
    const ws = new WebSocket("wss://ws-feed.exchange.coinbase.com");
    ws.onopen = () => ws.send(JSON.stringify({type:"subscribe",product_ids:["BTC-USD"],channels:["matches"]}));
    ws.onmessage = e => {
        const d = JSON.parse(e.data);
        if(d.type==="match") addTrade("1m", parseFloat(d.price), parseFloat(d.size), new Date(d.time).getTime());
    };
})();

// =========================
// BITSTAMP WS
// =========================
(() => {
    const ws = new WebSocket("wss://ws.bitstamp.net");
    ws.onopen = () => ws.send(JSON.stringify({event:"bts:subscribe",data:{channel:"live_trades_btcusd"}}));
    ws.onmessage = e => {
        const d = JSON.parse(e.data);
        if(d.event==="trade") addTrade("1m", parseFloat(d.data.price), parseFloat(d.data.amount), d.data.microtimestamp/1000);
    };
})();

// =========================
// OKX WS
// =========================
(() => {
    const ws = new WebSocket("wss://ws.okx.com:8443/ws/v5/public");
    ws.onopen = () => ws.send(JSON.stringify({op:"subscribe",args:[{channel:"trades",instId:"BTC-USDT"}]}));
    ws.onmessage = e => {
        const d = JSON.parse(e.data);
        if(!d.data) return;
        d.data.forEach(trade => addTrade("1m", parseFloat(trade.p), parseFloat(trade.s), trade.ts));
    };
})();

// =========================
// HUOBI WS
// =========================
(() => {
    const ws = new WebSocket("wss://api.huobi.pro/ws");
    ws.onopen = () => ws.send(JSON.stringify({sub:"market.btcusdt.trade.detail",id:"huobi"})));
    ws.onmessage = e => {
        const d = JSON.parse(e.data);
        if(!d.tick||!d.tick.data) return;
        d.tick.data.forEach(trade => addTrade("1m", trade.price, trade.amount, trade.ts));
    };
})();

// =========================
// UPDATE LOOP
// =========================
setInterval(()=>{aggregateBooks(); renderAggTable(); renderVWAPTable();},1000);
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
