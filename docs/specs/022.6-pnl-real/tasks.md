# Tasks 022.6 — PnL Real Computation

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26

## Esta sesión

- [x] Helper pure `_compute_pnl_pct(entry, sl, tp1, outcome, side)` en tracker.py top-level
- [x] WIN → close=tp1, LOSS → close=sl, PARTIAL → midpoint(entry, tp1)
- [x] SHORT signo invertido
- [x] Returns None si datos insuficientes (entry <= 0, tp1/sl missing)
- [x] Hook extension en `update_trade_status` Spec 022.5
- [x] SELECT entry/sl/tp1/side WHERE outcome_pnl IS NULL (idempotent)
- [x] UPDATE outcome_pnl per row
- [x] try/except interno aislado — no afecta Spec 022.5 ni trade close
- [x] Log `📊 [intel_outcomes] pnl_pct alert_id=X (id=Y, side=SIDE) → ±N.NN%`
- [x] Extender `get_intel_ab_stats` boost_segments con avg_pnl_pct, total_pnl_pct, pnl_n
- [x] Cero (0.0) en bucket vacío sin crash
- [x] py_compile tracker.py OK
- [x] Smoke 6 escenarios PASS (LONG WIN/LOSS/PARTIAL, SHORT WIN/LOSS, OPEN no-op)
- [ ] Commit `feat(metrics): spec-022.6 pnl_pct real computation en intel_outcomes`
- [ ] Push origin/main

## Verificación post-deploy

- [ ] Próximo trade cerrado Railway → log dual visible: `auto-updated` + `pnl_pct`
- [ ] `sqlite3 trades.db "SELECT id, alert_id, outcome, outcome_pnl FROM intel_outcomes WHERE outcome_pnl IS NOT NULL LIMIT 10"` populated rows
- [ ] `curl https://[url]/api/metrics/intel_ab` boost_segments contienen `avg_pnl_pct`, `total_pnl_pct`, `pnl_n` no-zero
- [ ] Tras 30+ trades cerrados: comparar avg_pnl_pct boost_3+ vs boost_0 → diferencia esperada ≥ 1pp

## Backlog Spec 022.7

- [ ] Expected Value (EV) per boost segment: `WR×avg_pnl_win + (1-WR)×avg_pnl_loss`
- [ ] Backfill retroactivo: script one-shot llena outcome_pnl para rows pre-022.6
- [ ] PARTIAL refinement: leer `trades.partial_pct` real (no midpoint estático)
- [ ] close_price real desde Binance API on close event (slippage capture)
- [ ] Dashboard chart distribution PnL por bucket (histogram/box plot)
- [ ] Notif Telegram cuando boost_3+ EV achieves stat significance (N≥30, ΔEV≥1pp)
