# Spec 020 — Dashboard Intel Endpoints (regime, CVD, onchain, social)

> **Status:** CODE COMPLETE 2026-05-26
> **Owner:** Fernando
> **Severity:** P1 — expose intel modules to Flask dashboard API
> **Origen:** Spec 015.5 backlog + Specs 009/010/012/013 follow-up

## Contexto

Spec 015 dejó dashboard live con métricas trades.db (WR, recent trades, episodes). Faltaba exponer los módulos intel nuevos (HMM/CVD/onchain/social) como endpoints API para que el dashboard o tooling externo puedan consultar el estado actual.

Spec 020 agrega 4 endpoints REST:
- `/api/metrics/regime?symbols=BTC/USDT,ETH/USDT` — HMM regime por símbolo
- `/api/metrics/cvd/<symbol>` — CVD segmentado
- `/api/metrics/onchain_eth?lookback_hours=24` — whale netflow ETH
- `/api/metrics/social/<symbol>` — Reddit + Google Trends sentiment

## Goals

1. Cada endpoint:
   - Import lazy del módulo intel respectivo
   - Si import falla (módulo no instalado) → 503 con mensaje claro
   - Si llamada fail → 500 con error
   - Si OK → JSON con datos + `generated_at` timestamp

2. Parámetros razonables:
   - `regime` acepta CSV `?symbols=...`
   - `cvd` y `social` toman símbolo en path
   - `onchain_eth` acepta `?lookback_hours=N`

## Non-goals

- Modificar `dashboard_live.html` para mostrar nuevos métricas — Spec 020.5 candidato (Frontend tweak)
- Autenticación / rate limit — Spec 015.5 candidato
- Endpoints para `/api/metrics/funding` (ya existe en otro lado)
- Endpoint `/api/metrics/grounded_search/usage` — Spec 014.6 candidato

## Dependencias

- `regime_hmm.detect_regime` ✅ (Spec 009)
- `cvd_segmented.compute_cvd_segmented` ✅ (Spec 012)
- `onchain.get_whale_netflow` ✅ (Spec 010)
- `social_quant.get_social_sentiment` ✅ (Spec 013)
- Flask `request`, `jsonify`, `datetime` ✅ ya en app.py

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Módulo intel falla y bloquea dashboard | Cada endpoint try/except aislado. 503 si import fail, 500 si runtime error |
| Endpoint expone API gratis sin auth | Spec 015.5 candidato auth. Por ahora solo se accede via Railway internal URL. |
| Query lento bloquea Flask worker | Cada módulo intel tiene su propio cache TTL. Worst case ~2s |
| Símbolo malformado en path | Flask `<path:symbol>` permite "/" en el path (BTC/USDT). Manejo via path converter |
| Daily cap exhausted en grounded_search no expone aquí | Endpoint social no usa grounded — usa Reddit/Trends. Sin riesgo cross-cap |

## Criterio de aceptación

1. `python3 -m py_compile app.py` → OK
2. AST: 4 endpoints definidos (`api_metrics_regime`, `api_metrics_cvd`, `api_metrics_onchain_eth`, `api_metrics_social`)
3. Cada endpoint envuelto en try/except con import lazy
4. Si módulo missing → 503 con error message
5. Si OK → JSON con datos + `generated_at`
6. Producción pendiente: probar endpoints en Railway URL con curl o browser
