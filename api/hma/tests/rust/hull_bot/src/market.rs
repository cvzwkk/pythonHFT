pub struct MarketData {
    pub prices: Vec<f32>,
    pub hma: Vec<f32>,
    pub slope: Vec<f32>,
}

impl MarketData {
    pub fn new(size: usize) -> Self {
        Self {
            prices: vec![0.0; size],
            hma: vec![0.0; size],
            slope: vec![0.0; size],
        }
    }
}
