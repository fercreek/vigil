# Spec 022 — A/B Test Framework para Intel Modules

> **Status:** CODE COMPLETE 2026-05-26
> **Owner:** Fernando
> **Severity:** P0 — sin esto, los Spec 016-021 no se validan
> **Origen:** Roadmap Spec 022 (plan.md aprobado)

## Contexto

Specs 016 (gates) + 021 (boost) intervienen V3-REVERSAL pero sin métricas no se puede validar si ayudan o no. Spec 022 captura datos por cada alert V3 para correlacionar con outcome posterior + endpoint que muestra stats.

## Goals

1. Tabla SQLite `intel_outcomes` en `trades.db` con cols completos: intel JSON, gates blocked, boost, conf pre/post, entry/sl/tp, outcome, pnl.
2. Helper `tracker.log_intel_event(...)` se llama POST alert send con `_sid` + datos.
3. Helper `tracker.update_intel_outcome(id, outcome, pnl)` para llenar outcome cuando trade cierra (Spec 022.5 hook a tracker.py outcome flow).
4. Helper `tracker.get_intel_ab_stats()` retorna WR por boost segment + top gates blocking.
5. Endpoint `/api/metrics/intel_ab` expone stats vía API.
6. Wire en `strategies.py:V3-REVERSAL` post `_store_pending` y `mid` send.

## Non-goals

- Hook outcome update automático en flow de trades (Spec 022.5 candidato)
- A/B en V2-AI / V4 / SWING — solo V3 este spec
- Gates blocked logging (alerts NO enviados) — Spec 022.6 candidato
- Dashboard UI nueva para stats — usar `/api/metrics/intel_ab` por ahora

## Dependencias

- `tracker.py` ✅ ya tiene init_db pattern + DB_FILE
- `strategies.py:V3-REVERSAL` ✅ tiene `_sid`, `_boost`, `_boost_reasons`, `_extra_intel`, `conf_score`
- `dashboard_metrics.py` opcional, no requerido

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Tabla nueva sin migration → bot crash en init | `CREATE TABLE IF NOT EXISTS` idempotente, safe |
| Outcome no se rellena → stats con `with_outcome=0` | Spec 022.5 candidato hook automático. Por ahora `update_intel_outcome` manual via API o cron |
| INSERT en cada V3 alert añade latencia | sqlite3 local fast (<5ms). V3 alerts raros (~1-5/día). Negligible |
| JSON malformado en `intel_json` o `gates_blocked_json` | json.dumps + try/except. Si falla → row no se inserta, V3 sigue normal |
| Conf score pre/post no capturado en bug | `_conf_score_pre = conf_score` antes del boost block. Si bug → snapshot incorrecto pero alert sigue |

## Criterio de aceptación

1. `python3 -m py_compile tracker.py strategies.py app.py` → OK
2. `init_db()` crea tabla `intel_outcomes` (verify schema con `sqlite3 trades.db .schema`)
3. Smoke insert + update + stats funciona
4. Endpoint `/api/metrics/intel_ab` retorna JSON con `total/with_outcome/boost_segments/gates_blocked_count/top_gates_blocking`
5. V3 alert real → row en intel_outcomes
6. Producción post-deploy: alerts V3 graban; al cabo de 30+ trades validar `boost_segments` stats
