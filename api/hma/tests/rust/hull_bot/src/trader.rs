pub struct Trader {
    pub balance: f64,
    pub position: f32,
    pub pnl: f64,
}

impl Trader {
    pub fn new() -> Self {
        Self {
            balance: 1000.0,
            position: 0.0,
            pnl: 0.0,
        }
    }

    pub fn update(&mut self, signal: f32, price: f32) {
        // Simple example trading logic based on HMA slope
        if signal > 0.0 {
            self.position += 1.0;
            self.balance -= price as f64;
        } else if signal < 0.0 && self.position > 0.0 {
            self.position -= 1.0;
            self.balance += price as f64;
            self.pnl += price as f64; // simplified PnL
        }
    }
}
