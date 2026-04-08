#!/usr/bin/env bash
# 🌐 Zenith Tunnel — Expone el bot local a TradingView via Cloudflare
# Uso: ./scripts/tunnel.sh
# Requiere: brew install cloudflare/cloudflare/cloudflared

if ! command -v cloudflared &> /dev/null; then
    echo "⚠️  cloudflared no encontrado. Instalando..."
    brew install cloudflare/cloudflare/cloudflared
fi

echo "🌐 Iniciando túnel Cloudflare → http://localhost:8080"
echo "   Copia la URL https://xxx.trycloudflare.com que aparezca abajo"
echo "   y configúrala en TradingView como: https://xxx.trycloudflare.com/webhook/tradingview"
echo ""
cloudflared tunnel --url http://localhost:8080
