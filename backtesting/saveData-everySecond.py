#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import websockets
import json
import pandas as pd
from datetime import datetime, timezone

PAIR = "btcusd"
WS_URL = "wss://ws.bitstamp.net"
FILENAME = "btcusd_1s.csv"

# Store 1-second candles
candles = {}

def update_candle(trade):
    ts = datetime.fromtimestamp(float(trade['timestamp']), tz=timezone.utc)
    sec = ts.replace(microsecond=0)  # 1-second bucket
    price = float(trade['price'])
    volume = float(trade['amount'])

    if sec not in candles:
        candles[sec] = {
            'open': price,
            'high': price,
            'low': price,
            'close': price,
            'volume': volume
        }
    else:
        candle = candles[sec]
        candle['high'] = max(candle['high'], price)
        candle['low'] = min(candle['low'], price)
        candle['close'] = price
        candle['volume'] += volume

async def main():
    async with websockets.connect(WS_URL) as ws:
        # Subscribe to live trades
        subscribe_msg = {
            "event": "bts:subscribe",
            "data": {"channel": f"live_trades_{PAIR}"}
        }
        await ws.send(json.dumps(subscribe_msg))
        print(f"Subscribed to live trades for {PAIR}...")

        while True:
            message = await ws.recv()
            data = json.loads(message)

            if data.get('event') == 'trade':
                trade_data = data['data']
                update_candle(trade_data)

            # Save to CSV every 10 seconds
            now = datetime.now(timezone.utc)
            if now.second % 10 == 0:
                if candles:
                    df = pd.DataFrame([
                        {'timestamp': k, **v} for k, v in candles.items()
                    ])
                    df.sort_values('timestamp', inplace=True)
                    df.to_csv(FILENAME, index=False)
                    print(f"Saved {len(df)} 1-second candles to {FILENAME}")

if __name__ == "__main__":
    asyncio.run(main())
