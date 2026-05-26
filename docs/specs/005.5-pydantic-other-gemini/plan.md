# Plan 005.5 — Pydantic Structured Output para Panorama

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Estrategia

Cambio aditivo y graceful. El worker viejo `_call_persona_task` permanece intacto. Un nuevo worker `_call_persona_task_structured` intenta primero el path Pydantic y delega al viejo en cualquier error. `get_hourly_panorama` cambia solo 1 línea (la función que submitea al executor).

## Decisiones técnicas

### 1. Sub-model vs flat schema

Decisión: `PanoramaPersonaResponse` es **flat** (3 campos atómicos: bias / clave / accion). Razón:
- A diferencia de Sentinel (que tiene 4 voces que el modelo a veces deja vacías) cada persona del Panorama es 1 unidad lógica.
- Flat reduce profundidad del JSON schema enviado a Gemini → menos overhead y menos chance de truncación.

### 2. Sinónimos en `bias`

Gemini Flash 2.5 ocasionalmente devuelve `bull` / `bullish` / `long` en lugar de `ALCISTA`. El `field_validator(mode='before')` normaliza estos sinónimos antes de que el Literal valide. Cualquier valor no reconocido → `NEUTRAL` (en lugar de raise). Esto evita perder la respuesta entera por una palabra mal escogida.

Tabla:
| Input | Output |
|-------|--------|
| `bull` / `bullish` / `long` / `alcista` (case-insensitive) | `ALCISTA` |
| `bear` / `bearish` / `short` / `bajista` | `BAJISTA` |
| `neutral` / `lateral` / `range` / `rango` | `NEUTRAL` |
| cualquier otra cosa | `NEUTRAL` (default) |

### 3. Trim + placeholder en `clave` / `accion`

`field_validator(mode='before')` aplica:
- `None` → `"—"`
- `"  "` (whitespace only) → `"—"`
- `"  texto  "` → `"texto"`

Mantiene el contrato del renderer downstream (placeholder em-dash es señal de "campo vacío" en todo el bot).

### 4. `to_telegram_format()` retrocompat

`get_hourly_panorama` concatena emoji + nombre persona delante del bloque BIAS/CLAVE/ACCIÓN:
```python
results[persona.lower()] = f"{info['emoji']} <b>{info['name']}</b>\n\n{answer}"
```

`answer` viene como string. `to_telegram_format()` produce exactamente `"BIAS: X\nCLAVE: Y\nACCIÓN: Z"` que es lo que el prompt actual pide → cero cambios downstream.

### 5. Path dual con fallback

```python
def _call_persona_task_structured(...):
    try:
        from models import PanoramaPersonaResponse
    except ImportError:
        return _call_persona_task(...)  # fallback

    if not client:
        return _call_persona_task(...)

    try:
        resp = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=GenerateContentConfig(
                system_instruction=PERSONAS[persona]['system'],
                response_schema=PanoramaPersonaResponse,
                ...
            ),
        )
        parsed = getattr(resp, 'parsed', None)
        if parsed and parsed.has_real_content():
            # replica memoria de _chat_with_persona side-effect
            return persona, parsed.to_telegram_format()
    except Exception:
        pass

    return _call_persona_task(...)  # fallback
```

Razón: Pydantic primary, chat fallback. Zero risk de regresión — si todo falla, el comportamiento es idéntico a antes.

### 6. Memoria persona preservada

`_chat_with_persona` tiene side-effect de cargar/guardar memoria (`_load_memory`, `_add_to_memory`, `log_ai_decision`). El path Pydantic replica esto manualmente con try/except — si falla la memoria, no aborta la respuesta (log warning y sigue).

### 7. NO migrar `get_top_setup` en este spec

`get_top_setup` retorna texto narrativo con bloque entry/SL/TP. Para Pydantic necesitaría:
- `verdict: Literal["LONG", "SHORT", "ESPERAR"]`
- `symbol: str | None` (solo si LONG/SHORT)
- `entry: float | None`, `sl: float | None`, `tp1: float | None`, `tp2: float | None`
- `racional: list[str]` con max 3 items
- `tamaño: Literal["Mini", "Normal"]`

Es factible pero requiere conditional fields (entry obligatorio solo si verdict != ESPERAR). Mejor en Spec 005.6 dedicado donde podamos testear el discriminator.

## Verificación

Smoke tests pasados (8 tests):
1. ✅ `py_compile` panorama.py + __init__.py + gemini_analyzer.py
2. ✅ Import `from models import PanoramaPersonaResponse`
3. ✅ Canonical: bias=ALCISTA → output formato correcto
4. ✅ Sinónimo bull → ALCISTA normalizado
5. ✅ Sinónimos bear/BEARISH/short/BAJISTA → BAJISTA
6. ✅ Bias inválido → fallback NEUTRAL
7. ✅ `max_length=200` enforced (ValidationError raised)
8. ✅ Trim whitespace + placeholder cuando vacío
9. ✅ `has_real_content()` correcto para defaults (False) y reales (True)

Verificación producción pendiente: próximo ciclo de Panorama horario.

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(ai): spec-005.5 Pydantic Panorama — PanoramaPersonaResponse + structured worker` |

Spec siguiente candidato: **005.6** — Pydantic para `get_top_setup` + `get_expert_advice` (requiere schemas con conditional fields).
