use std::collections::VecDeque;

/* =========================
   UTILS
========================= */

#[inline(always)]
fn wma(slice: &[f64]) -> f64 {
    let n = slice.len();
    let mut num = 0.0;
    let mut den = 0.0;

    // linear weights: 1..n
    for (i, v) in slice.iter().enumerate() {
        let w = (i + 1) as f64;
        num += v * w;
        den += w;
    }
    num / den
}

/* =========================
   HULL MOVING AVERAGE
========================= */

#[inline]
pub fn hma(prices: &VecDeque<f64>, period: usize) -> Option<f64> {
    let len = prices.len();
    if len < period + 4 {
        return None;
    }

    let half = period / 2;
    let sqrt_p = (period as f64).sqrt() as usize;

    let p = prices.make_contiguous();

    let wma_half = wma(&p[len - half..len]);
    let wma_full = wma(&p[len - period..len]);

    // raw hull
    let hull_raw = 2.0 * wma_half - wma_full;

    // smoothing (final HMA)
    let mut temp = Vec::with_capacity(sqrt_p);
    for i in (len - sqrt_p)..len {
        temp.push(p[i]);
    }

    Some(wma(&temp))
}

/* =========================
   SLOPE (linear regression)
========================= */

#[inline]
pub fn slope(prices: &VecDeque<f64>, lookback: usize) -> f64 {
    let len = prices.len();
    if len < lookback {
        return 0.0;
    }

    let p = prices.make_contiguous();
    let start = len - lookback;

    let mut sum_x = 0.0;
    let mut sum_y = 0.0;
    let mut sum_xy = 0.0;
    let mut sum_x2 = 0.0;

    for i in 0..lookback {
        let x = i as f64;
        let y = p[start + i];
        sum_x += x;
        sum_y += y;
        sum_xy += x * y;
        sum_x2 += x * x;
    }

    let n = lookback as f64;
    let denom = n * sum_x2 - sum_x * sum_x;
    if denom == 0.0 {
        return 0.0;
    }

    (n * sum_xy - sum_x * sum_y) / denom
}

/* =========================
   MOMENTUM
========================= */

#[inline]
pub fn momentum(prices: &VecDeque<f64>, lookback: usize) -> f64 {
    let len = prices.len();
    if len <= lookback {
        return 0.0;
    }

    let p = prices.make_contiguous();
    let now = p[len - 1];
    let prev = p[len - 1 - lookback];

    (now - prev) / prev
}

/* =========================
   FINAL PREDICTION
========================= */

#[inline]
pub fn predict(prices: &VecDeque<f64>) -> f64 {
    let h = match hma(prices, 55) {
        Some(v) => v,
        None => return 0.0,
    };

    let last = *prices.back().unwrap();

    let slope_val = slope(prices, 20);
    let mom_val = momentum(prices, 14);

    // normalized deltas
    let hma_delta = (last - h) / last;

    // weights match Python logic
    (hma_delta * 0.6) + (slope_val * 0.3) + (mom_val * 0.1)
}
