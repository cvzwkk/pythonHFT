use std::fs;
use std::path::Path;

use crate::trader::PaperTrader;

/* =========================
   FILE CONFIG
========================= */

const STATE_FILE: &str = "trader_state.json";

/* =========================
   LOAD STATE
========================= */

pub fn load_state(trader: &parking_lot::Mutex<PaperTrader>) {
    if !Path::new(STATE_FILE).exists() {
        return;
    }

    if let Ok(data) = fs::read_to_string(STATE_FILE) {
        if let Ok(restored) = serde_json::from_str::<PaperTrader>(&data) {
            *trader.lock() = restored;
        }
    }
}

/* =========================
   SAVE STATE
========================= */

pub fn save_state(trader: &parking_lot::Mutex<PaperTrader>) {
    if let Ok(json) = serde_json::to_string_pretty(&*trader.lock()) {
        let _ = fs::write(STATE_FILE, json);
    }
}
