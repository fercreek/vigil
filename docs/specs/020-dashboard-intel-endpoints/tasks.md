# Tasks 020 — Dashboard Intel Endpoints

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26

## Esta sesión

- [x] `/api/metrics/regime?symbols=...` endpoint (HMM Spec 009)
- [x] `/api/metrics/cvd/<symbol>` endpoint (CVD Spec 012)
- [x] `/api/metrics/onchain_eth?lookback_hours=N` endpoint (Whale Spec 010)
- [x] `/api/metrics/social/<symbol>` endpoint (Social Spec 013)
- [x] Import lazy + 503 si module ImportError
- [x] try/except runtime → 500 con error message
- [x] `generated_at` ISO timestamp en cada response
- [x] py_compile app.py OK
- [x] AST verify 4 endpoints defined
- [ ] Commit `feat(dashboard): spec-020 intel endpoints`
- [ ] Push origin/main

## Verificación post-deploy (Railway)

- [ ] `curl https://[url]/api/metrics/regime` → JSON con 5 símbolos
- [ ] `curl https://[url]/api/metrics/cvd/BTC/USDT` → CVD breakdown
- [ ] `curl https://[url]/api/metrics/onchain_eth` → whale netflow ETH 24h
- [ ] `curl https://[url]/api/metrics/social/BTC` → reddit + trends signal
- [ ] Si hmmlearn missing → 503 explícito (graceful)

## Backlog Spec 020.5+

- [ ] Frontend tweak: regime cards en dashboard_live.html
- [ ] CVD chart over time (depende Spec 012.6 persistence)
- [ ] HTTP Basic auth en /api/metrics/*
- [ ] /api/metrics/grounded_search/usage (Spec 014.6)
- [ ] /api/metrics/regime/history (Spec 009.5 persistence)
- [ ] Caching response headers
