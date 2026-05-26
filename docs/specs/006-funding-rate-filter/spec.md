# Spec 006 — Funding Rate Filter para V3-Reversal

> **Status:** IN PROGRESS 2026-05-26
> **Created:** 2026-05-26
> **Owner:** Fernando
> **Severity:** P0 — quick win Mes 1 Semana 3 (anticipado a sem 1) del roadmap NotebookLM 4
> **Origen:** `docs/research/notebook-lm-4/RESULTS.md` Prompt 1 top 1 + Prompt 3

## Contexto

NotebookLM 4 análisis identificó Funding Rate Filter como **TOP 1 quick win** — complejidad 1, $0, integra en Apocalipsis. Recomendación: "Si funding rate annualized > 10% persistente, viene latigazo de volatilidad — bloquear V3-REVERSAL".

Bot ya tiene `market_intel.get_funding_rates()` operativo (cache 5min, devuelve `annualized` %). Falta gate global que use ese signal contra V3-REVERSAL.

Nota técnica: Spec 006 originalmente era "Context Caching Gemini". Medición del prompt actual (277 tokens) confirma que NO califica para Gemini caching (mínimo 4096 tokens). Caching defer al backlog; Spec 006 ahora = Funding Rate Filter.

## Goals

1. `FUNDING_REVERSAL_BLOCK_ANNUALIZED = 30.0` en config.py — threshold conservador (NotebookLM dijo 10%, bumpeamos a 30% para no killear todas las alerts hasta validar; documentado en plan.md).
2. Gate en `strategies.py:V3-REVERSAL` (line ~497): si `funding annualized > threshold`, log + `continue`.
3. Logear el evento con clear cause-reason (debug visible para tuning del threshold).
4. NO afectar V2-AI, V4, SWING, COMMODITY (solo V3-REVERSAL — la más sensible a latigazos según research).

## Non-goals

- Wire funding context en voz Apocalipsis del Sentinel Compact — Spec 006.5 candidato (requiere extender el prompt + tests).
- Cambiar `FUNDING_EXTREME_LONG/SHORT` existentes (usados en `get_funding_signal` contrarian) — esos siguen su propósito.
- Funding rate gate en V4/SWING — research específico era para V3 reversals.
- Multi-exchange funding (Binance only por ahora).

## Dependencias

- `market_intel.get_funding_rates()` ✅ ya existe
- `config.py:FUNDING_EXTREME_LONG` ya existe (no se toca)
- `strategies.py:check_strategies()` line 497 — modificar

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Threshold 30% kills demasiadas alerts → bot deja de alertar V3 | Logs del bloqueo permiten tuning. Si 7 días bloquea >50% alerts V3, bajar a 50%. |
| Threshold 30% es muy permisivo → no protege como NotebookLM esperaba | Empezar conservador (30) y bajar a 10 después de 1 sem en producción. |
| Funding rate cache 5min puede no reflejar spikes súbitos | Cache TTL existente OK — funding cambia c/8h Binance, 5min suficiente. |
| `funding_data` puede no estar pasado al loop V3 | Verificar que se inyecta correctamente (fallback fetch local si None). |

## Criterio de aceptación

1. `python3 -m py_compile config.py strategies.py` → OK
2. Constante `FUNDING_REVERSAL_BLOCK_ANNUALIZED` importable
3. Smoke test: simular funding_data con annualized=35% → V3 trigger NO se envía + log visible
4. Smoke test: simular funding_data con annualized=15% → V3 trigger SÍ se envía normal
5. Production deploy: NYSE/cripto sessions siguientes, verificar logs `[V3-Reversal] funding ... bloqueando`
