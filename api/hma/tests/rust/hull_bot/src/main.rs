mod ffi;
mod market;
mod trader;

use axum::{routing::get, Router, Json};
use serde_json::json;
use std::{sync::{Arc, Mutex}, net::SocketAddr};
use core_affinity;
use futures_util::{StreamExt};
use tokio_tungstenite::connect_async;
use url::Url;

use market::MarketData;
use trader::Trader;

#[tokio::main]
async fn main() {
    // Pin CPU core
    if let Some(core) = core_affinity::get_core_ids().and_then(|c| c.get(0).cloned()) {
        core_affinity::set_for_current(core);
    }

    let md = Arc::new(Mutex::new(MarketData::new(1024)));
    let trader = Arc::new(Mutex::new(Trader::new()));

    // HTTP endpoint
    let app = Router::new().route("/live", get({
        let md = md.clone();
        let trader = trader.clone();
        move || {
            let md = md.lock().unwrap();
            let t = trader.lock().unwrap();
            Json(json!({
                "last_price": md.prices.last().unwrap_or(&0.0),
                "balance": t.balance,
                "position": t.position,
                "pnl": t.pnl
            }))
        }
    }));

    // Spawn task for Bitfinex WebSocket
    let md_clone = md.clone();
    let trader_clone = trader.clone();
    tokio::spawn(async move {
        let url = Url::parse("wss://api-pub.bitfinex.com/ws/2").unwrap();
        let (ws_stream, _) = connect_async(url).await.expect("Failed to connect");
        let (mut _write, mut read) = ws_stream.split();

        // Subscribe to BTC/USD trades
        let subscribe_msg = r#"{
            "event": "subscribe",
            "channel": "trades",
            "symbol": "tBTCUSD"
        }"#;
        _write.send(tokio_tungstenite::tungstenite::Message::Text(subscribe_msg.into())).await.unwrap();

        let period = 16;

        while let Some(message) = read.next().await {
            if let Ok(msg) = message {
                if msg.is_text() {
                    let text = msg.to_text().unwrap();

                    // Skip event messages
                    if text.contains("\"event\"") { continue; }

                    // Bitfinex trade message: [CHANNEL_ID, "tu", [PRICE, COUNT, AMOUNT]]
                    if let Ok(v) = serde_json::from_str::<serde_json::Value>(text) {
                        if let Some(arr) = v.as_array() {
                            if arr.len() > 1 {
                                if let Some(inner) = arr[1].as_array() {
                                    if inner.len() >= 3 {
                                        if let Some(price) = inner[0].as_f64() {
                                            let price = price as f32;

                                            let mut md = md_clone.lock().unwrap();
                                            let mut trader = trader_clone.lock().unwrap();

                                            // Update price buffer
                                            md.prices.push(price);
                                            if md.prices.len() > 1024 {
                                                md.prices.remove(0);
                                            }

                                            // Compute HMA + slope
                                            let (hma, slope) = ffi::compute_hma_slope(&md.prices, period);
                                            md.hma = hma;
                                            md.slope = slope;

                                            // Update trader
                                            let sig = *md.slope.last().unwrap_or(&0.0);
                                            trader.update(sig, price);
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    });

    let addr = SocketAddr::from(([0,0,0,0], 8000));
    println!("Listening on {}", addr);
    axum::Server::bind(&addr).serve(app.into_make_service()).await.unwrap();
}
