# Plan 005 — Pydantic Structured Output

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Estrategia

Cambio aditivo. Pydantic queda como path primario; parser manual existente queda como fallback legacy. Cero riesgo de regresión — si Pydantic schema falla, el código corre exactamente igual que antes del fix.

## Decisiones técnicas

### 1. SentinelResponse vs SentinelVoices como sub-model

```python
class SentinelVoices(BaseModel):
    genesis: str = "—"
    exodo: str = "—"
    salmos: str = "—"
    apocalipsis: str = "—"

class SentinelResponse(BaseModel):
    bias: Literal["LONG", "SHORT", "NEUTRAL"]
    score: int = Field(ge=0, le=5)
    verdict: Literal["ACUMULAR", "ESPERAR", "REDUCIR"]
    voices: SentinelVoices
    action: str
```

Decisión: voices como sub-model en lugar de `dict[str, str]`. Razón:
- Pydantic + Gemini SDK genera mejor JSON schema cuando hay tipos anidados claros.
- Cada voz tiene `max_length=120` enforceado.
- IDE autocomplete + type hints en el bot.

### 2. Sinónimos en field_validators

`bias` acepta `"bull"`, `"BULLISH"`, `"long"` → normaliza a `"LONG"`. Razón: Gemini Flash 2.5 a veces ignora el Literal y devuelve sinónimos. El validator absorbe la variación sin raise.

`verdict` igual — `"acumular"` lowercase normaliza.

### 3. Default values en lugar de Optional

`voices.genesis = "—"` default en lugar de `Optional[str]`. Razón: el renderer ya espera `dict.get(key, "—")`. Pydantic con default elimina la necesidad de Optional + None handling en el caller.

### 4. `has_real_voices()` method

```python
def has_real_voices(self) -> bool:
    return any(v and v != "—" for v in (self.voices.genesis, ...))
```

Encapsula la regla de Spec 003 fix (`7d306a7`): si todas las voices son placeholder, la alerta es inútil. Caller hace skip.

### 5. `to_renderer_dict()` retrocompatibilidad

`voice_compactor.render_sentinel_compact()` espera dict con shape específico. Pydantic instance no es dict pero `model_dump()` lo cumple. Creé method `to_renderer_dict()` explícito para documentar el contrato.

Alternativa rechazada: cambiar el renderer a aceptar `SentinelResponse`. Razón: aumentaría coupling — el renderer es agnóstico al provider AI. Pydantic en el AI layer, dict en el render layer.

### 6. Fallback dual-layer

```python
if _has_pydantic_schema:
    # Try Pydantic path
    if parsed_obj is not None:
        return parsed_obj.to_renderer_dict()
    # Pydantic falló → fallback al parser manual
parsed = voice_compactor.parse_sentinel_json(raw)
```

Razón: si Pydantic schema validation falla (ej. Gemini devuelve bias inválido que no captura el validator), no perdemos la respuesta — caemos al parser manual que ya tenía 3 niveles de recovery.

### 7. NO migrar otras llamadas Gemini en este spec

`get_weekly_bias`, `get_panorama`, `get_multi_symbol_event` también usan JSON mode. NO se migran en este spec — riesgo de bug si una API call rompe. Spec 005.5 candidato para batch migration cuando este pase QA en producción 1 semana.

## Verificación

Smoke tests pasados:
1. ✅ `python3 -m py_compile gemini_analyzer.py models/sentinel.py voice_compactor.py`
2. ✅ Import: `from models import SentinelResponse` funciona
3. ✅ Default instance: `SentinelResponse()` produce todos placeholders
4. ✅ Real voices: `has_real_voices() == True` con voices no-placeholder
5. ✅ Sinónimo bias: `bias='bull'` → normaliza a `'LONG'`
6. ✅ Validation: `score=10` raise ValidationError
7. ✅ Renderer end-to-end: `render_sentinel_compact()` produce mensaje completo con tags 🎩⚡🌊💀✅

Verificación en producción pendiente (próxima alerta sentinel ZEC).

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(ai): spec-005 Pydantic Structured Output — SentinelResponse model + Gemini response_schema` |

Spec 006 candidato siguiente: Context Caching (Gemini cache system prompt 80% boilerplate).
