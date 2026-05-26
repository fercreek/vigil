# Plan 011 — Multi-image BitLobo

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Decisiones técnicas

### 1. Nueva función vs modificar analyze_chart

Nueva función `analyze_chart_multi`. Razón:
- `analyze_chart` (single-image) tiene caller en telegram handler — no romper
- API distinta (list[str] vs str) — más limpio separar
- Spec 011.5 wireará al handler para decidir cuándo usar single vs multi

### 2. Construcción de contents multimodal

```python
contents = []
for path in image_paths:
    with open(path, "rb") as f:
        img_bytes = f.read()
    ext = path.lower().split(".")[-1]
    mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
    contents.append(types.Part.from_bytes(data=img_bytes, mime_type=mime))
contents.append(types.Part.from_text(text=prompt))
```

Orden importa: imágenes primero, prompt al final. Gemini analiza en orden de Parts.

### 3. image_labels opcional con validación

Si None → labels genéricos "Imagen 1", "Imagen 2", ...
Si list → validar length matches image_paths o early return error.

Razón: permite uso simple (sin labels) + uso experto (labels específicos).

### 4. max_output_tokens 600 vs 400 single

Más imágenes = más contexto = response más rica. 600 da margen para análisis cross-asset.

### 5. Memory log con prefix "[MULTI-CHART {N}img]"

Distingue en memoria entre single-chart y multi-chart calls, útil para audit posterior.

## Verificación

- ✅ py_compile bitlobo_agent.py
- ✅ AST: analyze_chart_multi + analyze_chart ambos definidos

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(bitlobo): spec-011 analyze_chart_multi — Gemini multimodal N imágenes` |

## Backlog Spec 011.5

- Wire en `telegram_commands.py`: si usuario envía N imágenes consecutivas + `/bitlobo SYM`, batch en multi call
- Aprovechar: pasar gráfica del bot Python + screenshot TradingView simultáneo
- Test costo real: medir tokens consumidos por imagen en producción
