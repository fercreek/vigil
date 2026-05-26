# Tasks 011 — Multi-image BitLobo

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26

## Esta sesión

- [x] `bitlobo_agent.analyze_chart_multi(image_paths, symbol, timeframe, extra_context, image_labels)` añadida
- [x] Validación paths inexistentes + image_labels length mismatch
- [x] Auto-detect mime por extensión .jpg/.jpeg → image/jpeg, else image/png
- [x] max_output_tokens 600 vs 400 single
- [x] Memory log con prefix `[MULTI-CHART {N}img]`
- [x] py_compile bitlobo_agent.py OK
- [x] AST: ambas funciones definidas
- [ ] Commit `feat(bitlobo): spec-011 analyze_chart_multi`
- [ ] Push origin/main

## Verificación post-deploy

- [ ] Llamar manualmente con 2 imágenes (precio + sectorial) → response menciona ambas
- [ ] Verificar log `[BITLOBO] multichart_SYMBOL` aparece en `ai_calls` (cuando se llame)
- [ ] Token usage estimado: 800-1000 input + 600 output por multi-call

## Backlog Spec 011.5

- [ ] Telegram handler para múltiples imágenes consecutivas
- [ ] Helper para combinar gráfica del bot + screenshot TradingView
- [ ] Test costo Gemini Flash por imagen real
