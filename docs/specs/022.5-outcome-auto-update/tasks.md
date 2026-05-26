# Tasks 022.5 — Outcome Auto-Update

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26

## Esta sesión

- [x] Hook en `tracker.update_trade_status` después del UPDATE trades
- [x] Mapping status → outcome (5 transitions cubiertas)
- [x] WHERE outcome IS NULL — no sobreescribe manual updates
- [x] Connection separada para intel_outcomes UPDATE
- [x] try/except graceful — trade close NO falla si intel UPDATE fails
- [x] Log `📊 [intel_outcomes] auto-updated alert_id=X → OUTCOME` visible
- [x] py_compile tracker.py OK
- [x] Smoke completa: insert intel + trade + update_trade_status → outcome verified
- [x] Mapping test 5 transitions correctos (FULL_WON/WON/PARTIAL_*/LOST/OPEN)
- [ ] Commit `feat(metrics): spec-022.5 outcome auto-update hook`
- [ ] Push origin/main

## Verificación post-deploy

- [ ] Próximo trade cerrado en bot Railway → log `[intel_outcomes] auto-updated alert_id=X → WIN`
- [ ] `sqlite3 trades.db "SELECT id, alert_id, outcome FROM intel_outcomes WHERE outcome IS NOT NULL LIMIT 5"` muestra rows con outcomes
- [ ] `curl https://[url]/api/metrics/intel_ab` → `with_outcome > 0`, boost_segments WR no vacíos
- [ ] Tras 30+ trades cerrados: validar boost_3+ WR vs boost_0 WR diferencia

## Backlog Spec 022.6

- [ ] Computar PnL real (signature update_trade_status + close_price param)
- [ ] Hook en episode_memory.resolve_outcome (alerts SIM sin trade row)
- [ ] Dashboard /api/metrics/intel_ab → chart WR distribution Spec 020.7
- [ ] Script one-shot retroactivo llenar intel_outcomes históricos
- [ ] Notif Telegram cuando segment achieves stat significance (N≥30, Δ≥5pp)
