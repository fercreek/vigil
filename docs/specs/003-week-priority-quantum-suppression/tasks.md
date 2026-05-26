# Tasks 003 — Week Priority + Quantum Suppression

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-25 — pending commit + lunes verification

## To-do esta sesión (25-May-2026)

- [x] Constantes nuevas en `config.py` (WEEK_PRIORITY_HIGH/MEDIUM/LOW, QUANTUM_SUPPRESSED, QUANTUM_REENTRY_PULLBACK_PCT, PRIORITY_BOOST_CLUSTER, WEEK_REVIEW_DATE)
- [x] CLAUDE.md sección 8k — análisis PTS + plan semanal
- [x] Import constantes en `stock_analyzer.py:stock_watchdog()` (line ~298)
- [x] Stale check WEEK_REVIEW_DATE (pre-loop, log WARNING si >7d)
- [x] Gate `QUANTUM_SUPPRESSED` skip (continue + log info)
- [x] Compute `priority_tag` por símbolo (HIGH = 🔥, LOW = 🟢, resto = "")
- [x] Prepend `priority_tag` en `ZONE_ALERT` msg (line ~336)
- [x] Prepend `priority_tag` en `ENTRY_ALERT` msg (line ~354)
- [x] `python3 -m py_compile stock_analyzer.py` → OK
- [x] Smoke test dispatcher (IONQ→skip, CRWV→🔥, XOM→🟢, NVDA→default) → PASS
- [ ] Commit `feat(stock): spec-003 week priority + quantum suppression`

## Verificación pendiente (lunes 26-May post-apertura)

- [ ] Bot loguea `"IONQ SUPRIMIDA"` + `"RGTI SUPRIMIDA"` (si caen en loop)
- [ ] Confirmar 0 alertas Telegram para IONQ/RGTI durante semana
- [ ] Si CRWV/COIN llega zona entrada → msg empieza con 🔥 PRIORIDAD ALTA
- [ ] Si XOM/JNJ llega zona entrada → msg empieza con 🟢 DEFENSIVA
- [ ] No regresión en alertas de símbolos sin priority (NVDA, etc.)

## Backlog post-semana (1-Jun-2026 cierre)

- [ ] Revisar `_LEARNING_LOG.md` — ¿priorización ayudó a Fernando filtrar mejor?
- [ ] Si sí → automatizar parse de reporte PTS para regenerar WEEK_PRIORITY_*
- [ ] Si no → eliminar tags y volver default
- [ ] Considerar columna `priority` en `signal_episodes` para analytics post-mortem

## Blocked / future

- Pullback detector real para auto-reactivar QUANTUM_SUPPRESSED (requiere series histórica 7d + threshold acordado con PTS).
- Cablear `MAX_PER_CLUSTER` + `PRIORITY_BOOST_CLUSTER` (requiere primero implementar conteo de posiciones simultáneas open en `tracker.py`).
