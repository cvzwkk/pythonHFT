#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import aiohttp
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pyngrok import ngrok
from datetime import datetime
import nest_asyncio

# =========================
# NGROK CONFIG
# =========================
NGROK_AUTH_TOKEN = "37FdHYm49BxuhlghpNJqDg9cmNX_5Z4XgJDUsEykxpkNVrn8T"  # <-- replace with your token
ngrok.set_auth_token(NGROK_AUTH_TOKEN)

# =========================
# BOT URLs
# =========================
BOT_URLS = {
    "CovEMA Bot": "http://127.0.0.1:8003/live",
    "HULL Bot": "http://127.0.0.1:8000/live",
    "SWMA Bot": "http://127.0.0.1:8004/live"
}

# =========================
# FASTAPI APP
# =========================
app = FastAPI(title="HFT Bots Live Dashboard")

# =========================
# FETCH DATA FROM EACH BOT
# =========================
async def fetch_bot_data(session, name, url):
    try:
        async with session.get(url, timeout=5) as r:
            data = await r.json()
            return name, data
    except Exception as e:
        return name, {"error": str(e)}

async def gather_all_bot_data():
    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_bot_data(session, name, url)
            for name, url in BOT_URLS.items()
        ]
        results = await asyncio.gather(*tasks)
        return dict(results)

# =========================
# GENERATE HTML
# =========================
def generate_html(data):
    html = f"""
    <html>
        <head>
            <title>HFT Bots Dashboard</title>
            <meta http-equiv="refresh" content="1">
            <style>
                body {{ font-family: Arial; background-color: #111; color: #eee; }}
                table {{ border-collapse: collapse; width: 90%; margin: auto; }}
                th, td {{ border: 1px solid #555; padding: 8px; text-align: center; }}
                th {{ background-color: #222; }}
                tr:nth-child(even) {{ background-color: #1a1a1a; }}
            </style>
        </head>
        <body>
            <h1 style="text-align:center;">HFT Bots Live Dashboard</h1>
            <table>
                <tr>
                    <th>Bot</th>
                    <th>Balance (USD)</th>
                    <th>Balance (BTC)</th>
                    <th>PnL (USD)</th>
                    <th>PnL (BTC)</th>
                    <th>Last Update</th>
                </tr>
    """
    for bot_name, bot_data in data.items():
        if "error" in bot_data:
            html += f"""
                <tr>
                    <td>{bot_name}</td>
                    <td colspan="5" style="color:red;">Error: {bot_data['error']}</td>
                </tr>
            """
        else:
            balance_usd = bot_data.get("balance", 0)
            total_pnl = bot_data.get("total_pnl", 0)
            btc_total = sum([v.get("btc_total", 0) for v in bot_data.get("totals", {}).values()])
            btc_pnl = sum([v.get("btc_total", 0) for v in bot_data.get("totals", {}).values()])  # optional, same as btc_total
            last_update = bot_data.get("timestamp", "")

            html += f"""
                <tr>
                    <td>{bot_name}</td>
                    <td>${balance_usd:,.2f}</td>
                    <td>{btc_total:.6f} BTC</td>
                    <td>${total_pnl:,.2f}</td>
                    <td>{btc_pnl:.6f} BTC</td>
                    <td>{last_update}</td>
                </tr>
            """
    html += "</table></body></html>"
    return html

# =========================
# FASTAPI ROUTES
# =========================
@app.get("/", response_class=HTMLResponse)
async def dashboard():
    data = await gather_all_bot_data()
    html = generate_html(data)
    return HTMLResponse(content=html)

@app.get("/api", response_class=JSONResponse)
async def api_dashboard():
    data = await gather_all_bot_data()
    return JSONResponse(content=data)

# =========================
# RUN SERVER
# =========================
async def main():
    public_url = ngrok.connect(8000, "http")
    print(f"Dashboard Public URL: {public_url}")

    import uvicorn
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="critical")
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.run(main())
