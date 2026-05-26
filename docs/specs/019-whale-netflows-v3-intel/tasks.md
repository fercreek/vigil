# Tasks 019 — Whale Netflows V3 INTEL

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26

## Esta sesión

- [x] V3-REVERSAL fetch whale netflow si `sym_base == "ETH"`
- [x] Guardar `_whale = {}` para uso después de fetch
- [x] Agregar `whale_signal` + `whale_net_flow_usd` a `_extra_intel`
- [x] Extender `_format_extra_intel` con línea whale (mapeo Genesis)
- [x] Try/except graceful — sin ETHERSCAN_API_KEY → skip whale, INTEL parcial
- [x] py_compile gemini_analyzer.py strategies.py OK
- [x] Smoke: full intel con whale → 4 líneas, sin whale → 3 líneas
- [ ] Commit `feat(onchain): spec-019 whale netflows V3 INTEL`
- [ ] Push origin/main

## Verificación post-deploy

- [ ] Próxima alerta V3 ETH/USDT en Railway → Telegram muestra línea whale en INTEL
- [ ] V3 BTC/SOL/etc → INTEL sin línea whale (correcto)
- [ ] Etherscan API key configurada (env var ETHERSCAN_API_KEY) — recommended
- [ ] Cache 5min activo → no rate limit Etherscan

## Backlog Spec 019.5

- [ ] Agregar BTC via blockchain.com API gratis
- [ ] Agregar SOL via SolanaFM gratis
- [ ] Whale gate BEARISH → kill V3 LONG (post-validation)
- [ ] Whale netflow trend 5d slope
- [ ] Dashboard endpoint `/api/metrics/onchain_eth`
