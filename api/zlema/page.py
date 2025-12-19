#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import requests
from pyngrok import ngrok, conf
import uvicorn

# -----------------------------
# CONFIG
# -----------------------------

NGROK_AUTH_TOKEN    = "36xkALQDnxGLwLU3o1CIo2SKsvt_7cUEHiQnMbNC2Snv5bfKk"
NGROK_DASHBOARD_PORT= 4041
LOCAL_PORT          = 8080

# Base API URLs for data
ZLEMA_API_URL       = "https://tiesha-nonfissile-jarvis.ngrok-free.dev/live"
HMA_API_URL         = "https://tiesha-nonfissile-jarvis.ngrok-free.dev/live"

# HTML templates
HTML_TEMPLATE = """
<title>{title}</title>
<h1>{title}</h1>
<div>Last updated: -</div>
<div>Balance: - | Total PnL: -</div>
<hr>
<table border="1">
<tr><th>Exchange</th><th>Price</th><th>Prediction</th><th>Position</th><th>PnL</th></tr>
{rows}
</table>
"""

# -----------------------------
# SETUP NGROK
# -----------------------------

if NGROK_AUTH_TOKEN:
    conf.get_default().auth_token = NGROK_AUTH_TOKEN
    conf.get_default().ngrok_port = NGROK_DASHBOARD_PORT

# -----------------------------
# FASTAPI APP
# -----------------------------

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def root():
    return """
    <h2>Multi-endpoint Server</h2>
    <ul>
      <li><a href="/zlema">/zlema</a></li>
      <li><a href="/hma">/hma</a></li>
    </ul>
    """

# --- ZLEMA UI ---

@app.get("/zlema", response_class=HTMLResponse)
def page_zlema():
    data = fetch_json(ZLEMA_API_URL)
    rows = format_table_rows(data)
    return HTML_TEMPLATE.format(title="ZLEMA Live Trading", rows=rows)

@app.get("/zlema/data")
def data_zlema():
    return JSONResponse(fetch_json(ZLEMA_API_URL))

# --- HMA UI ---

@app.get("/hma", response_class=HTMLResponse)
def page_hma():
    data = fetch_json(HMA_API_URL)
    rows = format_table_rows(data)
    return HTML_TEMPLATE.format(title="HMA Live Trading", rows=rows)

@app.get("/hma/data")
def data_hma():
    return JSONResponse(fetch_json(HMA_API_URL))

# -----------------------------
# HELPERS
# -----------------------------

def fetch_json(url):
    try:
        return requests.get(url, timeout=5).json()
    except Exception as e:
        return {"error": str(e)}

def format_table_rows(data):
    rows = ""
    last_trades = data.get("last_trades", [])
    for t in last_trades:
        rows += "<tr>"
        rows += f"<td>{t.get('exchange', '-')}</td>"
        rows += f"<td>{t.get('price', '-') }</td>"
        rows += f"<td>{t.get('prediction', '-') }</td>"
        rows += f"<td>{t.get('position', '-') }</td>"
        rows += f"<td>{t.get('pnl', '-') }</td>"
        rows += "</tr>"
    return rows

# -----------------------------
# RUN SERVER + NGROK
# -----------------------------

if __name__ == "__main__":
    public_url = ngrok.connect(addr=LOCAL_PORT, bind_tls=True)
    print(f"📡 Public URL: {public_url}")
    print(f"🔧 Ngrok Dashboard: http://127.0.0.1:{NGROK_DASHBOARD_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=LOCAL_PORT)
