# live_table_ngrok_fixed.py
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import requests
from pyngrok import ngrok, conf
import uvicorn

# -----------------------------
# CONFIGURE VARIABLES HERE
# -----------------------------
NGROK_AUTH_TOKEN = "36xkALQDnxGLwLU3o1CIo2SKsvt_7cUEHiQnMbNC2Snv5bfKk"  # <-- replace with your ngrok token
NGROK_DASHBOARD_PORT = 4041                       # <-- change dashboard port if needed
LOCAL_PORT = 8080 # <-- FastAPI server port

# Set ngrok auth token
if NGROK_AUTH_TOKEN:
    conf.get_default().auth_token = NGROK_AUTH_TOKEN

# Set ngrok dashboard port
conf.get_default().ngrok_port = NGROK_DASHBOARD_PORT

# API endpoint to fetch live data
API_URL = "https://tiesha-nonfissile-jarvis.ngrok-free.dev/live"

# -----------------------------
# FastAPI app
# -----------------------------
app = FastAPI()

# HTML page with live-updating table
# HTML page with live-updating table and trades history
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Hull Live Trading Table</title>
<style>
  body { font-family: Arial; margin: 20px; }
  table { border-collapse: collapse; width: 100%; margin-bottom: 30px; }
  th, td { border: 1px solid #ccc; padding: 6px; text-align: center; }
  th { background-color: #f4f4f4; }
  .negative { color: red; }
  .positive { color: green; }
</style>
</head>
<body>

<h2>Live Trading Data</h2>
<p>Last updated: <span id="timestamp">-</span></p>
<p>
  Balance: <b><span id="balance">-</span></b> |
  Total PnL: <b><span id="total_pnl">-</span></b>
</p>

<!-- CURRENT STATE -->
<table id="liveTable">
  <thead>
    <tr>
      <th>Exchange</th>
      <th>Price</th>
      <th>Prediction HMA</th>
      <th>Position</th>
      <th>PnL</th>
    </tr>
  </thead>
  <tbody></tbody>
</table>

<h2>Last 50 Trades</h2>
<table id="tradeHistoryTable">
  <thead>
    <tr>
      <th>Time</th>
      <th>Exchange</th>
      <th>Type</th>
      <th>Side</th>
      <th>Price</th>
      <th>Added BTC</th>
      <th>Total BTC</th>
      <th>PnL</th>
    </tr>
  </thead>
  <tbody></tbody>
</table>

<script>
async function fetchData() {
  try {
    const res = await fetch("/proxy");
    const data = await res.json();

    document.getElementById("timestamp").textContent = data.timestamp;
    document.getElementById("balance").textContent = data.balance.toFixed(2);
    document.getElementById("total_pnl").textContent = data.total_pnl.toFixed(2);

    // ======================
    // LIVE TABLE
    // ======================
    const tbody = document.querySelector("#liveTable tbody");
    tbody.innerHTML = "";

    for (const [ex, d] of Object.entries(data.exchanges)) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${ex}</td>
        <td>${d.price.toFixed(2)}</td>
        <td>${d.prediction_hma ? d.prediction_hma.toFixed(2) : "-"}</td>
        <td>${d.position}</td>
        <td class="${d.pnl >= 0 ? "positive" : "negative"}">
          ${d.pnl.toFixed(2)}
        </td>
      `;
      tbody.appendChild(tr);
    }

    // ======================
    // TRADE HISTORY
    // ======================
    const tradeBody = document.querySelector("#tradeHistoryTable tbody");
    tradeBody.innerHTML = "";

    data.last_trades.slice(-50).reverse().forEach(t => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${t.time || "-"}</td>
        <td>${t.exchange}</td>
        <td>${t.type}</td>
        <td>${t.side}</td>
        <td>${t.price ? t.price.toFixed(2) : "-"}</td>
        <td>${t.btc_added ? t.btc_added.toFixed(8) : "-"}</td>
        <td>${t.total_btc ? t.total_btc.toFixed(8) : "-"}</td>
        <td class="${(t.pnl || 0) >= 0 ? "positive" : "negative"}">
          ${t.pnl !== null && t.pnl !== undefined ? t.pnl.toFixed(4) : "-"}
        </td>
      `;
      tradeBody.appendChild(tr);
    });

  } catch (err) {
    console.error(err);
  }
}

setInterval(fetchData, 1000);
fetchData();
</script>

</body>
</html>
"""

# Route for HTML page
@app.get("/", response_class=HTMLResponse)
def home():
    return HTML_PAGE

# Route for live API data
@app.get("/data")
def get_data():
    try:
        r = requests.get(API_URL, timeout=5)
        return r.json()
    except:
        return {"timestamp":"-", "balance":0, "total_pnl":0, "exchanges":{}}

# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    # Open ngrok tunnel (HTTP) on LOCAL_PORT, dashboard on NGROK_DASHBOARD_PORT
    public_url = ngrok.connect(addr=LOCAL_PORT, bind_tls=True)
    print(f"Public URL: {public_url}")
    print(f"Ngrok dashboard port: {NGROK_DASHBOARD_PORT}")

    # Run FastAPI server
    uvicorn.run(app, host="0.0.0.0", port=LOCAL_PORT)
