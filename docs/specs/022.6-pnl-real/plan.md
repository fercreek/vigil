# Plan 022.6 — PnL Real Computation

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Decisiones técnicas

### 1. Helper pure `_compute_pnl_pct` (top-level, sin DB I/O)

Separar el cálculo de la persistencia permite:
- Test unitario simple (no DB setup)
- Reuso desde otros call sites futuros (e.g. backfill script, dashboard preview)
- Lógica única de signo SHORT — un solo lugar para auditar

Firma:
```python
def _compute_pnl_pct(entry, sl, tp1, outcome, side) -> float | None
```

### 2. Estimación close_price (sin Binance live API)

```
WIN     → close = tp1                  (asume hit TP1, sin overshoot)
LOSS    → close = sl                   (asume hit SL exacto)
PARTIAL → close = (entry + tp1) / 2    (midpoint conservador)
```

Razón: `update_trade_status(trade_id, status)` NO recibe close_price. Las columnas existentes en intel_outcomes (entry/sl/tp1) capturadas al INSERT time son la fuente de verdad disponible. Estimación de tp1/sl es **realista para la mayoría de cierres** porque el flow del bot triggers status update justo cuando se hit TP o SL.

Refinamiento futuro (Spec 022.7): leer `trades.partial_pct` para PARTIAL real, leer `trades.close_price` si existe.

### 3. Signo SHORT invertido

```python
pnl_pct = (close - entry) / entry * 100
if side == "SHORT":
    pnl_pct *= -1
```

Para SHORT, hit del TP (tp1 < entry) da diferencia negativa; flip de signo refleja ganancia real del trader. Tested explícitamente en smoke (SHORT WIN entry 100 / tp1 90 → +10%).

### 4. Hook extension dentro del try/except Spec 022.5

Anidar el bloque PnL **dentro** del outer try del hook 022.5, con su propio inner try. Razón:
- Si compute falla, NO debe regresar el outcome update categorial (Spec 022.5 ya commiteado anteriormente)
- Trade close NO debe fallar por cálculo de PnL
- Log de error visible pero no escalado

```python
try:
    # ... Spec 022.5 outcome UPDATE ...
    _conn.commit()
    try:
        # Spec 022.6 compute + UPDATE outcome_pnl
        ...
    except Exception as _pe:
        print(f"[intel_outcomes pnl_pct ERROR] ...")
    _conn.close()
except Exception as _e:
    print(f"[intel_outcomes auto-update ERROR] ...")
```

### 5. Reuso de connection abierta

El bloque PnL reutiliza `_conn`/`_c` del hook 022.5 (aún abierta antes del `.close()`). Single round-trip a SQLite — eficiente, sin race.

### 6. SELECT con filtro `outcome_pnl IS NULL`

Evita recomputar y sobreescribir. Idempotent — si el hook corre 2 veces para el mismo trade_id, la segunda es no-op en el UPDATE PnL.

### 7. AVG/SUM en `get_intel_ab_stats` con manejo NULL

```sql
SELECT AVG(outcome_pnl), SUM(outcome_pnl), COUNT(outcome_pnl)
FROM intel_outcomes
WHERE {condition} AND outcome_pnl IS NOT NULL
```

SQLite ignora NULLs en AGG funcs automáticamente, pero el `WHERE ... IS NOT NULL` hace explícito el `pnl_n` (registros con PnL computed, distinto del count total del bucket que incluye OPENs).

Caso bucket vacío: AVG/SUM retornan NULL → conversión `round(float(_avg), 3) if _avg is not None else 0.0` previene crashes en dashboard frontend.

## Verificación

- ✅ py_compile tracker.py
- ✅ Smoke 6 escenarios (LONG WIN/LOSS/PARTIAL + SHORT WIN/LOSS + OPEN no-op) all PASS
- ✅ get_intel_ab_stats devuelve avg_pnl_pct, total_pnl_pct, pnl_n en cada bucket
- ✅ Log dual visible: `auto-updated` (Spec 022.5) + `pnl_pct` (Spec 022.6)
- ✅ WHERE outcome_pnl IS NULL evita re-compute idempotent

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(metrics): spec-022.6 pnl_pct real computation en intel_outcomes` |

## Backlog Spec 022.7

- **Expected Value boost-segment analysis**: `EV = WR × avg_pnl_pct_wins + (1-WR) × avg_pnl_pct_losses`. Comparar boost_3+ EV vs boost_0 EV — métrica definitiva del A/B test.
- Backfill retroactivo: script one-shot llenar outcome_pnl para rows con outcome NOT NULL pero outcome_pnl NULL (pre-Spec 022.6 history).
- PARTIAL refinement: leer `trades.partial_pct` para computar close real (e.g. 50% partial → close = entry + 0.5*(tp1-entry)).
- close_price real desde Binance API on close event — opcional, si el slippage importa en analytics.
- Dashboard endpoint `/api/metrics/intel_ab` → chart distribution de PnL por bucket (histogram + box plot).
- Notif Telegram cuando boost_3+ EV achieves stat significance (N≥30, EV diff ≥ 1pp).
