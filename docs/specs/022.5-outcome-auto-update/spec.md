# Spec 022.5 — Outcome Auto-Update Hook (intel_outcomes)

> **Status:** CODE COMPLETE 2026-05-26
> **Owner:** Fernando
> **Severity:** P0 — desbloquea Spec 022 A/B framework
> **Origen:** Spec 022 backlog

## Contexto

Spec 022 creó `intel_outcomes` table + `log_intel_event` (INSERT al alert send) + `update_intel_outcome` (UPDATE al cerrar trade). **Falta:** llamar `update_intel_outcome` automático cuando trade transita a FULL_WON/LOST/PARTIAL_CLOSED. Sin esto, tabla intel_outcomes nunca recibe outcome → `get_intel_ab_stats()` retorna WR 0% siempre → A/B framework inútil.

Spec 022.5 hook simple en `tracker.update_trade_status` — el chokepoint único donde trades cambian status.

## Goals

1. Modificar `tracker.update_trade_status(trade_id, status)`:
   - Después del UPDATE de `trades`, agregar query UPDATE `intel_outcomes` SET outcome = X WHERE alert_id = trade_id
   - Status mapping:
     * `FULL_WON` / `WON` → `"WIN"`
     * `PARTIAL_CLOSED` / `PARTIAL_WON` → `"PARTIAL"`
     * `LOST` → `"LOSS"`
     * Otros (`OPEN`, etc.) → no update
   - `outcome_filled_at = CURRENT_TIMESTAMP`
   - `WHERE outcome IS NULL` — no sobreescribe update manual previo
   - try/except graceful — error no rompe el flow normal

2. Log visible para debug: `📊 [intel_outcomes] auto-updated alert_id=X → OUTCOME`

## Non-goals

- Computar PnL real (entry_price - close_price ratio) — Spec 022.6 candidato
- Hook en otras strategies actualizando trade status fuera de update_trade_status — bot ya canaliza todo aquí
- Update retroactivo de trades históricos pre-022 — out of scope (intel_outcomes tabla nueva)
- Dashboard auto-refresh stats al cerrar trade — endpoint Spec 022 ya retorna stats live

## Dependencias

- `tracker.py:update_trade_status` ✅ chokepoint identificado
- `intel_outcomes` table ✅ Spec 022
- `alert_id` en intel_outcomes = trade.id (Spec 022 wire usa `_sid` retorno de `_store_pending`)

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Error en UPDATE intel_outcomes bloquea trade close | try/except wrap — falla silent, trade close sigue normal |
| Race condition: trade status update + intel insert concurrent | SQLite single-writer lock, sin race |
| Mapping de status incorrecto | Tests smoke 5 transiciones verificadas |
| Trade legacy sin intel row (pre-Spec 022) | UPDATE matches 0 rows, no error |
| Update sobre row con outcome ya manual | `WHERE outcome IS NULL` evita sobreescribir |

## Criterio de aceptación

1. `python3 -m py_compile tracker.py` → OK
2. Smoke completa:
   - log_intel_event insert con alert_id=X
   - update_trade_status(X, 'FULL_WON')
   - SELECT outcome FROM intel_outcomes WHERE id = X → 'WIN'
   - outcome_filled_at populated CURRENT_TIMESTAMP
3. Mapping correcto FULL_WON/WON→WIN, PARTIAL_*→PARTIAL, LOST→LOSS, OPEN→no update
4. Producción: próximo trade cerrado en bot → intel_outcomes recibe outcome auto
5. Tras 30+ trades cerrados: `/api/metrics/intel_ab` muestra `with_outcome > 0` y WR boost segments populated
