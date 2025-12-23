use serde::{Serialize, Deserialize};

/* =========================
   POSITION
========================= */

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Position {
    pub side: Side,
    pub avg_price: f64,
    pub size: f64,
    pub adds: u32,
    pub tp_price: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum Side {
    Buy,
    Sell,
}

/* =========================
   PAPER TRADER
========================= */

#[derive(Debug, Serialize, Deserialize)]
pub struct PaperTrader {
    pub balance: f64,
    pub pnl: f64,
    pub position: Option<Position>,
    pub trade_count: u64,
}

impl PaperTrader {
    pub fn new(balance: f64) -> Self {
        Self {
            balance,
            pnl: 0.0,
            position: None,
            trade_count: 0,
        }
    }

    /* =========================
       ENTRY LOGIC
    ========================= */

    #[inline]
    pub fn maybe_open(&mut self, signal: f64, price: f64) {
        if self.position.is_some() {
            return;
        }

        // threshold matches Python logic
        if signal.abs() < 0.0003 {
            return;
        }

        let side = if signal > 0.0 {
            Side::Buy
        } else {
            Side::Sell
        };

        let risk_capital = self.balance * 0.01;
        let size = risk_capital / price;

        let tp_price = match side {
            Side::Buy => price * 1.0025,
            Side::Sell => price * 0.9975,
        };

        self.position = Some(Position {
            side,
            avg_price: price,
            size,
            adds: 0,
            tp_price,
        });

        self.trade_count += 1;
    }

    /* =========================
       DCA / SCALE IN
    ========================= */

    #[inline]
    pub fn maybe_add(&mut self, price: f64) {
        let pos = match self.position.as_mut() {
            Some(p) => p,
            None => return,
        };

        if pos.adds >= 3 {
            return;
        }

        let unfavorable = match pos.side {
            Side::Buy => price < pos.avg_price * 0.999,
            Side::Sell => price > pos.avg_price * 1.001,
        };

        if !unfavorable {
            return;
        }

        let add_size = pos.size * 0.5;
        let new_notional = pos.avg_price * pos.size + price * add_size;
        let new_size = pos.size + add_size;

        pos.avg_price = new_notional / new_size;
        pos.size = new_size;
        pos.adds += 1;

        // move TP
        pos.tp_price = match pos.side {
            Side::Buy => pos.avg_price * 1.0025,
            Side::Sell => pos.avg_price * 0.9975,
        };
    }

    /* =========================
       EXIT LOGIC (TP)
    ========================= */

    #[inline]
    pub fn maybe_close(&mut self, price: f64) {
        let pos = match self.position.clone() {
            Some(p) => p,
            None => return,
        };

        let hit_tp = match pos.side {
            Side::Buy => price >= pos.tp_price,
            Side::Sell => price <= pos.tp_price,
        };

        if !hit_tp {
            return;
        }

        let pnl = match pos.side {
            Side::Buy => (price - pos.avg_price) * pos.size,
            Side::Sell => (pos.avg_price - price) * pos.size,
        };

        self.balance += pnl;
        self.pnl += pnl;
        self.position = None;
    }
}
