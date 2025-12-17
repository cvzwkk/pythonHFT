import os
import asyncio
import aiohttp
import numpy as np
import pandas as pd
import json
from collections import deque
from datetime import datetime
import nest_asyncio
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
from pyngrok import ngrok

nest_asyncio.apply()

# =========================
# NGROK AUTH
# =========================
NGROK_AUTH_TOKEN = "36xhpiAn5cRi9ObeqeKYdJBZ13k_3z1GytiAf4Sn3czxWwNBm"
ngrok.set_auth_token(NGROK_AUTH_TOKEN)

# =========================
# SETTINGS
# =========================
ORDERBOOK_APIS = {
    "Coinbase": "https://api.exchange.coinbase.com/products/BTC-USD/book?level=2",
    "Kraken": "https://api.kraken.com/0/public/Depth?pair=XBTUSD&count=10",
    "Bitstamp": "https://www.bitstamp.net/api/v2/order_book/btcusd/",
    "Bitfinex": "https://api.bitfinex.com/v1/book/btcusd"
}

BALANCE_FILE = "balance.json"

def safe_return(v):
    return None if v is None or np.isnan(v) or np.isinf(v) else float(v)

def log_returns(prices):
    return np.diff(np.log(prices + 1e-8))

def micro_price(bid, ask, bid_sz, ask_sz):
    return (ask * bid_sz + bid * ask_sz) / (bid_sz + ask_sz + 1e-8)

# =========================
# LOAD / SAVE STATE
# =========================
def save_trader_state(trader):
    state = {
        "balance": trader.balance,
        "pnl": trader.pnl,
        "positions": trader.positions,
        "trades": list(trader.trades)
    }
    with open(BALANCE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def load_trader_state():
    if os.path.exists(BALANCE_FILE):
        try:
            return json.load(open(BALANCE_FILE))
        except:
            pass
    return {"balance": 1000.0, "pnl": {}, "positions": {}, "trades": []}

# =========================
# MODELS
# =========================
def predict_hma_robust(prices, period=16):
    if len(prices)<4: return None
    prices=np.array(prices,dtype=np.float64)
    prices=np.where(np.isfinite(prices),prices,np.nan)
    prices=pd.Series(prices).fillna(method="ffill").fillna(method="bfill").values
    def wma(arr,n):
        n=min(n,len(arr))
        weights=np.arange(1,n+1)
        return np.dot(arr[-n:],weights)/weights.sum()
    half=max(2,period//2)
    hma=2*wma(prices,half)-wma(prices,period)
    slope=np.polyfit(np.arange(min(half,len(prices)-1)+1),prices[-min(half,len(prices)-1)-1:],1)[0]
    returns=np.diff(np.log(prices+1e-9))
    momentum=np.sum(np.exp(-np.linspace(0,3,len(returns)))*returns) if len(returns)>1 else 0.0
    vol=np.std(returns[-half:])+1e-9
    vol_boost=np.tanh(vol*80)
    z=(np.log(prices[-1])-np.mean(np.log(prices)))/(np.std(np.log(prices))+1e-9)
    mr_factor=np.tanh(-0.3*z)
    forecast=hma+slope*(1+vol_boost)+momentum*0.5+mr_factor*vol*0.3
    return safe_return(forecast)

def exotic_hma(prices, period=16):
    try:
        prices=np.array(prices,dtype=np.float64)
        prices=np.where(np.isfinite(prices),prices,np.nan)
        prices=pd.Series(prices).fillna(method="ffill").fillna(method="bfill").values
        n=max(2,min(period,len(prices)))
        half=max(2,n//2)
        def wma(arr,n):
            n=min(n,len(arr))
            weights=np.arange(1,n+1)
            return np.dot(arr[-n:],weights)/weights.sum()
        hma=2*wma(prices,half)-wma(prices,n)
        x=np.arange(min(5,len(prices)))
        slope=np.polyfit(x,prices[-len(x):],1)[0]
        log_ret=np.diff(np.log(prices+1e-8))
        vol=np.std(log_ret[-10:])+1e-8
        vol_boost=np.tanh(vol*80)
        z=(np.log(prices[-1])-np.mean(np.log(prices)))/(np.std(np.log(prices))+1e-8)
        mr_factor=np.tanh(-0.3*z)
        momentum=np.sum(np.exp(-np.linspace(0,3,len(log_ret)))*log_ret) if len(log_ret)>1 else 0.0
        forecast=hma+slope*(1+vol_boost)+momentum*0.5+mr_factor*vol*0.3
        return float(forecast)
    except:
        return float(prices[-1])

def exotic_covwma(prices, period=12):
    try:
        prices=np.array(prices,dtype=np.float64)
        prices=np.where(np.isfinite(prices),prices,np.nan)
        prices=pd.Series(prices).fillna(method="ffill").fillna(method="bfill").values
        n=min(period,len(prices))
        if n<2: return float(prices[-1])
        returns=np.diff(prices)/(prices[:-1]+1e-8)
        cov_matrix=np.cov(np.vstack([returns[-n:], np.arange(n)]))
        weights=cov_matrix[1]/(cov_matrix[1].sum()+1e-8)
        covwma=np.sum(prices[-n:]*weights)
        momentum=np.sum(np.exp(-np.linspace(0,3,n))*returns[-n:])
        vol=np.std(returns[-n:])+1e-8
        vol_boost=np.tanh(vol*50)
        forecast=covwma+momentum*0.5+vol_boost*vol
        return safe_return(forecast)
    except:
        return float(prices[-1])

def exotic_macd(prices, fast=12, slow=26, signal=9):
    try:
        prices=np.array(prices,dtype=np.float64)
        prices=np.where(np.isfinite(prices),prices,np.nan)
        prices=pd.Series(prices).fillna(method="ffill").fillna(method="bfill").values
        if len(prices)<slow: return float(prices[-1])
        ema_fast=pd.Series(prices).ewm(span=fast,adjust=False).mean().values[-1]
        ema_slow=pd.Series(prices).ewm(span=slow,adjust=False).mean().values[-1]
        macd=ema_fast-ema_slow
        macd_hist=macd-pd.Series(prices).ewm(span=signal,adjust=False).mean().values[-1]
        returns=np.diff(np.log(prices+1e-8))
        vol=np.std(returns[-slow:])+1e-8
        mr_factor=np.tanh(-(prices[-1]-prices.mean())/(prices.std()+1e-8))
        forecast=prices[-1]+macd_hist*0.7+vol*0.3+mr_factor*0.2
        return safe_return(forecast)
    except:
        return float(prices[-1])

MODELS = {
    "HMA": predict_hma_robust,
    "HMA2": exotic_hma,
    "CoVWMA": exotic_covwma,
    "MACD": exotic_macd
}

# =========================
# PAPER TRADER
# =========================
class PaperTrader:
    def __init__(self, balance=1000):
        state=load_trader_state()
        self.balance=state["balance"]
        self.pnl=state.get("pnl",{})
        self.positions=state.get("positions",{})
        self.trades=deque(state.get("trades",[]), maxlen=50)

    def open_trade(self, key, side, price, size=1.0, model=None):
        if self.positions.get(key) is None:
            self.positions[key]={"side":side,"entry":price,"size":size,"model":model}

    def close_trade(self, key, price):
        p=self.positions.get(key)
        if p:
            size=p.get("size",1.0)
            pnl=(price-p["entry"])*size if p["side"]=="buy" else (p["entry"]-price)*size
            self.balance+=pnl
            self.pnl[p.get("model","unknown")]=self.pnl.get(p.get("model","unknown"),0.0)+pnl
            trade_record={
                "exchange_model":key,
                "model":p.get("model"),
                "side":p["side"],
                "entry":p["entry"],
                "exit":price,
                "size":size,
                "pnl":pnl,
                "time":datetime.now().isoformat()
            }
            self.trades.append(trade_record)
            self.positions[key]=None

    def total_pnl(self):
        return sum(self.pnl.values())

# =========================
# FETCH ORDERBOOK
# =========================
async def fetch_price(ex,url,session):
    try:
        async with session.get(url,timeout=5) as r:
            d=await r.json()
            if ex=="Coinbase":
                bid,bid_sz=map(float,d["bids"][0])
                ask,ask_sz=map(float,d["asks"][0])
            elif ex=="Kraken":
                book=list(d["result"].values())[0]
                bid,bid_sz=map(float,book["bids"][0][:2])
                ask,ask_sz=map(float,book["asks"][0][:2])
            elif ex=="Bitstamp":
                bid,bid_sz=float(d["bids"][0][0]),float(d["bids"][0][1])
                ask,ask_sz=float(d["asks"][0][0]),float(d["asks"][0][1])
            else:
                bid=float(d["bids"][0]["price"])
                bid_sz=float(d["bids"][0]["amount"])
                ask=float(d["asks"][0]["price"])
                ask_sz=float(d["asks"][0]["amount"])
            return ex,micro_price(bid,ask,bid_sz,ask_sz)
    except:
        return ex,None

# =========================
# FASTAPI
# =========================
app=FastAPI()
trader=PaperTrader()
history={e:deque(maxlen=60) for e in ORDERBOOK_APIS}

@app.get("/live")
async def live_data():
    output={}
    for ex, prices in history.items():
        model_preds={name: func(list(prices)) for name,func in MODELS.items()}
        output[ex]={"last_price":prices[-1] if prices else None,"models":model_preds}
    return JSONResponse({
        "balance":trader.balance,
        "total_pnl":trader.total_pnl(),
        "positions":trader.positions,
        "pnl":trader.pnl,
        "last_trades":list(trader.trades),
        "exchanges":output
    })

async def update_prices():
    async with aiohttp.ClientSession() as session:
        while True:
            results=await asyncio.gather(*[fetch_price(e,u,session) for e,u in ORDERBOOK_APIS.items()])
            for ex, price in results:
                if price:
                    history[ex].append(price)
                    for model_name, func in MODELS.items():
                        pred=func(list(history[ex]))
                        key=f"{ex}_{model_name}"
                        pos=trader.positions.get(key)
                        if pred is not None:
                            vol=np.std(log_returns(np.array(history[ex])))+1e-8
                            threshold=price*vol*0.2
                            if pos is None:
                                if pred>price+threshold:
                                    trader.open_trade(key,"buy",price,model=model_name)
                                elif pred<price-threshold:
                                    trader.open_trade(key,"sell",price,model=model_name)
                            else:
                                if pos["side"]=="buy" and pred<price-threshold:
                                    trader.close_trade(key,price)
                                elif pos["side"]=="sell" and pred>price+threshold:
                                    trader.close_trade(key,price)
            save_trader_state(trader)
            await asyncio.sleep(1)

def start_app():
    loop=asyncio.get_event_loop()
    loop.create_task(update_prices())
    public_url=ngrok.connect(8000)
    print(f"Public ngrok URL: {public_url}")
    uvicorn.run(app, host="127.0.0.1", port=8000)

if __name__=="__main__":
    start_app()
