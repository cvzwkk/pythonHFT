#include <immintrin.h>
#include <stdlib.h>
#include <math.h>

/* SWMA: Simple Weighted Moving Average */
void swma_avx(const float* data, float* out, int n, int period) {
    for (int i = 0; i <= n-8; i+=8) {
        __m256 sum = _mm256_setzero_ps();
        for (int j=0;j<period;j++){
            __m256 val = _mm256_loadu_ps(&data[i+j]);
            __m256 weight = _mm256_set1_ps((j+1.0f)/period);
            sum = _mm256_add_ps(sum, _mm256_mul_ps(val, weight));
        }
        _mm256_storeu_ps(&out[i], sum);
    }
}

/* HMA: Hull Moving Average */
void hma_avx(const float* data, float* out, int n, int period) {
    int half = period/2;
    float* wma_full = (float*)aligned_alloc(32, n*sizeof(float));
    float* wma_half = (float*)aligned_alloc(32, n*sizeof(float));
    float* diff = (float*)aligned_alloc(32, n*sizeof(float));

    swma_avx(data, wma_full, n, period);
    swma_avx(data, wma_half, n, half);

    for(int i=0;i<=n-8;i+=8){
        __m256 w_full = _mm256_loadu_ps(&wma_full[i]);
        __m256 w_half = _mm256_loadu_ps(&wma_half[i]);
        __m256 res = _mm256_sub_ps(_mm256_mul_ps(_mm256_set1_ps(2.0f), w_half), w_full);
        _mm256_storeu_ps(&diff[i], res);
    }

    swma_avx(diff, out, n, (int)sqrtf(period));

    free(wma_full);
    free(wma_half);
    free(diff);
}

/* Slope */
void slope_avx(const float* hma, float* out, int n) {
    for(int i=1;i<=n-8;i+=8){
        __m256 curr = _mm256_loadu_ps(&hma[i]);
        __m256 prev = _mm256_loadu_ps(&hma[i-1]);
        __m256 diff = _mm256_sub_ps(curr, prev);
        _mm256_storeu_ps(&out[i], diff);
    }
}
