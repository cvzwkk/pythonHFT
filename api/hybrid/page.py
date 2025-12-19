import os
import time
import requests

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

from pyngrok import ngrok, conf

# =========================
# CONFIG
# =========================
NGROK_AUTH_TOKEN = os.getenv("36xkALQDnxGLwLU3o1CIo2SKsvt_7cUEHiQnMbNC2Snv5bfKk")

PORT = 8080

ZLEMA_API = "http://127.0.0.1:9001/zlema/data"
HMA_API   = "http://127.0.0.1:9002/hma/data"

REFRESH_SECONDS = 2

# =========================
# FASTAPI
# =========================
app = FastAPI()

# =========================
# HELPERS
# =========================
def fetch(url):
    try:
        return requests.get(url, timeout=1).json()
    except Exception as e:
        return {"error": str(e)}

def row(model):
    t = model.get("last_trades", [{}])[0]
    return f"""
    <tr>
        <td>{model.get("model", "-")}</td>
        <td>{t.get("exchange", "-")}</td>
        <td>{t.get("price", "-")}</td>
        <td>{t.get("prediction", "-")}</td>
        <td>{t.get("position", "-")}</td>
        <td>{t.get("pnl", "-")}</td>
        <td>{time.strftime('%H:%M:%S', time.localtime(t.get("timestamp", 0)))}</td>
    </tr>
    """

# =========================
# ROUTES
# =========================
@app.get("/", response_class=HTMLResponse)
def dashboard():
    zlema = fetch(ZLEMA_API)
    hma   = fetch(HMA_API)

    return f"""
    <html>
    <head>
        <title>HFT Models Dashboard</title>
        <meta http-equiv="refresh" content="{REFRESH_SECONDS}">
        <style>
            body {{
                font-family: monospace;
                background: #0b0b0b;
                color: #e0e0e0;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
            }}
            th, td {{
                border: 1px solid #333;
                padding: 6px;
                text-align: center;
            }}
            th {{
                background: #111;
            }}
            h2 {{
                margin-top: 10px;
            }}
        </style>
    </head>
    <body>
        <h2>📊 Live Trading Models</h2>

        <table>
            <tr>
                <th>Model</th>
                <th>Exchange</th>
                <th>Price</th>
                <th>Prediction</th>
                <th>Position</th>
                <th>PnL</th>
                <th>Time</th>
            </tr>
            {row(zlema)}
            {row(hma)}
        </table>
    </body>
    </html>
    """

# =========================
# START
# =========================
if __name__ == "__main__":
    if NGROK_AUTH_TOKEN:
        conf.get_default().auth_token = NGROK_AUTH_TOKEN
        public_url = ngrok.connect(PORT, bind_tls=True)
        print(f"🌐 Public dashboard: {public_url}")

    uvicorn.run(app, host="0.0.0.0", port=PORT)
