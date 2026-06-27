#!/usr/bin/env python3
"""Download Clash subscription, generate config.yaml, start mihomo.

Usage:
    python3 deploy_clash.py          # Download + generate + start
    python3 deploy_clash.py --gen    # Only generate config.yaml
    python3 deploy_clash.py --start  # Only start from existing config
"""

import base64
import os
import re
import subprocess
import sys
import time
import urllib.parse
import yaml

# ── Config ──────────────────────────────────────────────────
SUB_URL = "https://app.mitce.net/?sid=376564&token=srvfxbhh"
CONFIG_DIR = "/root/.config/clash"
CONFIG_PATH = f"{CONFIG_DIR}/config.yaml"
MIHOMO_BIN = "/usr/bin/verge-mihomo-alpha"
MIXED_PORT = 7892
EXT_CTRL = "127.0.0.1:9090"

os.makedirs(CONFIG_DIR, exist_ok=True)


def fetch_proxies() -> list[str]:
    """Download and decode base64 subscription. Returns list of proxy URIs."""
    r = subprocess.run(
        ["curl", "-s", "--connect-timeout", "10", "--max-time", "20", SUB_URL],
        capture_output=True, text=True, timeout=25,
    )
    if r.returncode != 0 or not r.stdout.strip():
        print("ERROR: Failed to fetch subscription")
        sys.exit(1)

    raw = r.stdout.strip()
    try:
        decoded = base64.b64decode(raw).decode()
    except Exception:
        decoded = raw  # might already be plain text

    uris = [l.strip() for l in decoded.splitlines() if l.strip()]
    print(f"Fetched {len(uris)} proxy URIs")
    return uris


def parse_vless(uri: str, name: str) -> dict:
    """Parse vless:// URI into Clash proxy dict."""
    parsed = urllib.parse.urlparse(uri)
    uuid_host = parsed.netloc.split("@")
    uuid = uuid_host[0] if len(uuid_host) > 1 else parsed.username or ""
    host_port = uuid_host[-1] if len(uuid_host) > 1 else parsed.netloc
    host = parsed.hostname or host_port.split(":")[0] if ":" in host_port else host_port
    port = parsed.port or 443

    params = dict(urllib.parse.parse_qsl(parsed.query))

    proxy = {
        "name": name,
        "type": "vless",
        "server": host,
        "port": port,
        "uuid": uuid,
        "flow": params.get("flow", ""),
        "tls": True,
        "udp": True,
        "skip-cert-verify": True,
        "servername": params.get("sni", ""),
    }

    if params.get("type") == "grpc":
        proxy["network"] = "grpc"
        proxy["grpc-opts"] = {"grpc-service-name": params.get("serviceName", "")}
    elif params.get("type") == "ws":
        proxy["network"] = "ws"
        proxy["ws-opts"] = {"path": params.get("path", "/")}

    if params.get("security") == "reality":
        proxy["reality-opts"] = {
            "public-key": params.get("pbk", ""),
            "short-id": params.get("sid", ""),
        }
        proxy["client-fingerprint"] = params.get("fp", "chrome")

    # Remove empty fields
    return {k: v for k, v in proxy.items() if v != "" and v is not None}


def parse_hysteria2(uri: str, name: str) -> dict:
    """Parse hysteria2:// URI into Clash proxy dict."""
    parsed = urllib.parse.urlparse(uri)
    pwd_host = parsed.netloc.split("@")
    password = pwd_host[0] if len(pwd_host) > 1 else parsed.username or ""
    host = parsed.hostname or ""
    port = parsed.port or 443

    params = dict(urllib.parse.parse_qsl(parsed.query))

    proxy = {
        "name": name,
        "type": "hysteria2",
        "server": host,
        "port": port,
        "password": password,
        "skip-cert-verify": True,
        "sni": params.get("sni", host),
    }

    if params.get("obfs") == "salamander":
        proxy["obfs"] = "salamander"
        proxy["obfs-password"] = params.get("obfs-password", "")

    return {k: v for k, v in proxy.items() if v != "" and v is not None}


def parse_tuic(uri: str, name: str) -> dict:
    """Parse tuic:// URI into Clash proxy dict."""
    # tuic://uuid:password@host:port?params
    match = re.match(r"tuic://([^:]+):([^@]+)@([^:]+):(\d+)\?(.*)", uri)
    if not match:
        print(f"  WARN: Cannot parse TUIC: {uri[:60]}...")
        return {"name": name, "type": "tuic", "server": "localhost", "port": 0}

    uuid, password, host, port_str, qs = match.groups()
    params = dict(urllib.parse.parse_qsl(qs))

    proxy = {
        "name": name,
        "type": "tuic",
        "server": host,
        "port": int(port_str),
        "uuid": uuid,
        "password": password,
        "skip-cert-verify": True,
        "sni": params.get("sni", host),
        "alpn": [params.get("alpn", "h3")],
        "congestion-controller": params.get("congestion_control", "bbr"),
        "udp-relay-mode": params.get("udp_relay_mode", "native"),
    }

    insecure = params.get("insecure", "0")
    if insecure == "1":
        proxy["skip-cert-verify"] = True

    return {k: v for k, v in proxy.items() if v != "" and v is not None}


def parse_proxy(uri: str) -> dict:
    """Parse a proxy URI string into a Clash proxy config dict."""
    # Extract name from fragment
    name = "Proxy"
    if "#" in uri:
        name = uri.split("#")[-1].strip()

    if uri.startswith("vless://"):
        return parse_vless(uri, name)
    elif uri.startswith("hysteria2://"):
        return parse_hysteria2(uri, name)
    elif uri.startswith("tuic://"):
        return parse_tuic(uri, name)
    elif uri.startswith("vmess://"):
        try:
            b64 = uri[len("vmess://"):]
            decoded = base64.b64decode(b64).decode()
            info = json.loads(decoded)
            return {
                "name": info.get("ps", name),
                "type": "vmess",
                "server": info.get("add", ""),
                "port": int(info.get("port", 0)),
                "uuid": info.get("id", ""),
                "alterId": int(info.get("aid", 0)),
                "cipher": info.get("scy", "auto") or "auto",
                "tls": info.get("tls", "") == "tls",
                "skip-cert-verify": True,
                "network": info.get("net", "tcp"),
            }
        except Exception:
            pass

    print(f"  WARN: Unknown proxy type: {uri[:60]}...")
    return {"name": name, "type": "ss", "server": "localhost", "port": 0, "password": ""}


def generate_config(uris: list[str]) -> dict:
    """Generate full Clash config from proxy URIs."""
    proxies = []
    for uri in uris:
        p = parse_proxy(uri)
        if p.get("port") and p.get("port") != 0:
            proxies.append(p)

    proxy_names = [p["name"] for p in proxies]

    config = {
        "port": 7890,
        "socks-port": 7891,
        "mixed-port": MIXED_PORT,
        "allow-lan": False,
        "mode": "Rule",
        "log-level": "warning",
        "external-controller": EXT_CTRL,
        "ipv6": False,

        "proxies": proxies,

        "proxy-groups": [
            {
                "name": "Proxy",
                "type": "select",
                "proxies": ["Auto"] + proxy_names,
            },
            {
                "name": "Auto",
                "type": "url-test",
                "proxies": proxy_names[:20] if len(proxy_names) > 20 else proxy_names,
                "url": "http://www.gstatic.com/generate_204",
                "interval": 300,
                "tolerance": 50,
            },
        ],

        "rules": [
            "MATCH,Proxy",
        ],
    }

    return config


def write_config(config: dict):
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    print(f"Config written: {CONFIG_PATH}")
    print(f"  Proxies: {len(config['proxies'])}")
    print(f"  Mixed port: {MIXED_PORT}")
    print(f"  External controller: {EXT_CTRL}")


def start_mihomo():
    """Kill existing mihomo and start a new one."""
    # Kill any existing
    subprocess.run(["pkill", "-f", MIHOMO_BIN], capture_output=True)
    time.sleep(1)

    proc = subprocess.Popen(
        [MIHOMO_BIN, "-d", CONFIG_DIR, "-f", CONFIG_PATH],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"mihomo started (PID={proc.pid})")

    # Wait and verify
    time.sleep(2)
    r = subprocess.run(
        ["curl", "-s", "--connect-timeout", "3", f"http://{EXT_CTRL}/version"],
        capture_output=True, text=True, timeout=5,
    )
    if r.returncode == 0 and r.stdout.strip():
        print(f"  Controller OK: {r.stdout.strip()}")
        return True
    else:
        print("  WARN: Controller not responding")
        return False


def check_proxy():
    """Test if the proxy is working."""
    time.sleep(1)
    r = subprocess.run(
        ["curl", "-s", "--connect-timeout", "5",
         "--proxy", f"http://127.0.0.1:{MIXED_PORT}",
         "-o", "/dev/null", "-w", "%{http_code}",
         "https://www.google.com"],
        capture_output=True, text=True, timeout=10,
    )
    if r.stdout.strip() == "200":
        print("  Proxy test: ✅ Google reachable")
        return True
    else:
        print(f"  Proxy test: ❌ HTTP {r.stdout.strip()}")
        return False


def set_env():
    """Print proxy environment variables for export."""
    print(f"\nSet these env vars to use the proxy:")
    print(f"  export HTTP_PROXY=http://127.0.0.1:{MIXED_PORT}")
    print(f"  export HTTPS_PROXY=http://127.0.0.1:{MIXED_PORT}")
    print(f"  export ALL_PROXY=socks5://127.0.0.1:{MIXED_PORT + 1}")
    print(f"  export no_proxy=localhost,127.0.0.1")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode in ("all", "--gen", "--gen-only"):
        print("=== Fetching subscription ===")
        uris = fetch_proxies()
        print("=== Generating config ===")
        config = generate_config(uris)
        write_config(config)

    if mode in ("all", "--start", "--start-only"):
        if not os.path.exists(CONFIG_PATH):
            print("ERROR: No config.yaml found. Run --gen first.")
            sys.exit(1)
        print("=== Starting mihomo ===")
        ok = start_mihomo()
        if ok:
            check_proxy()
        set_env()

    if mode == "--test":
        check_proxy()
