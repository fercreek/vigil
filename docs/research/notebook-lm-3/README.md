# NotebookLM 3 — Bot Performance Audit

> **Patrón:** validación empírica de constantes del bot con datos reales de trades.db.
> Complemento del Notebook 1 (PTS Watchlist).

## Status

🟡 Corpus + prompts listos · pending Fernando upload + run

## Archivos

- `performance-audit-corpus.md` — 148 líneas. Snapshot trades.db local 2026-05-26. Cubre periodo 2026-03-30 → 2026-04-22 (91 trades + 39 episodes).
- `PROMPTS.md` — 6 prompts (kill switches audit, conf_score paradox, huérfanas, direction bias, cross-ref PTS, plan acción).
- `RESULTS.md` — template + findings inmediatos sin NotebookLM.
- `README.md` — este archivo.

## Caveat importante

La DB local es snapshot de Abr 22. NO tiene:
- Trades post Spec 002/003/004 (May-23 onwards).
- Resultados de yfinance fallback aplicado retroactivamente.
- Constantes Spec 003+004 reflejadas en trade outcomes.

Para análisis vivo: extraer DB de Railway primero. Ver `Refresh corpus` abajo.

## Refresh corpus desde Railway

```bash
# 1. Backup DB local
cp trades.db trades.db.bak_$(date +%Y%m%d)

# 2. Download DB de Railway (cuando esté disponible)
# Opción A: railway run python -c "..." (corre código en producción)
# Opción B: SSH a Railway container (requiere setup)
# Opción C: railway logs + parse output (limitado)

# 3. Re-generar corpus
cd /Users/fernandocastaneda/Documents/ideas/scalp_bot
python3 scripts/generate_audit_corpus.py  # TODO crear script

# 4. Re-upload a NotebookLM Notebook 3 (remove old source, add new)
```

## Tiempo estimado

- Setup notebook + upload: 2 min
- Prompts 1-6: 4-7 min cada uno (algunos son cross-reference complejos)
- Total: 30-45 min

## Por qué NotebookLM aquí

Datos tabulares (trades.db) → análisis cualitativo de patrones + hipótesis investigativas. NotebookLM:
- Citado por sección del corpus.
- Permite preguntas follow-up.
- Audio Overview puede explicar la paradoja conf_score conversacionalmente.

Alternativa Claude: requeriría inyectar 5k+ tokens de tabla en cada query, mientras NotebookLM lo retrieva.
