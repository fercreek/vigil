# Spec 010 — Whale Netflows On-Chain Tracker

> **Status:** CODE COMPLETE 2026-05-26
> **Owner:** Fernando
> **Severity:** P1 — NotebookLM 4 Prompt 3 ranking TOP 2 on-chain signal (post Funding Rates Spec 006)
> **Origen:** `docs/research/notebook-lm-4/RESULTS.md` Prompt 3

## Contexto

NotebookLM 4 Prompt 3 evaluó señales on-chain para crypto trading bots y rankeó **Whale Netflows como TOP 2** después de Funding Rates (ya implementado en Spec 006). El ratio señal/ruido es alto: cuando whales (movimientos >$1M) depositan masivamente a exchanges, históricamente precede a sell pressure en ventana 6-24h. Inversamente, withdrawals masivos a cold storage indican accumulation y suelen preceder rallies.

Etherscan + BscScan ofrecen APIs free tier suficientes para tracking horario sin costo. Hardcodeamos las wallets públicas verificadas de top 5 exchanges (Binance, Coinbase, Kraken, OKX, Bybit).

## Goals

1. `onchain.get_whale_netflow(token, chain, lookback_hours, min_value_usd)` retorna dict con `inflow_usd`, `outflow_usd`, `net_flow_usd`, `signal` (BEARISH/BULLISH/NEUTRAL).

2. Tracking de ETH (Etherscan) y BSC (BscScan) — chains mainstream con suficientes whale movements para señal estadística.

3. Cache 5min (Etherscan free tier 5 calls/sec) — degradación graceful: si API falla, retorna cache previo o dict vacío `{}`.

4. NO auto-fetch en main loop — solo on-demand cuando función es llamada (hook futuro: Cuadrilla Zenith voz Genesis o comando `/whales`).

5. Constantes thresholds en `config.py` para tuneo post-7d.

## Non-goals

- No tracking ERC-20 tokens custom (solo nativo ETH/BNB este spec)
- No tracking Solana / Tron / Cosmos (chains sin scanner público compatible Etherscan API format)
- NO wire automático en `strategies.py` ni `gemini_analyzer.py` — solo función pública lista para hook en Spec 010.5
- No alertas Telegram automáticas — `get_whale_html()` provisto para comando manual `/whales` (wire futuro)
- No backfill histórico — solo ventana corta `lookback_hours` (default 24h)

## Dependencias

- `requests` (ya en bot) ✅
- `os.getenv("ETHERSCAN_API_KEY")` opcional (free tier funciona sin key, mejor con)
- `exchange_singleton.binance_futures` para precio USD del token ✅
- `logger_core.logger` para warnings ✅

## Constants en config.py

```python
WHALE_NETFLOW_BEARISH_USD = 10_000_000   # net_flow > 10M = BEARISH
WHALE_NETFLOW_BULLISH_USD = -10_000_000  # net_flow < -10M = BULLISH
WHALE_NETFLOW_CACHE_TTL = 300            # 5 min
WHALE_NETFLOW_TIMEOUT = 8.0              # HTTP timeout
```

Threshold $10M elegido como noise floor:
- Movimientos <$10M en 24h son normales (Binance procesa ~$500M/día spot ETH)
- $10M+ net direccional = movimiento direccional intencional de whale cluster
- Tunable post-7d basado en stats reales

## Exchange wallets hardcoded

ETH chain (verificadas en Etherscan, labels públicos):
- Binance 14: `0x28c6c06298d514db089934071355e5743bf21d60`
- Binance 15: `0xf977814e90da44bfa03b6295a0616a897441acec`
- Coinbase: `0x71660c4005ba85c37ccec55d0c4493e66fe775d3`
- Kraken: `0x2910543af39aba0cd09dbb2d50200b3e800a63d2`
- OKX: `0x6cc5f688a315f3dc28a7781717a9a798a59fda7b`

BSC chain (Binance hot wallets + Bybit + OKX BSC).

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Etherscan free tier 5 calls/sec rate limit | Cache 5min + iteración secuencial (no async parallel) |
| Wallets de exchanges cambian (rotation) | Lista hardcoded revisable; flag `last_update_ts` permite detectar staleness |
| Tokens no-nativos ERC-20 no soportados | Solo ETH/BNB nativo este spec — ERC-20 needs `tokentx` endpoint (Spec 010.5) |
| Precio USD del token vía Binance puede fallar | Try/except + return `{}` graceful |
| Whale "self-transfer" entre wallets propias falso-positivo | Limitación aceptada — magnitud agregada >$10M sigue siendo señal direccional |
| Withdrawal a CEX intermediario (no cold storage real) | Aceptado — proxy imperfecto pero estadísticamente útil |

## Criterio de aceptación

1. `python3 -m py_compile onchain.py config.py` → OK
2. AST: `get_whale_netflow`, `get_whale_html`, `_classify_signal`, `_fetch_wallet_transfers` definidos en `onchain.py`
3. `from config import WHALE_NETFLOW_BEARISH_USD, WHALE_NETFLOW_BULLISH_USD, WHALE_NETFLOW_CACHE_TTL, WHALE_NETFLOW_TIMEOUT` → OK
4. `from onchain import get_whale_netflow` → OK sin side effects (no API call al import)
5. Llamar `get_whale_netflow("ETH", "eth", 24)` sin red → retorna `{}` graceful (no excepción)

## Follow-up — Spec 010.5 candidatos

- Wire en Cuadrilla Zenith voz Genesis (`gemini_analyzer.py`): incluir whale netflow context en prompt cripto
- Comando Telegram `/whales [token]` registrado en `telegram_commands.py`
- ERC-20 token support (USDT, USDC) vía `tokentx` endpoint
- Background polling cada 30min para Genesis (con flag `WHALE_BACKGROUND_POLL = False` default)
- Threshold dinámico basado en volumen 24h del token (escalar para small caps)
