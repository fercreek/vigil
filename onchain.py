"""
onchain.py — Spec 010: Whale Netflows Tracker

Fuente: Etherscan (ETH) + BscScan (BSC) free APIs.
Tracking de transferencias grandes (>$1M) hacia/desde wallets de exchanges conocidos.

Lógica de señal:
- Net inflow a exchanges (positive) = BEARISH (whales depositan para vender)
- Net outflow desde exchanges (negative) = BULLISH (whales retiran a cold storage)

Diseño cache-first con degradación graceful — sin API key funciona en modo limitado.
NO auto-fetch: solo cuando get_whale_netflow() es llamada explícitamente.

Funciones principales:
  - get_whale_netflow(token, chain, lookback_hours, min_value_usd) → dict con net_flow + signal
  - get_whale_html()                                                → HTML para Telegram /whales
"""

import os
import time
from typing import Optional

import requests

from logger_core import logger
from config import (
    WHALE_NETFLOW_BEARISH_USD,
    WHALE_NETFLOW_BULLISH_USD,
    WHALE_NETFLOW_CACHE_TTL,
    WHALE_NETFLOW_TIMEOUT,
)

# ═══════════════════════════════════════════════════════════════════════════════
# 1. EXCHANGE WALLETS (hardcoded top 5 por chain)
# ═══════════════════════════════════════════════════════════════════════════════

# Direcciones públicas verificadas en Etherscan. Lowercase para comparación robusta.
EXCHANGE_WALLETS_ETH = {
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance 14",
    "0xf977814e90da44bfa03b6295a0616a897441acec": "Binance 15",
    "0x71660c4005ba85c37ccec55d0c4493e66fe775d3": "Coinbase",
    "0x2910543af39aba0cd09dbb2d50200b3e800a63d2": "Kraken",
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b": "OKX",
}

# BSC: Binance hot wallets más conocidas en BNB chain.
EXCHANGE_WALLETS_BSC = {
    "0x8894e0a0c962cb723c1976a4421c95949be2d4e3": "Binance BSC Hot 1",
    "0xf977814e90da44bfa03b6295a0616a897441acec": "Binance BSC Hot 2",
    "0x4982085c9e2f89f2ecb8131eca71afad896e89cb": "Binance BSC Hot 3",
    "0x161ba15a5f335c9f06bb5bbb0a9ce14076fbb645": "Bybit BSC",
    "0xa180fe01b906a1be37be6c534a3300785b20d947": "OKX BSC",
}

# API endpoints
ETHERSCAN_API = "https://api.etherscan.io/api"
BSCSCAN_API = "https://api.bscscan.com/api"

# ═══════════════════════════════════════════════════════════════════════════════
# 2. CACHE (module-level — patrón de market_intel.py)
# ═══════════════════════════════════════════════════════════════════════════════

_CACHE: dict = {
    # key: f"{token}:{chain}:{lookback_hours}" → {"data": {...}, "last_update": ts}
}


# ═══════════════════════════════════════════════════════════════════════════════
# 3. HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _get_api_config(chain: str) -> tuple:
    """Retorna (api_url, api_key, wallets_dict) para la chain especificada."""
    chain = chain.lower()
    if chain == "eth":
        api_key = os.getenv("ETHERSCAN_API_KEY", "")
        return ETHERSCAN_API, api_key, EXCHANGE_WALLETS_ETH
    elif chain in ("bsc", "bnb"):
        api_key = os.getenv("BSCSCAN_API_KEY", "")
        return BSCSCAN_API, api_key, EXCHANGE_WALLETS_BSC
    else:
        raise ValueError(f"Chain no soportada: {chain} (usa 'eth' o 'bsc')")


def _get_token_price_usd(token_symbol: str) -> Optional[float]:
    """
    Precio aproximado USD del token. Lazy import a indicators para evitar circularidad.
    Retorna None si no se puede obtener.
    """
    try:
        # Lazy import — el bot ya tiene Binance singleton para precios spot
        from exchange_singleton import binance_futures
        ticker = binance_futures.fetch_ticker(f"{token_symbol}/USDT:USDT")
        return float(ticker.get("last") or 0.0)
    except Exception as e:
        logger.warning(f"[WhaleNetflow] No se pudo obtener precio {token_symbol}: {e}")
        return None


def _fetch_wallet_transfers(
    api_url: str,
    api_key: str,
    wallet_address: str,
    start_block: int = 0,
    timeout: float = WHALE_NETFLOW_TIMEOUT,
) -> list:
    """
    Fetch txlist normal de Etherscan/BscScan para una wallet.

    Endpoint: ?module=account&action=txlist&address=...&startblock=...&sort=desc
    Free tier: 5 calls/sec sin API key, mejor con key.

    Retorna lista de tx dicts o lista vacía en error.
    """
    params = {
        "module": "account",
        "action": "txlist",
        "address": wallet_address,
        "startblock": start_block,
        "endblock": 99999999,
        "sort": "desc",
        "page": 1,
        "offset": 100,  # Top 100 más recientes
    }
    if api_key:
        params["apikey"] = api_key

    try:
        resp = requests.get(api_url, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "1" and isinstance(data.get("result"), list):
            return data["result"]
        # status="0" puede ser "No transactions found" — válido, no es error
        return []
    except requests.exceptions.Timeout:
        logger.warning(f"[WhaleNetflow] Timeout fetching {wallet_address[:10]}...")
        return []
    except Exception as e:
        logger.warning(f"[WhaleNetflow] Error fetching {wallet_address[:10]}...: {e}")
        return []


def _classify_signal(net_flow_usd: float) -> str:
    """Clasifica el net flow en BEARISH / BULLISH / NEUTRAL."""
    if net_flow_usd > WHALE_NETFLOW_BEARISH_USD:
        return "BEARISH"
    if net_flow_usd < WHALE_NETFLOW_BULLISH_USD:
        return "BULLISH"
    return "NEUTRAL"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def get_whale_netflow(
    token_symbol: str = "ETH",
    chain: str = "eth",
    lookback_hours: int = 24,
    min_value_usd: float = 1_000_000,
) -> dict:
    """
    Fetch whale movements to/from exchanges en las últimas N horas.

    Args:
        token_symbol: símbolo del token (ETH, BNB, etc.)
        chain: "eth" o "bsc"
        lookback_hours: ventana temporal (default 24h)
        min_value_usd: monto mínimo para considerar "whale" (default $1M)

    Returns:
        dict con:
            token, chain, lookback_hours,
            inflow_usd  — total flowing TO exchanges (bearish, whales depositan)
            outflow_usd — total flowing FROM exchanges (bullish, whales retiran)
            net_flow_usd = inflow - outflow (positive = bearish)
            signal: "BEARISH" | "BULLISH" | "NEUTRAL"
            tx_count, last_update_ts
        Empty dict {} en failure total.
    """
    # ── Cache check ─────────────────────────────────────────────────────────
    cache_key = f"{token_symbol}:{chain}:{lookback_hours}"
    now = time.time()
    cached = _CACHE.get(cache_key)
    if cached and (now - cached.get("last_update", 0)) < WHALE_NETFLOW_CACHE_TTL:
        return cached["data"]

    # ── API config ──────────────────────────────────────────────────────────
    try:
        api_url, api_key, wallets = _get_api_config(chain)
    except ValueError as e:
        logger.warning(f"[WhaleNetflow] {e}")
        return {}

    # ── Precio token (para convertir valor nativo → USD) ────────────────────
    price_usd = _get_token_price_usd(token_symbol)
    if not price_usd or price_usd <= 0:
        logger.warning(f"[WhaleNetflow] Precio inválido para {token_symbol}, abortando")
        return {}

    # ── Ventana temporal ────────────────────────────────────────────────────
    cutoff_ts = int(now - lookback_hours * 3600)

    inflow_usd = 0.0
    outflow_usd = 0.0
    tx_count = 0

    # ── Iterar wallets de exchange ──────────────────────────────────────────
    for wallet_addr in wallets.keys():
        txs = _fetch_wallet_transfers(api_url, api_key, wallet_addr)
        if not txs:
            continue

        for tx in txs:
            try:
                tx_ts = int(tx.get("timeStamp", 0))
                if tx_ts < cutoff_ts:
                    # txs ordenadas DESC — al primer tx fuera de ventana, break
                    break

                # Valor en wei → token native → USD
                value_wei = int(tx.get("value", "0"))
                if value_wei <= 0:
                    continue
                value_native = value_wei / 1e18  # ETH/BNB tienen 18 decimals
                value_usd = value_native * price_usd

                if value_usd < min_value_usd:
                    continue

                # Clasificar dirección
                tx_to = (tx.get("to") or "").lower()
                tx_from = (tx.get("from") or "").lower()
                wallet_lower = wallet_addr.lower()

                if tx_to == wallet_lower:
                    # Alguien ENVÍA al exchange = inflow (bearish)
                    inflow_usd += value_usd
                    tx_count += 1
                elif tx_from == wallet_lower:
                    # Exchange ENVÍA fuera = outflow (bullish, withdrawal a cold storage)
                    outflow_usd += value_usd
                    tx_count += 1

            except (ValueError, KeyError, TypeError) as e:
                logger.warning(f"[WhaleNetflow] tx parse error: {e}")
                continue

    net_flow_usd = inflow_usd - outflow_usd
    signal = _classify_signal(net_flow_usd)

    result = {
        "token": token_symbol,
        "chain": chain,
        "lookback_hours": lookback_hours,
        "inflow_usd": round(inflow_usd, 2),
        "outflow_usd": round(outflow_usd, 2),
        "net_flow_usd": round(net_flow_usd, 2),
        "signal": signal,
        "tx_count": tx_count,
        "last_update_ts": int(now),
    }

    _CACHE[cache_key] = {"data": result, "last_update": now}
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 5. TELEGRAM HTML GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

_SIGNAL_EMOJI = {
    "BEARISH": "🔴",
    "BULLISH": "🟢",
    "NEUTRAL": "⚪",
}


def get_whale_html(token_symbol: str = "ETH", chain: str = "eth", lookback_hours: int = 24) -> str:
    """HTML formateado de whale netflow para Telegram (/whales command)."""
    data = get_whale_netflow(token_symbol, chain, lookback_hours)

    lines = [f"🐋 <b>WHALE NETFLOW — {token_symbol} ({chain.upper()})</b>\n"]

    if not data:
        lines.append("<i>⚠️ Data no disponible (API timeout o sin precio).</i>")
        return "\n".join(lines)

    signal = data.get("signal", "NEUTRAL")
    emoji = _SIGNAL_EMOJI.get(signal, "⚪")
    inflow = data.get("inflow_usd", 0.0)
    outflow = data.get("outflow_usd", 0.0)
    net = data.get("net_flow_usd", 0.0)
    txs = data.get("tx_count", 0)

    lines.append(f"{emoji} <b>Signal:</b> {signal}")
    lines.append(f"⏱️ <b>Ventana:</b> últimas {lookback_hours}h | <b>Tx:</b> {txs}")
    lines.append(f"📥 <b>Inflow → exchanges:</b> ${inflow:,.0f}")
    lines.append(f"📤 <b>Outflow ← exchanges:</b> ${outflow:,.0f}")
    lines.append(f"📊 <b>Net flow:</b> ${net:+,.0f}")
    lines.append("")
    lines.append("<i>💡 Net > +$10M = whales depositan (BEARISH, sell pressure)</i>")
    lines.append("<i>💡 Net < -$10M = whales retiran (BULLISH, accumulation)</i>")

    return "\n".join(lines)
