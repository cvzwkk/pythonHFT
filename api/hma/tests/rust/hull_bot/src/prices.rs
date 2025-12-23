use crate::{AppState};
use crate::models;
use crate::trader::Side;

use reqwest::Client;
use tokio::time::{sleep, Duration};

/* =========================
   PRICE LOOP
========================= */

pub async fn price_loop(state: AppState) {
    let client = Client::new();

    loop {
        if let Some(price) = fetch_price(&client).await {
            // -------------------------
            // Update market state
            // -------------------------
            {
                let mut market = state.market.lock();
                market.push_price(price);
            }

            // -------------------------
            // Run prediction
            // -------------------------
            let signal = {
                let market = state.market.lock();
                models::predict(&market.prices)
            };

            // -------------------------
            // Trading logic
            // -------------------------
            {
                let mut trader = state.trader.lock();

                trader.maybe_close(price);
                trader.maybe_add(price);
                trader.maybe_open(signal, price);
            }
        }

        sleep(Duration::from_secs(1)).await;
    }
}

/* =========================
   PRICE FETCHER
========================= */

async fn fetch_price(client: &Client) -> Option<f64> {
    // Bitfinex public ticker (same as Python bot)
    let url = "https://api-pub.bitfinex.com/v2/ticker/tBTCUSD";

    let resp = client.get(url).send().await.ok()?;
    let data = resp.json::<Vec<f64>>().await.ok()?;

    // index 6 = last price
    data.get(6).copied()
}
