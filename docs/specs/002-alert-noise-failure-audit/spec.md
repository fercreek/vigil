# Spec 002 — Alert Noise + Failure Audit + Quiet Mode

> **Status:** COMPLETED 2026-05-23
> **Created:** 2026-05-23
> **Owner:** Fernando
> **Severity:** P0 — bot sobrecargado de ruido + alertas accionables se perdían silenciosamente

## Problema raíz

Mezcla de dos fallas opuestas:
1. **Demasiado ruido** en Telegram: PULSO + PANORAMA + SENTINEL TAO + NINJA + 3× startup msgs por redeploy. Mensajes contradictorios (LONG @ RSI 76 "esperar pullback").
2. **Alertas accionables perdidas en silencio**: signal_coordinator HOLD permanente, Telegram send fails sin retry, stock thread crash loop, `_alert_cache` wipe en restart.

Resultado: Fernando recibía decenas de alertas no accionables + faltaban señales reales. Imposible medir bot.

## Síntomas medidos

| # | Síntoma | Origen | Severidad |
|---|---------|--------|-----------|
| S1 | PULSO 16:00 + PANORAMA 16:01 = duplicado AI | check_market_pulse + main loop | P0 |
| S2 | PANORAMA CLAVE truncado | output Gemini cortado | P2 |
| S3 | SENTINEL TAO 4/5 LONG @ RSI 76 contradictorio | should_send_sentinel sin filtro RSI | P1 |
| S4 | TAO consumía 67% costo AI sin trades | `bias` calls + SENTINEL TAO activos | P1 |
| S5 | `ai_calls` invisible desde Apr 7 | DB path mismatch tracker vs ai_budget | P0 |
| S6 | 22+ stock episodes huérfanas | check_pending_outcomes solo cripto prices | P1 |
| S7 | `_alert_cache` in-memory wipe en restart | stock_analyzer module-level dict | P0 |
| S8 | TradingView webhook nunca emitía Telegram | signal_coordinator single-source HOLD bug | P0 |
| S9 | Telegram fails silentes (429/DNS) | send_telegram 1-shot sin retry | P1 |
| S10 | Stock thread crash loop | _fetch_prices block >300s, watchdog kill | P1 |
| S11 | Botones inline ruido + UX no necesario | inline_keyboard hardcoded en 5 sites | P2 |
| S12 | Startup ONLINE × 3 threads ruido por redeploy | bot.main + swing + stock unconditional | P2 |

## Goals (qué se considera resuelto)

1. **PULSO + PANORAMA** no duplican (gate 600s).
2. **SENTINEL** filtra direction vs RSI extremo (LONG≥72 / SHORT≤28).
3. **TAO** sin SENTINEL ni bias cuando `TAO_TRADING_ENABLED=False`.
4. **`ai_calls`** se loguea a `trades.db` raíz (path absoluto).
5. **Stock episodes** se auto-cierran (yfinance fallback en check_pending_outcomes).
6. **`_alert_cache`** persiste a `data/stock_alert_cache.json`.
7. **signal_coordinator** envía single-source si confidence ≥ 0.7.
8. **Telegram send** 3 intentos con backoff exponencial + respeto a 429 retry_after.
9. **Stock thread** heartbeat cada 10 símbolos durante batch yfinance.
10. **ENABLE_TELEGRAM_BUTTONS** kill switch global (default False).
11. **ANALYSIS_MODE_QUIET** kill switch global de status alerts (default True).

## Non-goals

- Persistencia `_alert_cache` en SQLite (JSON suficiente).
- Refactor signal_coordinator a state machine.
- Migración yfinance → polygon/finnhub.
- Cache hit fix Claude Haiku (P2 backlog).
- Persona column en `ai_calls` (P1 backlog).
- BitLobo episodes auto-fill tp sintético (P1 backlog).

## Dependencias

- `config.py` — flags ENABLE_TELEGRAM_BUTTONS + ANALYSIS_MODE_QUIET.
- `alert_manager.py` — retry + button gate.
- `signal_coordinator.py` — single-source fix.
- `scalp_alert_bot.py` — quiet gates + sentinel TAO skip + PULSO/PANORAMA gate.
- `gemini_analyzer.py` — get_weekly_bias TAO skip.
- `episode_memory.py` — yfinance fallback.
- `stock_analyzer.py` — heartbeat + persistencia + button gate.
- `swing_bot.py`, `commodities_bot.py`, `scalper_shorts_bot.py` — button gate.
- `strategies.py` — NINJA quiet gate.
- `ai_budget.py` — DB path absoluto.
