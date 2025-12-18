#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import json
from collections import defaultdict, deque
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import uvicorn
from pyngrok import ngrok, conf
import websockets

# =============================
# CONFIG
# =============================
NGROK_AUTH_TOKEN = "37008jtAxiSWPEdzp7OtNvmXcxv_55UUkotksc7ztTYaM2huH"
LOCAL_PORT = 8989

if NGROK_AUTH_TOKEN:
    conf.get_default().auth_token = NGROK_AUTH_TOKEN

# =============================
# STORAGE
# =============================
ORDERBOOK = defaultdict(lambda: {"bids": {}, "asks": {}})
TRADES = deque(maxlen=500)

# =============================
# FASTAPI APP
# =============================
app = FastAPI()

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Live Orderbook + Trades</title>
<script src="https://cdn.plot.ly/plotly-2.30.0.min.js"></script>
<style>body{font-family:Arial;margin:20px;}</style>
</head>
<body>
<h2>Live Orderbook Depth + Trades</h2>
<div id="orderbookDepth" style="width:100%;height:500px;"></div>
<script>
let lastBids=[], lastAsks=[], depthReady=false;
function cumulative(levels){let sum=0;return levels.map(([p,s])=>{sum+=s;return[p,sum];});}
function highlightChanges(oldLevels,newLevels){let colors=new Array(newLevels.length).fill('rgba(0,0,0,0)');const oldMap=new Map(oldLevels.map(([p,s])=>[p,s]));newLevels.forEach(([p,s],idx)=>{if(!oldMap.has(p)||oldMap.get(p)!==s)colors[idx]='yellow';});return colors;}
function renderOrderbook(bids,asks,trades=[]){
    const bidCum=cumulative(bids), askCum=cumulative(asks);
    const bidColors=highlightChanges(lastBids,bids), askColors=highlightChanges(lastAsks,asks);
    const bidTrace={x:bidCum.map(d=>d[0]),y:bidCum.map(d=>d[1]),type:"scatter",mode:"lines+markers",fill:"tozeroy",name:"Bids",line:{color:"rgb(0,180,0)",width:2},marker:{color:bidColors,size:6},fillcolor:"rgba(0,180,0,0.35)"}; 
    const askTrace={x:askCum.map(d=>d[0]),y:askCum.map(d=>d[1]),type:"scatter",mode:"lines+markers",fill:"tozeroy",name:"Asks",line:{color:"rgb(220,0,0)",width:2},marker:{color:askColors,size:6},fillcolor:"rgba(220,0,0,0.35)"};
    const tradeTrace={x:trades.map(t=>t.price),y:trades.map(t=>t.cum||0),type:"scatter",mode:"markers",name:"Trades",marker:{color:trades.map(t=>t.side==="BUY"?"lime":"red"),size:10,opacity:0.8}};
    const layout={margin:{l:60,r:20,t:20,b:40},xaxis:{title:"Price"},yaxis:{title:"Cumulative BTC"},legend:{orientation:"h",y:1.15},transition:{duration:100,easing:"cubic-in-out"}};
    if(!depthReady){Plotly.newPlot("orderbookDepth",[bidTrace,askTrace,tradeTrace],layout,{displayModeBar:false,responsive:true});depthReady=true;}
    else{Plotly.react("orderbookDepth",[bidTrace,askTrace,tradeTrace],layout);}
    setTimeout(()=>{bidTrace.marker.color=new Array(bids.length).fill('rgb(0,180,0)');askTrace.marker.color=new Array(asks.length).fill('rgb(220,0,0)');Plotly.react("orderbookDepth",[bidTrace,askTrace,tradeTrace],layout);},100);
    lastBids=bids; lastAsks=asks;
}
let ws = new WebSocket("ws://localhost:8080/ws");
ws.onmessage = event => {const data=JSON.parse(event.data);renderOrderbook(data.bids,data.asks,data.trades||[]);}
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def home():
    return HTML_PAGE

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        try:
            bids, asks = [], []
            for ex in ORDERBOOK.values():
                bids.extend(list(ex["bids"].items()))
                asks.extend(list(ex["asks"].items()))
            bids = sorted(bids,key=lambda x:x[0],reverse=True)[:30]
            asks = sorted(asks,key=lambda x:x[0])[:30]
            trades = list(TRADES)[:50]
            await websocket.send_text(json.dumps({"bids":bids,"asks":asks,"trades":trades}))
            await asyncio.sleep(0.05)
        except:
            break

# =============================
# BINANCE WS
# =============================
async def binance_orderbook_ws():
    url = "wss://stream.binance.com:9443/ws/btcusdt@depth@100ms"
    async with websockets.connect(url) as ws:
        async for msg in ws:
            data = json.loads(msg)
            book = ORDERBOOK["Binance"]
            for p,s in data.get("b",[]): p,s=float(p),float(s); book["bids"][p]=s if s!=0 else book["bids"].pop(p,None)
            for p,s in data.get("a",[]): p,s=float(p),float(s); book["asks"][p]=s if s!=0 else book["asks"].pop(p,None)

async def binance_trades_ws():
    url = "wss://stream.binance.com:9443/ws/btcusdt@trade"
    async with websockets.connect(url) as ws:
        async for msg in ws:
            data=json.loads(msg)
            TRADES.appendleft({"exchange":"Binance","price":float(data["p"]),"quantity":float(data["q"]),"side":"BUY" if not data["m"] else "SELL","time":data["T"]})

# =============================
# BITSTAMP WS
# =============================
async def bitstamp_orderbook_ws():
    url = "wss://ws.bitstamp.net"
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps({"event":"bts:subscribe","data":{"channel":"order_book_btcusd"}}))
        async for msg in ws:
            data=json.loads(msg)
            if data.get("event")=="data":
                book = ORDERBOOK["Bitstamp"]
                book["bids"]={float(p):float(s) for p,s in data["data"]["bids"]}
                book["asks"]={float(p):float(s) for p,s in data["data"]["asks"]}

# =============================
# MAIN
# =============================
if __name__=="__main__":
    public_url = ngrok.connect(LOCAL_PORT, bind_tls=True)
    print(f"Public URL: {public_url}")
    loop = asyncio.get_event_loop()
    loop.create_task(binance_orderbook_ws())
    loop.create_task(binance_trades_ws())
    loop.create_task(bitstamp_orderbook_ws())
    uvicorn.run(app, host="0.0.0.0", port=LOCAL_PORT)
