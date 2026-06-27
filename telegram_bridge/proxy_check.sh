#!/bin/bash
# Check and restart Clash proxy if needed
PROXY_URL="http://127.0.0.1:7892"
CTRL_URL="http://127.0.0.1:9090/version"

# Check if proxy is responding
if timeout 3 curl -s "$CTRL_URL" > /dev/null 2>&1; then
    # Check if it can reach external
    if timeout 5 curl -s --proxy "$PROXY_URL" -o /dev/null -w "%{http_code}" https://www.google.com 2>/dev/null | grep -q 200; then
        echo "Proxy OK"
        exit 0
    fi
fi

echo "Proxy down, restarting..."
pkill -9 verge-mihomo 2>/dev/null
sleep 1
nohup /usr/bin/verge-mihomo-alpha -d /root/.config/clash -f /root/.config/clash/config.yaml > /dev/null 2>&1 &
echo "Restarted mihomo"
