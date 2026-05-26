# Tasks 010 — Whale Netflows On-Chain Tracker

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26

## Esta sesión

- [x] `onchain.py` creado en raíz del repo
  - `get_whale_netflow(token, chain, lookback_hours, min_value_usd)` pública
  - `get_whale_html(token, chain, lookback_hours)` para Telegram futuro
  - `_classify_signal`, `_fetch_wallet_transfers`, `_get_api_config`, `_get_token_price_usd` privados
- [x] Hardcoded 5 wallets ETH (Binance 14/15, Coinbase, Kraken, OKX)
- [x] Hardcoded 5 wallets BSC (Binance hot x3, Bybit, OKX)
- [x] Cache module-level dict con TTL 5min
- [x] 4 constantes agregadas a `config.py`:
  - WHALE_NETFLOW_BEARISH_USD = 10_000_000
  - WHALE_NETFLOW_BULLISH_USD = -10_000_000
  - WHALE_NETFLOW_CACHE_TTL = 300
  - WHALE_NETFLOW_TIMEOUT = 8.0
- [x] Spec docs (spec.md, plan.md, tasks.md) creados
- [x] py_compile + AST verification
- [ ] Commit `feat(onchain): spec-010 whale netflows tracker` (Fernando hará en main thread)
- [ ] Push origin/main (Fernando)

## Verificación post-deploy

- [ ] Sin error de import en arranque (`from onchain import get_whale_netflow`)
- [ ] No side-effects de la nueva module a otros flows (V2-AI, V3, V4, SWING)
- [ ] Llamar `get_whale_netflow("ETH")` manual → retorna dict con campos esperados
- [ ] Si Etherscan timeout / rate limit → log warning, retorna `{}`, no crashea

## Próximos specs (010.5 candidates)

- [ ] **Spec 010.5a** — Wire en Cuadrilla Zenith voz **Genesis** (`gemini_analyzer.py`)
  - Incluir whale netflow context en prompt cripto: "Net flow 24h: $X (signal: BEARISH/BULLISH/NEUTRAL)"
  - Genesis tradicionalmente la voz fundacional/macro — encaja con on-chain structure
- [ ] **Spec 010.5b** — Comando Telegram `/whales [token]`
  - Registrar en `telegram_commands.py`
  - HTML output ya provisto por `get_whale_html()`
- [ ] **Spec 010.5c** — ERC-20 token support (USDT, USDC vía `tokentx` endpoint)
  - Spec aparte porque cambia el endpoint y agrega complejidad de contract_address mapping
- [ ] **Spec 010.5d** — Background polling cada 30min (opt-in con flag default False)

## Notas

- API key Etherscan **NO requerida** para free tier basic queries — el código la usa si está en `.env` como `ETHERSCAN_API_KEY` (recomendado para mejor rate limit)
- BSC chain incluida pero menos prioritaria (volume whale ETH > BSC)
- Solana / Tron / otras chains requieren scanner diferente — fuera de scope este spec
