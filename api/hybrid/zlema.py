# api/zlema/zlema.py

import threading
import time
import numpy as np
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

# =========================
# SHARED STATE (THREAD SAFE)
# =========================
latest_zlema = {
    "exchange": "BINANCE",
    "price": None,
    "prediction": None,
    "position": None,
    "pnl": None,
    "timestamp": None
}

lock = threading.Lock()

# =========================
# ZLEMA CORE LOGIC (example)
# =========================
def run_zlema_loop():
    global latest_zlema

    price = 50000.0

    while True:
        price += np.random.randn() * 2
        prediction = price + np.random.randn() * 5

        with lock:
            latest_zlema.update({
                "price": round(price, 2),
                "prediction": round(prediction, 2),
                "position": "LONG" if prediction > price else "SHORT",
                "pnl": round(np.random.randn() * 10, 2),
                "timestamp": time.time()
            })

        time.sleep(1)  # 1-second HFT loop

# =========================
# FASTAPI
# =========================
app = FastAPI()

@app.get("/zlema/data")
def zlema_data():
    with lock:
        return JSONResponse({
            "model": "ZLEMA",
            "last_trades": [latest_zlema]
        })

# =========================
# START
# =========================
if __name__ == "__main__":
    threading.Thread(target=run_zlema_loop, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=9001)
