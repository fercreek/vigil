# Spec 011 — Multi-image Input para BitLobo (Gemini multimodal)

> **Status:** CODE COMPLETE 2026-05-26
> **Owner:** Fernando
> **Severity:** P1 — Mes 2 Sem 8 roadmap NotebookLM 4 (anticipado)
> **Origen:** `docs/research/notebook-lm-4/RESULTS.md` Prompt 5 + Prompt 6 Spec 012

## Contexto

`bitlobo_agent.py:analyze_chart` actualmente analiza UNA imagen de gráfica (Gemini Vision). NotebookLM 4 Prompt 5 sugirió aprovechar mejor Gemini Flash 2.5 multimodal — soporta N imágenes en un solo prompt.

Use case real: Fernando envía gráfica de precio + mapa de calor sectorial + gráfico VIX. Hoy son 3 llamadas separadas a Gemini. Con multi-image podemos cruzarlas en una sola call y BitLobo da un panorama integrado.

## Goals

1. Nueva función `analyze_chart_multi(image_paths, symbol, timeframe, extra_context, image_labels)` en `bitlobo_agent.py`.
2. Acepta lista de paths + lista opcional de labels descriptivos.
3. Construye `contents` con N `Part.from_bytes` + 1 `Part.from_text` final.
4. Prompt incluye descripción ordenada de las imágenes con sus labels.
5. Mantener `analyze_chart` (single image) intacto — retrocompatibilidad.

## Non-goals

- Wire en telegram handler para detectar múltiples imágenes consecutivas — Spec 011.5 candidato.
- Cache de imágenes ya enviadas — fuera de scope.
- Soporte otros providers (Claude vision) — solo Gemini Flash 2.5.

## Dependencias

- `bitlobo_agent.py` ✅ existe
- Gemini Flash 2.5 multimodal API ✅ ya usado en `analyze_chart`
- `_load_memory`, `_add_to_memory`, `log_ai_decision` ✅ existen

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Costo de tokens por imagen extra | Cada imagen ~258 tokens Gemini. 3 imágenes ≈ 800 tokens. Negligible vs benefit |
| `image_labels` length mismatch | Validación explícita + early return con error msg |
| max_output_tokens 400 insuficiente para análisis cross-asset | Bumpeo a 600 |
| Imagen mime detection falla | Auto-detect por extensión (.jpg/.jpeg → image/jpeg, else image/png) |

## Criterio de aceptación

1. `python3 -m py_compile bitlobo_agent.py` → OK
2. AST: `analyze_chart_multi` definida + `analyze_chart` sigue presente
3. Smoke con paths inexistentes → return "Faltan imágenes — [...]"
4. Smoke con image_labels mismatch → return error claro
5. Producción pendiente: cuando Fernando envíe múltiples imágenes vía Telegram (handler en Spec 011.5).
