#!/usr/bin/env bash
# Free, instant public HTTPS tunnel via Cloudflare
# No password, no registration, no interstitial reminder screen!
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$ROOT/.venv/bin/cloudflared"

if [ ! -f "$BIN" ]; then
    echo "Downloading cloudflared binary..."
    curl -L -s https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o "$BIN"
    chmod +x "$BIN"
fi

echo "=========================================================="
echo "  NASA Earth Pulse — Public Tunnel (Cloudflare)"
echo "  Connecting local server http://localhost:8000 to public HTTPS..."
echo "=========================================================="
exec "$BIN" tunnel --url http://localhost:8000
