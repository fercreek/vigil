# Plan 001 — Bot Recovery

## Estrategia

Paralelizar diagnóstico (read-only) primero, luego fixes secuenciales por prioridad.

## Fases

### Fase 0 — Diagnóstico paralelo (3 agents simultáneos)

| Agent | Scope | Output |
|-------|-------|--------|
| **A1 — Bot Silence Investigator** | S1: ¿por qué no abre trades desde Apr 22? Revisar logs, scheduler, filtros bloqueantes | `reports/A1-bot-silence.md` |
| **A2 — Scoring Audit** | S2: conf_score=5 → 0% WR. Auditar lógica de scoring en `indicators.py` + `strategies.py` | `reports/A2-scoring-audit.md` |
| **A3 — Symbol Health** | S3/S4/S5: SHORT, TAO, ZEC. Análisis estadístico per-symbol con propuesta de kill/tune | `reports/A3-symbol-health.md` |

Cada agent SOLO investiga (read-only). No edits. Reporta findings + recomendación con diff sugerido.

### Fase 1 — Fixes P0 (después de Fase 0)

Fixes uno por uno, con compile-check + commit chico cada uno:

1. **F1** — Aplicar recomendaciones A1 (desbloquear bot)
2. **F2** — Aplicar recomendaciones A2 (scoring fix o eliminar score=5)
3. **F3** — Aplicar recomendaciones A3 (kill TAO + retunear ZEC + filtrar SHORT)

### Fase 2 — Wiring de gates (P2)

4. **F4** — Wire `DEFENSIVE_SECTORS` + `SECTOR_CLUSTERS` en `strategies.py` y stock pipeline
5. **F5** — Wire `VIX_DORMANT_THRESHOLD` + `SP500_VERDE/NARANJA` regime gate
6. **F6** — Extender `FOMC` suppression a `EARNINGS_SUPPRESS_24H`

### Fase 3 — Niveles watchlist (P3)

7. **F7** — Calcular ATR-based SL/TP/BE para RGTI, CORZ, CIFR, JNJ, KO, CL (script existente `cortex-watchlist`)

### Fase 4 — Verificación

8. **V1** — Smoke test: `python3 -m py_compile` en todos los archivos tocados
9. **V2** — Backtest rápido (si infra existe) en 30d sample
10. **V3** — Deploy a Railway + monitor 72h → confirmar S1 resuelto

## Definition of Done

- Todas las tasks en `tasks.md` marked done
- Bot abre ≥ 1 trade real en 72h
- `git log` muestra commits por síntoma con referencia a spec 001
- `tasks.md` cerrado con métricas finales post-fix
