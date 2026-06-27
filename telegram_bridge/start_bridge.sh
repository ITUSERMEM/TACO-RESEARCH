#!/bin/bash
# Start Telegram Bot bridge for opencode
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export HTTP_PROXY=http://127.0.0.1:7892
export HTTPS_PROXY=http://127.0.0.1:7892
export NO_PROXY=localhost,127.0.0.1

# Ensure tmux server is running and set history
tmux start-server 2>/dev/null || true
tmux set -g history-limit 5000 2>/dev/null || true

# Kill stale session
tmux kill-session -t opencode 2>/dev/null || true

echo "[tg-bridge] Creating tmux session 'opencode'..."
tmux new-session -d -s opencode -x 120 -y 120 'opencode'
sleep 2

echo "[tg-bridge] Starting Telegram bridge..."
cd "$SCRIPT_DIR"
exec python3 telegram_bridge.py
