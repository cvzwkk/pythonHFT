#![allow(dead_code)]

use std::collections::VecDeque;
use std::sync::Arc;
use parking_lot::Mutex;

use tokio::time::{sleep, Duration};

use serde::{Serialize, Deserialize};

mod models;
mod trader;
mod prices;
mod server;
mod state;

/* =========================
   GLOBAL CONFIG
========================= */

const SYMBOL: &str = "BTCUSD";
const PRICE_WINDOW: usize = 256;
const HMA_PERIOD: usize = 55;

const BASE_BALANCE: f64 = 1000.0;
const RISK_PER_TRADE: f64 = 0.01;
const TAKE_PROFIT_PCT: f64 = 0.0025;

/* =========================
   SHARED MARKET STATE
========================= */

#[derive(Clone)]
pub struct MarketState {
    pub prices: VecDeque<f64>,
    pub last_price: f64,
}

impl MarketState {
    pub fn new() -> Self {
        Self {
            prices: VecDeque::with_capacity(PRICE_WINDOW),
            last_price: 0.0,
        }
    }

    #[inline]
    pub fn push_price(&mut self, price: f64) {
        if self.prices.len() >= PRICE_WINDOW {
            self.prices.pop_front();
        }
        self.prices.push_back(price);
        self.last_price = price;
    }
}

/* =========================
   APP STATE
========================= */

#[derive(Clone)]
pub struct AppState {
    pub market: Arc<Mutex<MarketState>>,
    pub trader: Arc<Mutex<trader::PaperTrader>>,
}

/* =========================
   MAIN ENTRYPOINT
========================= */

#[tokio::main]
async fn main() {
    env_logger::init();

    let market = Arc::new(Mutex::new(MarketState::new()));
    let trader = Arc::new(Mutex::new(trader::PaperTrader::new(BASE_BALANCE)));

    // restore state if exists
    state::load_state(&trader);

    let app_state = AppState {
        market: market.clone(),
        trader: trader.clone(),
    };

    // price feed loop
    {
        let state = app_state.clone();
        tokio::spawn(async move {
            prices::price_loop(state).await;
        });
    }

    // http server
    server::run_server(app_state).await;
}
