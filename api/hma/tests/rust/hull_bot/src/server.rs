use axum::{
    routing::get,
    Router,
    Json,
};
use serde_json::json;
use std::net::SocketAddr;

use crate::AppState;

/* =========================
   SERVER
========================= */

pub async fn run_server(state: AppState) {
    let app = Router::new()
        .route("/live", get(move || live_handler(state.clone())));

    let addr: SocketAddr = "0.0.0.0:8000".parse().unwrap();

    axum::Server::bind(&addr)
        .serve(app.into_make_service())
        .await
        .unwrap();
}

/* =========================
   HANDLER
========================= */

async fn live_handler(state: AppState) -> Json<serde_json::Value> {
    let trader = state.trader.lock();
    let market = state.market.lock();

    Json(json!({
        "price": market.last_price,
        "balance": trader.balance,
        "pnl": trader.pnl,
        "position": trader.position,
        "trades": trader.trade_count
    }))
}
