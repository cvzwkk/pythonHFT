#[link(name = "hma_avx")]
extern "C" {
    pub fn swma_avx(data: *const f32, out: *mut f32, n: i32, period: i32);
    pub fn hma_avx(data: *const f32, out: *mut f32, n: i32, period: i32);
    pub fn slope_avx(hma: *const f32, out: *mut f32, n: i32);
}

pub fn compute_hma_slope(prices: &Vec<f32>, period: i32) -> (Vec<f32>, Vec<f32>) {
    let n = prices.len() as i32;
    let mut hma = vec![0f32; prices.len()];
    let mut slope = vec![0f32; prices.len()];

    unsafe {
        hma_avx(prices.as_ptr(), hma.as_mut_ptr(), n, period);
        slope_avx(hma.as_ptr(), slope.as_mut_ptr(), n);
    }

    (hma, slope)
}
