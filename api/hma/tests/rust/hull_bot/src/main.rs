mod ffi;
mod market;
mod trader;

use axum::{routing::get, Router, Json};
use serde_json::json;
use std::{sync::{Arc, Mutex}, net::SocketAddr};
use core_affinity;

use market::MarketData;
use trader::Trader;

#[tokio::main]
async fn main() {
    // Pin CPU core to reduce jitter
    if let Some(core) = core_affinity::get_core_ids().and_then(|c| c.get(0).cloned()) {
        core_affinity::set_for_current(core);
    }

    let md = Arc::new(Mutex::new(MarketData::new(1024)));
    let trader = Arc::new(Mutex::new(Trader::new()));

    // HTTP endpoint for monitoring
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

    // Simulated market feed
    let md_clone = md.clone();
    let trader_clone = trader.clone();
    tokio::spawn(async move {
        let period = 16;
        loop {
            {
                let mut md = md_clone.lock().unwrap();
                let mut trader = trader_clone.lock().unwrap();

                // Generate fake new price
                let new_price = md.prices.last().unwrap_or(&100.0) + 0.5;
                md.prices.push(new_price);
                if md.prices.len() > 1024 { md.prices.remove(0); }

                // Compute HMA + slope
                let (hma, slope) = ffi::compute_hma_slope(&md.prices, period);
                md.hma = hma;
                md.slope = slope;

                // Update trader using slope signal
                let sig = *md.slope.last().unwrap_or(&0.0);
                trader.update(sig, new_price);
            }
            tokio::time::sleep(std::time::Duration::from_millis(1)).await;
        }
    });

    let addr = SocketAddr::from(([0,0,0,0], 8000));
    println!("Listening on {}", addr);
    axum::Server::bind(&addr).serve(app.into_make_service()).await.unwrap();
}
