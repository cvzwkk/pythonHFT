#!/usr/bin/env bash
set -e
sudo apt update
sudo apt install -y pkg-config libssl-dev
export OPENSSL_DIR=/usr
export OPENSSL_LIB_DIR=/usr/lib/x86_64-linux-gnu
export OPENSSL_INCLUDE_DIR=/usr/include

APP_NAME="hull_bot"
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN_PATH="$APP_DIR/target/release/$APP_NAME"

echo "🚀 Hull Bot build & run"
echo "📁 Project root: $APP_DIR"
echo "📦 Binary path: $BIN_PATH"

cd "$APP_DIR"

# Load Rust env if not already loaded (important on VPS)
if [ -f "$HOME/.cargo/env" ]; then
  source "$HOME/.cargo/env"
fi

echo "🏗️  Building release binary..."
cargo build --release

if [ ! -x "$BIN_PATH" ]; then
  echo "❌ Binary not found or not executable: $BIN_PATH"
  exit 1
fi

echo "🛑 Stopping existing hull_bot (if any)..."
pkill -f "$BIN_PATH" || true

echo "▶️  Starting hull_bot..."
nohup "$BIN_PATH" > hull_bot.log 2>&1 &

sleep 1

echo "✅ hull_bot running"
echo "📄 Logs: tail -f hull_bot.log"
echo "🌐 API: http://localhost:8000/live"
