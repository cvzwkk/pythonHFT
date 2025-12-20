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
table { border-collapse: collapse; width: 100%; margin-bottom: 30px; }
th, td { border: 1px solid #ccc; padding: 8px; text-align: center; }
th { background-color: #f4f4f4; }
.negative { color: red; }
.positive { color: green; }

@keyframes addFlash { from { background-color: #ffffcc; } to { background-color: transparent; } }
.add-trade { animation: addFlash 0.8s ease-out; }
@keyframes closeWin { from { background-color: #ccffcc; } to { background-color: transparent; } }
@keyframes closeLoss { from { background-color: #ffcccc; } to { background-color: transparent; } }
.close-win  { animation: closeWin 1s ease-out; }
.close-loss { animation: closeLoss 1s ease-out; }
@keyframes pnlUp { from { background-color: #ccffcc; } to { background-color: transparent; } }
@keyframes pnlDown { from { background-color: #ffcccc; } to { background-color: transparent; } }
.pnl-up   { animation: pnlUp 0.6s ease-out; }
.pnl-down { animation: pnlDown 0.6s ease-out; }
#orderbookContainer { margin-top: 20px; }
#orderbookTable, #aggBookTable, #vwapTable { width: 100%; font-size: 13px; }
.ask { color: red; }
.bid { color: green; }
.flash { animation: flashBg 0.4s ease-out; }
@keyframes flashBg { from { background-color: #ffff99; } to { background-color: transparent; } }
.agg-flash { animation: aggFlash 0.6s ease-out; }
@keyframes aggFlash { from { background-color: #ffff99; } to { background-color: transparent; } }
</style>
</head>

<body>
<div>
<h2>Live Trading Data</h2>
<p>Last updated: <span id="timestamp">-</span></p>
<p>Balance: <span id="balance">-</span> | Total PnL: <span id="total_pnl">-</span></p>

<table id="liveTable"><thead>
<tr><th>Exchange</th><th>Price</th><th>Prediction</th><th>Position</th><th>PnL</th></tr>
</thead><tbody></tbody></table>

<h2>Last 50 Trades</h2>
<table id="tradeHistoryTable">
<thead><tr><th>Time</th><th>Exchange</th><th>Type</th><th>Side</th><th>Price</th><th>BTC Added</th><th>Total BTC</th><th>PnL</th></tr></thead>
<tbody></tbody>
</table>

<h2>Bitfinex Order Book</h2>
<table id="orderbookTable">
<thead><tr><th colspan="2" style="color:red">Asks</th><th colspan="2" style="color:green">Bids</th></tr>
<tr><th>Price</th><th>Size</th><th>Price</th><th>Size</th></tr></thead>
<tbody></tbody></table>

<h2>Aggregated Order Book (Top/Mid/Deep)</h2>
<table id="aggBookTable">
<thead><tr><th>Depth</th><th style="color:red">Ask Liquidity</th><th style="color:green">Bid Liquidity</th><th>Imbalance</th></tr></thead>
<tbody>
<tr data-level="top"><td>Top</td><td>-</td><td>-</td><td>-</td></tr>
<tr data-level="mid"><td>Mid</td><td>-</td><td>-</td><td>-</td></tr>
<tr data-level="deep"><td>Deep</td><td>-</td><td>-</td><td>-</td></tr>
</tbody>
</table>

<h2>VWAP / Volume Profile (1m, 15m, 4h, 1d, 1w, 1M)</h2>
<table id="vwapTable">
<thead><tr><th>TF</th><th>VWAP</th><th>Std</th><th>Total Volume</th></tr></thead>
<tbody>
<tr data-tf="1m"><td>1m</td><td>-</td><td>-</td><td>-</td></tr>
<tr data-tf="15m"><td>15m</td><td>-</td><td>-</td><td>-</td></tr>
<tr data-tf="4h"><td>4h</td><td>-</td><td>-</td><td>-</td></tr>
<tr data-tf="1d"><td>1d</td><td>-</td><td>-</td><td>-</td></tr>
<tr data-tf="1w"><td>1w</td><td>-</td><td>-</td><td>-</td></tr>
<tr data-tf="1M"><td>1M</td><td>-</td><td>-</td><td>-</td></tr>
</tbody>
</table>

</div>

<script>
let lastTotalPnl=null;
let lastExchangePnl={};
let lastSeenTradeTime=null;

async function updateTable(){
    try{
        const res=await fetch('/data');
        const data=await res.json();

        document.getElementById('timestamp').textContent=data.timestamp??'-';
        document.getElementById('balance').textContent=Number(data.balance??0).toFixed(2);

        const totalPnlEl=document.getElementById('total_pnl');
        const totalPnl=Number(data.total_pnl??0);
        totalPnlEl.textContent=totalPnl.toFixed(6);
        totalPnlEl.className=totalPnl>=0?'positive':'negative';
        if(lastTotalPnl!==null) totalPnlEl.classList.add(totalPnl>lastTotalPnl?'pnl-up':'pnl-down');
        lastTotalPnl=totalPnl;

        // Live positions
        const liveBody=document.querySelector('#liveTable tbody'); liveBody.innerHTML='';
        for(const [ex,info] of Object.entries(data.exchanges||{})){
            const pnl=Number(info.pnl??0);
            const row=document.createElement('tr');
            let pnlClass=pnl>=0?'positive':'negative';
            let pnlFlash='';
            if(lastExchangePnl[ex]!==undefined) pnlFlash=pnl>lastExchangePnl[ex]?'pnl-up':'pnl-down';
            lastExchangePnl[ex]=pnl;
            row.innerHTML=`<td>${ex}</td><td>${Number(info.price??0).toFixed(2)}</td><td>${info.prediction!==null?Number(info.prediction).toFixed(2):'-'}</td><td>${info.position??'-'}</td><td class="${pnlClass} ${pnlFlash}">${pnl.toFixed(6)}</td>`;
            liveBody.appendChild(row);
        }

        // Trade history
        const thBody=document.querySelector('#tradeHistoryTable tbody'); thBody.innerHTML='';
        const trades=[...(data.last_trades||[])].slice(-10).reverse();
        for(const trade of trades){
            const row=document.createElement('tr');
            if(lastSeenTradeTime && trade.time>lastSeenTradeTime){
                if(trade.type==='CLOSE') row.classList.add((trade.pnl??0)>=0?'close-win':'close-loss');
                else row.classList.add('add-trade');
            }
            row.innerHTML=`<td>${trade.time}</td><td>${trade.exchange}</td><td>${trade.type}</td><td>${trade.side}</td><td>${Number(trade.price??0).toFixed(2)}</td><td>${trade.btc_added!==null?Number(trade.btc_added).toFixed(8):'-'}</td><td>${trade.total_btc!==null?Number(trade.total_btc).toFixed(8):'-'}</td><td class="${(trade.pnl??0)>=0?'positive':'negative'}">${trade.pnl!==null?Number(trade.pnl).toFixed(6):'-'}</td>`;
            thBody.appendChild(row);
        }
        if(trades.length>0) lastSeenTradeTime=trades[0].time;
    }catch(err){ console.error("LIVE UPDATE ERROR:", err); }
}

setInterval(updateTable,1000);
updateTable();

// ======================
// VWAP AGGREGATOR
// ======================

const TIMEFRAMES = { "1m":60000, "15m":900000, "4h":14400000, "1d":86400000, "1w":604800000, "1M":2592000000 };
const tradeBuffers={}; Object.keys(TIMEFRAMES).forEach(tf=>tradeBuffers[tf]=[]);
const AGG_EXCHANGES=["bitfinex","binance","kraken","bitstamp","okx","huobi","coinbase"];

function addTrade(tf, price, volume, timestamp){
    if(!price || !volume || !timestamp) return;
    if(timestamp<10000000000) timestamp*=1000; // normalize s->ms
    tradeBuffers[tf].push({price,volume,ts:timestamp});
    const cutoff=Date.now()-TIMEFRAMES[tf];
    while(tradeBuffers[tf].length && tradeBuffers[tf][0].ts<cutoff) tradeBuffers[tf].shift();
}

function computeVWAP(tf){
    const trades=tradeBuffers[tf];
    if(trades.length===0) return {vwap:null,std:null,vol:0};
    let sumP=0, sumPV=0, vol=0, arr=[];
    trades.forEach(t=>{ sumPV+=t.price*t.volume; sumP+=t.price*t.volume; vol+=t.volume; arr.push(t.price); });
    const vwap=sumPV/vol;
    const mean=vwap;
    const std=Math.sqrt(arr.reduce((a,p)=>a+Math.pow(p-mean,2),0)/arr.length);
    return {vwap,std,vol};
}

function renderVWAP(){
    Object.keys(TIMEFRAMES).forEach(tf=>{
        const {vwap,std,vol}=computeVWAP(tf);
        const row=document.querySelector(`#vwapTable tbody tr[data-tf='${tf}']`);
        row.cells[1].textContent=vwap?vwap.toFixed(2):'-';
        row.cells[2].textContent=std?std.toFixed(2):'-';
        row.cells[3].textContent=vol?vol.toFixed(4):'-';
    });
}

setInterval(renderVWAP,1000);

// ======================
// AGGREGATED BOOK
// ======================

const aggBooks={};
AGG_EXCHANGES.forEach(ex=>aggBooks[ex]={bids:new Map(),asks:new Map(),mid:null});
const aggResult={top:{bid:0,ask:0},mid:{bid:0,ask:0},deep:{bid:0,ask:0}};
const AGG_DEPTHS={top:0.001,mid:0.005,deep:0.015};

function calcMid(bids,asks){
    if(!bids.size || !asks.size) return null;
    return (Math.max(...bids.keys())+Math.min(...asks.keys()))/2;
}

function resetAgg(){ for(const lvl in aggResult){ aggResult[lvl].bid=0; aggResult[lvl].ask=0; } }

function aggregateBooks(){
    resetAgg();
    AGG_EXCHANGES.forEach(ex=>{
        const book=aggBooks[ex];
        if(!book.mid) return;
        book.bids.forEach((size,price)=>{
            const d=(book.mid-price)/book.mid;
            if(d<=AGG_DEPTHS.deep){
                if(d<=AGG_DEPTHS.top) aggResult.top.bid+=size;
                else if(d<=AGG_DEPTHS.mid) aggResult.mid.bid+=size;
                else aggResult.deep.bid+=size;
            }
        });
        book.asks.forEach((size,price)=>{
            const d=(price-book.mid)/book.mid;
            if(d<=AGG_DEPTHS.deep){
                if(d<=AGG_DEPTHS.top) aggResult.top.ask+=size;
                else if(d<=AGG_DEPTHS.mid) aggResult.mid.ask+=size;
                else aggResult.deep.ask+=size;
            }
        });
    });
}

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

setInterval(()=>{aggregateBooks(); renderAggTable();},250);

</script>
</body>
</html>
"""

# =============================
# ROUTES
# =============================
@app.get("/", response_class=HTMLResponse)
def home(): return HTML_PAGE

@app.get("/data")
def get_data():
    try: return requests.get(API_URL, timeout=5).json()
    except: return {"timestamp":"-","balance":0,"total_pnl":0,"exchanges":{},"last_trades":[]}

# =============================
# MAIN
# =============================
if __name__=="__main__":
    public_url = ngrok.connect(addr=LOCAL_PORT, bind_tls=True)
    print(f"Public URL: {public_url}")
    print(f"Ngrok dashboard port: {NGROK_DASHBOARD_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=LOCAL_PORT)
