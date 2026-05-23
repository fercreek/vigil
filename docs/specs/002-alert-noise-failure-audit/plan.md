# Plan 002 — Alert Noise + Failure Audit

> **Spec:** [spec.md](spec.md)
> **Status:** COMPLETED

## Estrategia

Tres fases ejecutadas en serie en la misma sesión 2026-05-23:

1. **Diagnóstico** (paralelo): 3 agentes audit (B/C/D) leen DB local + código.
2. **P0 fixes** (foreground): aplicar resultados consolidados.
3. **Audit intenso post-P0**: cubrir failure modes que silencian alertas accionables.

## Commits en orden

| Hash | Scope | Notas |
|------|-------|-------|
| `c299b09` | fix: PULSO+PANORAMA gate + Sentinel RSI/direction filter | Audit inicial visual de alertas Telegram pegadas por Fernando. |
| `94bec99` | feat: ENABLE_TELEGRAM_BUTTONS kill switch | Permite reactivar botones case-by-case. |
| `94e3cb6` | feat: P0 quiet mode + AI DB fix + TAO sentinel kill + stock outcomes | Resultado consolidado audits B/C/D. |
| `db3681d` | fix: alerts no enviadas — 4 failure modes | signal_coordinator + retry + heartbeat + persistencia. |

## Decisiones técnicas

### 1. Kill switches, no destrucción

Toda funcionalidad ruidosa quedó detrás de flag:
- `ENABLE_TELEGRAM_BUTTONS` (default False)
- `ANALYSIS_MODE_QUIET` (default True)
- `KILL_SALMOS_PROPHECY` (preexistente, True)
- `TAO_TRADING_ENABLED` (preexistente, False, ahora gateando sentinel + bias)
- `V1_LONG_ENABLED`, `V1_SHORT_ENABLED`, `V5_ENABLED` (preexistente, False)

Razón: período de análisis = silenciar. Si una decisión se prueba mala, revertir = un flag.

### 2. AI DB path: absoluto en lugar de relativo

`ai_budget.py:25` hacía `from tracker import DB_FILE` que sufría race condition cuando Railway proceso tenía cwd distinto al repo. Solución: `os.path.dirname(os.path.abspath(__file__))` resuelve siempre al repo root.

### 3. signal_coordinator: confidence threshold

Bug: caller hace `submit() + resolve_and_send()` mismo turn → `oldest_age=0 < WINDOW_SECS=120` → siempre HOLD. Nadie re-llamaba después de 120s. Single-source signals quedaban colgadas.

Fix: si `confidence >= 0.7` enviar inmediato. Lo que pierde: ventana de "esperar a ver si otros source confirman". Lo que gana: alertas reales no se pierden.

### 4. send_telegram: 3 retries con backoff

Reemplaza 1-shot fail por:
- Try 1 → sleep 1s
- Try 2 → sleep 2s
- Try 3 → sleep 4s

Casos especiales:
- 429: respeta `retry_after` de payload
- 401/403/404: no retry (auth/chat err = no recuperable)

### 5. stock_analyzer: heartbeat batched

`_fetch_prices` ahora llama `thread_health.heartbeat("stock")` cada 10 símbolos. Con 37 tickers y ~3-5s/símbolo, el peor caso baja de un solo bloque de 185s a 4 segmentos heartbeated. Watchdog ya no mata el thread.

### 6. `_alert_cache` persistente JSON

Path: `data/stock_alert_cache.json`. Helpers `_mark_alert()` / `_clear_alert()` salvan en cada mutación. Idempotente. Tamaño esperado < 5KB con watchlist de 37 tickers.

## Riesgos conocidos

| Riesgo | Mitigación |
|--------|-----------|
| Kill switches no se reactivan a tiempo | Documentado en spec; revisión semanal |
| yfinance fallback en check_pending_outcomes costoso | Cache local por ciclo limita a N símbolos distintos × 1 call/ciclo |
| Retry 3× puede causar latencia 7s en send fail | Acceptable; alertas son async vs HFT |
| `_alert_cache` JSON race condition (multi-thread) | Solo stock thread escribe; no race |
| TradingView webhook ahora envía single-source confianza 0.7 | Verificar en producción que webhook payload tiene confidence ≥ 0.7 |

## Métricas a observar post-deploy

- Alert volume/día (target: < 10 accionables Telegram)
- `ai_calls` count post 2026-05-23 (debe empezar a llenarse)
- `signal_episodes.outcome IS NULL` % (debe bajar desde 79%)
- Stock thread restart count (esperado: 0/día)
- Telegram send fail count en logs (esperado: < 5/día)
