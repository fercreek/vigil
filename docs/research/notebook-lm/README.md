# NotebookLM Research Pipeline

> **Patrón:** delegar análisis intensivo de fuentes a NotebookLM. Claude scout + integra. Fernando upload + ejecuta prompts + paste back.

## Flujo

```
[Fuentes en repo]  ──→  [pts-watchlist-corpus.md]  ──→  NotebookLM (web)
                                                            │
                                                            ▼
                                                       [Prompts]
                                                            │
                                                            ▼
                          [RESULTS.md] ◄─── Fernando paste back
                              │
                              ▼
                       Claude integra ──→  config.py / CLAUDE.md / spec 004
```

## Notebooks planeados

| # | Notebook | Status | Folder |
|---|----------|--------|--------|
| 1 | PTS Watchlist Deep Dive | 🟡 corpus listo, prompts listos, pending Fernando | `./` |
| 2 | Catalyst Calendar 26-30 May | 📋 planeado | TBD |
| 3 | Bot Performance Audit | 📋 planeado | TBD |

## Archivos de notebook 1

- `pts-watchlist-corpus.md` — corpus (688 líneas). **Subir a NotebookLM como source.**
- `PROMPTS.md` — 7 prompts a correr en orden.
- `RESULTS.md` — template para pegar outputs.
- `README.md` — este archivo.

## Pasos Fernando — Notebook 1

1. Abrir https://notebooklm.google.com
2. Click "New notebook" → nombre: "PTS Watchlist Deep Dive"
3. Sources → "Upload source" → seleccionar `pts-watchlist-corpus.md`
4. Abrir `PROMPTS.md` en este repo
5. Copiar Prompt 1 → pegar en chat NotebookLM → run
6. Output → copiar → pegar en `RESULTS.md` debajo de "Prompt 1"
7. Repetir Prompts 2-6 (Prompt 7 audio es opcional)
8. Cuando todo esté pegado → en Claude Code: "listo, pegué resultados NotebookLM"

## Tiempo estimado

- Setup notebook + upload: 2 min
- Prompts 1-6: 3-5 min cada uno (NotebookLM tarda ~1 min/prompt + lectura)
- Total: 25-40 min

## Por qué NotebookLM y no agente Claude

| Criterio | NotebookLM | Claude Agent |
|----------|-----------|--------------|
| Corpus grande (>50k tokens) | ✅ usa retrieval automático | ⚠️ context window cuesta |
| Citaciones a fuentes | ✅ link a sección exacta | ✅ pero menos visual |
| Audio Overview | ✅ único | ❌ no nativo |
| Iteración rápida | ✅ chat persistente | ⚠️ requiere relanzar contexto |
| Integración automática a código | ❌ output manual | ✅ Edit/Write directo |
| Costo | 🆓 (Google account) | 💰 API tokens |

**Conclusión:** NotebookLM mejor para análisis exploratorio de corpus grande. Claude mejor para integrar findings a código. Combinarlos = mejor de ambos.

## Mantenimiento

- Cada vez que Daniel Marin publique reporte nuevo → agregarlo a CLAUDE.md sección 8X siguiente.
- Re-correr `sed -n '143,XXXp' CLAUDE.md > pts-watchlist-corpus.md` para refrescar corpus.
- Re-subir corpus actualizado a NotebookLM (o agregar reporte como source separado).
- Re-correr prompts cada lunes pre-apertura o cuando régimen cambie.
