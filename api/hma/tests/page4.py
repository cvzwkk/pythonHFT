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
   EXISTING ANIMATIONS
========================= */
@keyframes addFlash {
  from { background-color: #ffffcc; }
  to   { background-color: transparent; }
}

.add-trade {
  animation: addFlash 0.8s ease-out;
}

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

</div>
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
