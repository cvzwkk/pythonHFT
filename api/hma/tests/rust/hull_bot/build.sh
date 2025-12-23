#!/usr/bin/env bash
set -e

echo "🚀 Building C AVX2 library"
gcc -O3 -march=native -mavx2 -mfma -ffast-math -funroll-loops \
    -fPIC -shared c_src/libhma_avx.c -o libhma_avx.so

echo "🚀 Building Rust binary"
cargo build --release
