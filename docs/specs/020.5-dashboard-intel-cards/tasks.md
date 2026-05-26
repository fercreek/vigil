# Tasks 020.5 — Dashboard Intel Cards

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26

## Esta sesión

- [x] Sección "📡 Intel en Vivo" agregada antes del footer en dashboard_live.html
- [x] 4 sub-sections con DIVs IDs:
  * regime-cards (HMM 5 cripto)
  * cvd-cards (CVD BTC/ETH)
  * whale-card (Whale ETH 24h)
  * social-cards (Social BTC/ETH/SOL)
- [x] Status indicator `intel-status` ("updated HH:MM:SS")
- [x] Helpers `regimeColor()`, `signalColor()`, `fetchJson(url)`
- [x] Funciones async loadRegimes/loadCVD/loadWhale/loadSocial
- [x] Promise.all paralelo en loadAll()
- [x] setInterval 30s para intel update (página reload 60s)
- [x] Grid responsive `auto-fill minmax(160px, 1fr)`
- [x] Color coding: STRONG_TREND verde, RANGE amarillo, SQUEEZE rojo
- [x] Footer agregado link `/api/metrics/intel_ab`
- [ ] Commit `feat(dashboard): spec-020.5 frontend intel cards`
- [ ] Push origin/main

## Verificación post-deploy

- [ ] Abrir `https://[railway]/dashboard/live` en browser
- [ ] 4 nuevas secciones visibles debajo de Recent Activity
- [ ] HMM cards muestran régimen + confidence per símbolo
- [ ] CVD cards muestran whale/retail amounts + signal
- [ ] Whale card muestra net flow + tx count (si ETHERSCAN_API_KEY)
- [ ] Social cards muestran reddit/trends + signal (si REDDIT creds)
- [ ] Status "updated HH:MM:SS" se actualiza cada 30s
- [ ] Si endpoint falla → card muestra "—" sin crash
- [ ] Mobile <600px responsive OK

## Backlog Spec 020.6

- [ ] Chart.js time-series (régimen history, CVD over time)
- [ ] /api/metrics/regime_transitions endpoint (Spec 002.6) + visualization
- [ ] Botones manual refresh / clear cache
- [ ] HTTP Basic auth (Spec 015.5)
- [ ] Telegram `/dashboard` link helper
- [ ] WebSocket push real-time
