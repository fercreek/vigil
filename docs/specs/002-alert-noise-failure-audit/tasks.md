# Tasks 002 — Alert Noise + Failure Audit

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** ALL DONE 2026-05-23

## Done en esta sesión

- [x] Audit B paralelo: signal_episodes huérfanas (31/39 = 79.5%)
- [x] Audit C paralelo: AI cost ROI (ciego desde Apr 7, TAO 67% costo)
- [x] Audit D paralelo: alert noise frequency (mapeo 25 tipos alertas)
- [x] Fix PULSO + PANORAMA gate 600s (`scalp_alert_bot.py:894-1054`)
- [x] Fix Sentinel direction vs RSI filter (`scalp_alert_bot.py:1128-1135`)
- [x] ENABLE_TELEGRAM_BUTTONS kill switch (`config.py` + 5 sites)
- [x] ANALYSIS_MODE_QUIET kill switch (`config.py` + 4 sites)
- [x] ai_budget DB path absoluto (`ai_budget.py:24-26`)
- [x] TAO SENTINEL skip cuando TAO_TRADING_ENABLED=False (`scalp_alert_bot.py:1082-1085`)
- [x] TAO bias skip cuando TAO_TRADING_ENABLED=False (`gemini_analyzer.py:801-808`)
- [x] check_pending_outcomes yfinance fallback (`episode_memory.py:155-172`)
- [x] signal_coordinator confidence-based send (`signal_coordinator.py:59-71`)
- [x] send_telegram 3-retry backoff (`alert_manager.py:153-178`)
- [x] _fetch_prices heartbeat batched (`stock_analyzer.py:86-110`)
- [x] _alert_cache persistente JSON (`stock_analyzer.py:203-237`)

## Backlog P1 (sesión siguiente)

- [ ] BitLobo signals: auto-fill tp1 sintético o skip episode si NULL (`stock_analyzer.py:312`)
- [ ] Agregar columna `persona` a `ai_calls` + logging Cuadrilla Zenith
- [ ] Cleanup script: marcar STALE en huérfanas >14d
- [ ] Migrar `_alert_cache` JSON → SQLite (race-safe future-proof)
- [ ] Verificar 0% cache hit Claude Haiku

## Backlog P2

- [ ] ZEC retry loop backoff cuando daily cap AI hit (`gemini_analyzer.py:463`)
- [ ] NINJA + V3 shared cooldown por símbolo (cuando se reactive)
- [ ] Auto-trigger commit message si pierde watchdog
- [ ] Test integración Telegram send (mock requests)
- [ ] Dashboard simple: alert volume + AI cost diario

## Verificación pendiente (próxima sesión mercado vivo)

- [ ] Confirmar PULSO 16:00 NO dispara (quiet on)
- [ ] Confirmar PANORAMA cada 2h NO dispara (quiet on)
- [ ] Confirmar SENTINEL ZEC SÍ dispara si setup válido
- [ ] Confirmar STOCK NEAR ENTRY funciona sin botones (mensaje claro)
- [ ] Verificar `ai_calls` se llena con nuevos rows en `trades.db` raíz
- [ ] Verificar `signal_episodes` outcome se llena para stocks
- [ ] Verificar stock thread no se reinicia en 24h
- [ ] Verificar `data/stock_alert_cache.json` se crea + actualiza
