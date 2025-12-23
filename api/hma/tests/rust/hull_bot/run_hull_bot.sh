#!/usr/bin/env bash
set -e
sudo apt update
sudo apt install -y pkg-config libssl-dev
export OPENSSL_DIR=/usr
export OPENSSL_LIB_DIR=/usr/lib/x86_64-linux-gnu
export OPENSSL_INCLUDE_DIR=/usr/include

# Add current directory to library path
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:.

# Pin process to CPU core 1 for deterministic latency
taskset -c 1 ./target/release/hull_bot
