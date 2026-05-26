# NotebookLM 4 — Trading Strategies Research

> **Diferencia con notebooks 1-3:**
> - Notebook 1 = PTS corpus análisis (curated source)
> - Notebook 3 = Bot performance audit (DB local)
> - Notebook 4 = **investigación externa** — qué SUMAR al bot
>
> Usa la feature **Discover Sources** de NotebookLM (botón en sidebar de fuentes) para que NotebookLM busque papers/artículos/blogs externos por topic.

## Status

🟡 Corpus + prompts listos · pending Fernando upload + Discover + run

## Archivos

- `bot-capabilities-corpus.md` — 295 líneas. Inventario completo de lo que tiene el bot HOY + lista explícita de gaps (lo que NO tiene).
- `PROMPTS.md` — 6 prompts (top 5 estrategias, SMC, on-chain, market regime ML, mejor uso Gemini, roadmap 90 días).
- `RESULTS.md` — template.
- `README.md` — este archivo.

## Pasos Fernando

1. Abrir https://notebooklm.google.com
2. New notebook → "Trading Strategies Research"
3. Sources → Upload `bot-capabilities-corpus.md`
4. Sources → **Discover** → buscar y agregar:
   - "quantitative trading strategies retail crypto"
   - "smart money concepts SMC trading"
   - "AI agent trading strategy backtesting"
   - "options flow unusual activity bot"
   - "on-chain analysis bitcoin signals"
   - "market regime detection machine learning"
5. NotebookLM seleccionará 5-15 sources confiables — confirmar.
6. Abrir `PROMPTS.md`, copiar Prompt 1, ejecutar en chat NotebookLM.
7. Output → `RESULTS.md` sección correspondiente.
8. Repetir Prompts 2-6.
9. Avisar a Claude: "listo notebook 4, pegué resultados".

## Tiempo estimado

- Setup + Discover: 5-10 min (NotebookLM tarda en encontrar sources)
- Prompts 1-6: 5-8 min cada uno (más sources = más tiempo de análisis)
- Total: 35-60 min

## Por qué este notebook es diferente

Los notebooks 1-3 tienen corpus cerrado (PTS reports, DB trades). Notebook 4 necesita conocimiento EXTERNO (academia, comunidad quant, open-source).

NotebookLM tiene 2 ventajas para este caso:
1. **Discover** trae fuentes verificables (no inventa).
2. **Citaciones** — cada claim queda atado a una fuente específica.

Sin Discover, NotebookLM solo usaría training data interno = riesgo de alucinaciones.

## Output esperado

Roadmap 90 días con:
- Mes 1: 4 quick wins implementables (días, costo $0)
- Mes 2: 4 cambios estructurales (semanas, costo bajo)
- Mes 3: 4 features de aprendizaje (más complejo)

Cada item → Spec X candidato. Yo (Claude) cruzo con Spec 004 backlog actual y armo specs en sesiones siguientes.

## Mantenimiento

Re-correr cada quarter (3 meses) — refresca research con sources nuevos. Constants del bot mismo (capabilities) cambian → re-generar corpus.
