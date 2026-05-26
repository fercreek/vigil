# Plan 022 — A/B Test Framework

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Decisiones técnicas

### 1. Tabla nueva vs columnas en `trades`

Nueva tabla `intel_outcomes`. Razón:
- Decoupling: intel ≠ trade strict (alert puede generar episode sin trade)
- Permite log de gates_blocked (alerts NO enviadas, futuras Spec 022.6)
- 0 risk break del schema actual de trades

### 2. Columns capturados

Snapshot completo para post-hoc analysis:
- `alert_id` (link a signal_episodes o trade id)
- `symbol`, `strategy`, `side`
- `intel_json` (TEXT JSON-serialized del _extra_intel)
- `gates_blocked_json` (TEXT JSON list, vacío si alert pasó)
- `boost_applied` (REAL)
- `boost_reasons` (TEXT, comma-separated)
- `conf_score_pre`, `conf_score_post` (REAL)
- `entry_price`, `sl_price`, `tp1_price` (REAL)
- `outcome` (TEXT NULL hasta llenar): WIN | LOSS | PARTIAL
- `outcome_pnl` (REAL NULL)
- `outcome_filled_at` (TEXT NULL CURRENT_TIMESTAMP cuando se llene)
- `ts` (TEXT DEFAULT CURRENT_TIMESTAMP)

### 3. Helpers separados por concern

- `log_intel_event(...)`: INSERT al alert send
- `update_intel_outcome(id, outcome, pnl)`: UPDATE cuando cierra trade
- `get_intel_ab_stats()`: SELECT agregado por buckets de boost

Cero coupling entre helpers — cada uno se llama desde contexto distinto.

### 4. Boost buckets simples

```python
boost_0    : boost_applied = 0   (baseline alerts)
boost_1+   : boost_applied >= 1  (al menos 1 signal aligned)
boost_3+   : boost_applied >= 3  (todos aligned, max teórico 3.5)
```

WR por bucket revela si boost helps o no:
- Si `boost_3+ WR > boost_0 WR + 5pp` → boost works
- Si igual → boost noise, considerar quitar
- Si peor → revisar pesos

### 5. Wire en V3-REVERSAL post `mid`

```python
if mid:  # alert sent
    open_position(...)
    _ep_id = ...
    register_signal_event(...)
    # Spec 022:
    try:
        import tracker as _trk
        _trk.log_intel_event(alert_id=_sid, ...)
    except Exception as _e:
        print(f"intel_log skip: {_e}")
```

Solo después de confirmar `mid` (alert OK Telegram). Evita capturar alerts que fallaron.

### 6. _conf_score_pre snapshot

Insertado entre `conf_score = round(conf_score + social_adj, 2)` y el boost block. Captura el score post-funding/post-social pero pre-boost-Spec-021.

## Verificación

- ✅ py_compile tracker.py + strategies.py + app.py
- ✅ Smoke insert + update + stats
- ✅ Test row cleaned
- Producción pendiente: alerts V3 reales graban; outcome update via Spec 022.5

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(metrics): spec-022 A/B test framework intel outcomes — SQLite + endpoint` |

## Backlog Spec 022.5

- Hook `update_intel_outcome` automático cuando trade cierra (vincular a tracker outcome update existente)
- Capturar gates_blocked en alerts NO enviadas (Spec 022.6)
- Dashboard UI con bar chart WR por boost segment
- Wire log_intel_event en V2-AI / V4 / SWING (cuando boost Spec 021.5 wired)
- Retención de datos: archive a `intel_outcomes_history` después de 90d
- Performance: índice (symbol, ts) en SQLite
