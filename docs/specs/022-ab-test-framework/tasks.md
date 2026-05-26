# Tasks 022 — A/B Test Framework

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26

## Esta sesión

- [x] Tabla `intel_outcomes` en init_db (idempotent CREATE IF NOT EXISTS)
- [x] Columns completos: alert_id, symbol, strategy, side, intel_json,
  gates_blocked_json, boost_applied, boost_reasons, conf_score_pre/post,
  entry/sl/tp1, outcome, outcome_pnl, outcome_filled_at, ts
- [x] Helper `tracker.log_intel_event(...)` INSERT
- [x] Helper `tracker.update_intel_outcome(id, outcome, pnl)` UPDATE
- [x] Helper `tracker.get_intel_ab_stats()` SELECT agregado:
  * total + with_outcome
  * boost_segments: boost_0 / boost_1+ / boost_3+ con count + wr%
  * gates_blocked_count + top_gates_blocking
- [x] Wire en `strategies.py:V3-REVERSAL` post `mid` send + open_position
- [x] `_conf_score_pre` snapshot antes del boost block
- [x] Endpoint `/api/metrics/intel_ab` en app.py
- [x] Smoke test insert + update + stats OK
- [x] Test row cleaned
- [ ] Commit `feat(metrics): spec-022 A/B test framework intel outcomes`
- [ ] Push origin/main

## Verificación post-deploy

- [ ] Próxima alerta V3 real → `sqlite3 trades.db "SELECT * FROM intel_outcomes ORDER BY id DESC LIMIT 1"` muestra row
- [ ] `curl https://[url]/api/metrics/intel_ab` retorna JSON con stats
- [ ] Tras 30+ trades V3: boost_segments WR comparison valida boost Spec 021
- [ ] Si boost_3+ WR > boost_0 WR + 5pp → Spec 021 boost works

## Backlog Spec 022.5

- [ ] Auto-update outcome cuando trade cierra (link a tracker outcome flow)
- [ ] Capturar gates_blocked en alerts NO enviadas (Spec 022.6)
- [ ] Dashboard UI bar chart por boost segment
- [ ] Wire log_intel_event en V2-AI/V4/SWING
- [ ] Retención: archive a intel_outcomes_history >90d
- [ ] SQLite índice (symbol, ts)
