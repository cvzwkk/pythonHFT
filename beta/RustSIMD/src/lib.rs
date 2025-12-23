use std::arch::x86_64::*;

/// Compute simple moving average (SMA) using AVX
#[no_mangle]
pub extern "C" fn sma_avx(data_ptr: *const f64, len: usize, out_ptr: *mut f64) {
    let data = unsafe { std::slice::from_raw_parts(data_ptr, len) };
    let out = unsafe { std::slice::from_raw_parts_mut(out_ptr, len) };

    let mut sum_vec = unsafe { _mm256_setzero_pd() };
    let mut i = 0;

    // Process chunks of 4 doubles
    while i + 4 <= len {
        unsafe {
            let chunk = _mm256_loadu_pd(data[i..].as_ptr());
            sum_vec = _mm256_add_pd(sum_vec, chunk);
            _mm256_storeu_pd(out[i..].as_mut_ptr(), chunk);
        }
        i += 4;
    }

    // Sum SIMD vector into scalar
    let mut scalar_sum = 0.0;
    let arr: [f64; 4] = unsafe { std::mem::transmute(sum_vec) };
    for v in arr { scalar_sum += v; }

    // Finish remaining elements
    while i < len {
        scalar_sum += data[i];
        out[i] = data[i];
        i += 1;
    }

    // Convert cumulative to SMA
    let mut cum = 0.0;
    for j in 0..len {
        cum += out[j];
        out[j] = cum / ((j + 1) as f64);
    }
}

/// Compute EMA with smoothing factor alpha (no SIMD needed, light)
#[no_mangle]
pub extern "C" fn ema_avx(data_ptr: *const f64, len: usize, alpha: f64, out_ptr: *mut f64) {
    let data = unsafe { std::slice::from_raw_parts(data_ptr, len) };
    let out = unsafe { std::slice::from_raw_parts_mut(out_ptr, len) };

    if len == 0 { return; }
    out[0] = data[0];
    for i in 1..len {
        out[i] = alpha * data[i] + (1.0 - alpha) * out[i-1];
    }
}

/// Compute momentum: difference between current value and value N periods ago
#[no_mangle]
pub extern "C" fn momentum(data_ptr: *const f64, len: usize, period: usize, out_ptr: *mut f64) {
    let data = unsafe { std::slice::from_raw_parts(data_ptr, len) };
    let out = unsafe { std::slice::from_raw_parts_mut(out_ptr, len) };

    for i in 0..len {
        if i < period {
            out[i] = 0.0;
        } else {
            out[i] = data[i] - data[i - period];
        }
    }
}
