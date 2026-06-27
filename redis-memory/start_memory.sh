#!/bin/bash
# Start Redis Stack (if not running) and initialize memory layer
set -e

DATA_DIR="/data/redis-stack"
mkdir -p "$DATA_DIR"

if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -q redis-stack; then
    echo "[redis-memory] Starting Redis Stack with AOF persistence..."
    docker rm -f redis-stack 2>/dev/null
    docker run -d \
      --name redis-stack \
      -p 6379:6379 \
      -v "$DATA_DIR:/var/lib/redis-stack" \
      --restart=unless-stopped \
      redis/redis-stack-server:latest \
      redis-stack-server --appendonly yes
    sleep 2
fi

echo "[redis-memory] Initializing indices and caches..."
cd /root/.config/opencode/redis-memory && TRANSFORMERS_OFFLINE=1 python3 init_memory.py
echo "[redis-memory] Ready"
