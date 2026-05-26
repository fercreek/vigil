# Spec 022.6 — PnL Real Computation (intel_outcomes.outcome_pnl)

> **Status:** CODE COMPLETE 2026-05-26
> **Owner:** Fernando
> **Severity:** P1 — desbloquea expected-value analysis sobre A/B framework
> **Origen:** Spec 022.5 backlog

## Contexto

Spec 022 creó `intel_outcomes` table + columna `outcome_pnl REAL DEFAULT NULL`. Spec 022.5 agregó auto-update categorial (`outcome` = WIN/LOSS/PARTIAL). **Falta:** computar `outcome_pnl` % real cuando trade cierra. Sin esto, A/B framework solo mide win rate categorial — no diferencia entre 2:1 R:R vs 5:1 R:R. Mismo WR puede tener expected-value muy distinto.

Spec 022.6 extiende el hook 022.5 para calcular `pnl_pct` real desde columnas existentes (`entry_price`, `sl_price`, `tp1_price`, `side`) — sin requerir nueva signature ni close_price live.

## Goals

1. **Helper pure `_compute_pnl_pct(entry, sl, tp1, outcome, side)`** en tracker.py (top-level, sin DB I/O):
   - WIN     → close = tp1            → +R según direction
   - LOSS    → close = sl              → -R según direction
   - PARTIAL → close = midpoint(entry, tp1)  (estimación conservadora)
   - SHORT   → invertir signo
   - Returns float o None si datos insuficientes

2. **Extender Spec 022.5 hook en `update_trade_status`** (después del UPDATE outcome):
   - SELECT entry_price, sl_price, tp1_price, side WHERE alert_id = ? AND outcome = ? AND outcome_pnl IS NULL
   - Compute pnl_pct vía helper
   - UPDATE intel_outcomes SET outcome_pnl = ? WHERE id = ?
   - try/except graceful — fallo NO rompe Spec 022.5 ni trade close
   - Log: `📊 [intel_outcomes] pnl_pct alert_id=X (id=Y, side=SIDE) → +N.NN%`

3. **Extender `get_intel_ab_stats` boost_segments**:
   - `avg_pnl_pct`: AVG(outcome_pnl) por bucket
   - `total_pnl_pct`: SUM(outcome_pnl) por bucket
   - `pnl_n`: COUNT(outcome_pnl NOT NULL) por bucket
   - Cero (0.0) si bucket vacío — sin crashes en dashboard

## Non-goals

- Close_price real desde Binance live API — estimación tp1/sl es conservadora y suficiente para A/B
- PnL en USD absoluto — solo % (size-independent para comparar señales)
- PARTIAL real ratio del partial_pct del trade row — midpoint estático es OK para esta versión
- Backfill retroactivo histórico — out of scope (Spec 022.7 candidato)
- Dashboard chart de pnl distribution — endpoint ya expone fields, frontend opcional

## Dependencias

- `tracker.update_trade_status` Spec 022.5 hook ✅
- `intel_outcomes` columns entry_price, sl_price, tp1_price, side ✅ Spec 022
- `outcome_pnl REAL` columna existente ✅

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Error en compute bloquea Spec 022.5 outcome update | try/except aislado dentro del hook 022.5 outer try |
| División por cero si entry = 0 | Helper retorna None si entry <= 0 |
| SHORT signo inverso mal computado | Test smoke explícito SHORT WIN + SHORT LOSS verifica |
| PARTIAL midpoint sobreestima si trade cerró cerca de entry | Aceptable — estimación cauta es propósito; refinar en Spec 022.7 con partial_pct real |
| Row sin entry/tp1/sl (intel logged pre-Spec 022 fields) | Helper retorna None, UPDATE skipea — sin error |
| outcome_pnl ya populated (manual o re-run) | WHERE outcome_pnl IS NULL evita sobreescribir |

## Criterio de aceptación

1. `python3 -m py_compile tracker.py` → OK
2. Smoke 6 escenarios (todos PASS):
   - LONG WIN (entry 100, tp1 110)  → pnl = +10.0%
   - LONG LOSS (entry 100, sl 95)   → pnl = -5.0%
   - SHORT WIN (entry 100, tp1 90)  → pnl = +10.0%
   - SHORT LOSS (entry 100, sl 105) → pnl = -5.0%
   - LONG PARTIAL (entry 100, tp1 110) → pnl = +5.0% (midpoint 105)
   - OPEN (no-op) → outcome=None, pnl=None
3. `get_intel_ab_stats` boost_segments contiene `avg_pnl_pct`, `total_pnl_pct`, `pnl_n` en cada bucket
4. Producción: próximo trade cerrado → log doble (`auto-updated` + `pnl_pct`) visible
5. Tras 30+ trades cerrados con outcome: `/api/metrics/intel_ab` boost_3+ vs boost_0 muestra `avg_pnl_pct` diferenciado
