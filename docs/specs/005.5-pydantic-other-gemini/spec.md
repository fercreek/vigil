# Spec 005.5 — Pydantic Structured Output para otras llamadas Gemini

> **Status:** CODE COMPLETE 2026-05-26
> **Created:** 2026-05-26
> **Owner:** Fernando
> **Severity:** P1 — quick win, continuación de Spec 005
> **Origen:** Backlog de Spec 005 — "Migrar otras llamadas Gemini" + consistency cross-endpoint

## Contexto

Spec 005 migró `get_sentinel_report_compact` a Pydantic Structured Output (`SentinelResponse`) y validó en producción que `resp.parsed` evita el parseo manual frágil. Tres llamadas Gemini adicionales en `gemini_analyzer.py` siguen usando texto libre + parsing manual:

1. **`get_hourly_panorama`** — 4 personas en paralelo (CONSERVADOR/SCALPER/SALMOS/APOCALIPSIS) responden con formato:
   ```
   BIAS: ALCISTA
   CLAVE: dato relevante
   ACCIÓN: qué hacer
   ```
   Texto libre sin enforcement. Si Gemini omite "CLAVE:" o invierte el orden, el renderer downstream lo muestra deforme.

2. **`get_top_setup`** — multi-symbol event detector. Devuelve `VEREDICTO: LONG [MONEDA]` + bloque entry/SL/TP. (Spec 005.6 candidate — más complejo, requiere schema con discriminator.)

3. **`get_expert_advice`** — análisis Elliott Waves. Texto libre con secciones `ANALISIS ELLIOTT / NIVELES CLAVE / PSICOLOGIA`. (Spec 005.6 candidate.)

Este spec (005.5) ataca **solo Panorama** porque es la llamada más estructurada (3 campos atómicos) y la que más se beneficia del enforcement (4 personas paralelas × parseo manual = 4x superficie de bug).

## Problema raíz

1. **Texto libre fragil:** Gemini Flash 2.5 ocasionalmente omite el prefijo `BIAS:` o lo localiza ("DIRECCIÓN:") rompiendo cualquier parser regex downstream.
2. **Sin Literal enforcement:** un `BIAS: bull` o `BIAS: long` rompe la rama colored downstream — el renderer espera ALCISTA/BAJISTA/NEUTRAL.
3. **Sin max_length:** una persona verbose puede saturar `max_output_tokens=400` antes de llegar a `ACCIÓN:`.
4. **Inconsistencia cross-endpoint:** Sentinel ya usa Pydantic, Panorama no. Mantenimiento divergente.

## Goals

1. Nuevo modelo Pydantic `PanoramaPersonaResponse` en `models/panorama.py`:
   - `bias: Literal["ALCISTA", "BAJISTA", "NEUTRAL"]` con validator para sinónimos (bull/long/etc.).
   - `clave: str` con `max_length=200` + trim.
   - `accion: str` con `max_length=200` + trim.
   - Método `to_telegram_format() -> str` para retrocompat con renderer existente.
   - Método `has_real_content() -> bool` para skip de respuestas vacías (replica patrón Sentinel).

2. Nuevo worker `_call_persona_task_structured` en `gemini_analyzer.py`:
   - Path primario: `response_schema=PanoramaPersonaResponse` via `client.models.generate_content`.
   - Preserva system prompt de la persona + memoria (load/add ctx + log_ai_decision).
   - Fallback graceful: si Pydantic falla o schema no disponible → `_call_persona_task` original (chat + texto libre).

3. Wire en `get_hourly_panorama`: ThreadPoolExecutor submit usa el worker nuevo.

4. `models/__init__.py` re-exporta `PanoramaPersonaResponse`.

## Non-goals

- Migrar `get_top_setup` o `get_expert_advice` (Spec 005.6 candidato — requieren schemas más complejos con conditionals o discriminators).
- Refactor del prompt — Pydantic enforza el shape sin tocar el prompt actual (que ya pide BIAS/CLAVE/ACCIÓN).
- Cambiar la firma de `get_hourly_panorama` — retorna dict[persona_lower → str] exactamente igual.
- Migrar `_chat_with_persona` — sigue siendo el path canónico para conversaciones con history.

## Dependencias

- `pydantic==2.13.3` ✅ ya instalado.
- `google-genai==2.6.0` ✅ soporta `response_schema=BaseModel`.
- `models/sentinel.py` ✅ existente como template.
- `models/panorama.py` — nuevo.
- `gemini_analyzer.py` — modificar `_call_persona_task_structured` (nuevo) + `get_hourly_panorama` (1 línea).

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Gemini ignora `response_schema` cuando hay system_instruction larga | Fallback automático a `_call_persona_task` (chat tradicional) |
| Memoria persona se rompe (load/add ctx side effect) | Replicar manualmente `_add_to_memory` en el path Pydantic |
| Renderer downstream rompe si formato cambia | `to_telegram_format()` produce string idéntico al prompt actual |
| `has_real_content()` false-negativo si modelo solo llenó `clave` | OR lógico: cualquier campo no-placeholder → True |

## Criterio de aceptación

1. `python3 -m py_compile models/panorama.py models/__init__.py gemini_analyzer.py` → OK.
2. `from models import PanoramaPersonaResponse` import OK.
3. Sinónimos: `PanoramaPersonaResponse(bias='bull')` → `bias='ALCISTA'`.
4. Validación: `clave='x' * 250` → ValidationError.
5. Trim: `clave='   '` → `clave='—'` (placeholder).
6. `has_real_content()`: defaults → False; cualquier campo con texto → True.
7. `to_telegram_format()` retorna formato exacto `BIAS: X\nCLAVE: Y\nACCIÓN: Z`.
8. Verificación producción pendiente: próximo Panorama horario muestra 4 voces correctamente formateadas en Telegram (`docs/specs/018-grounded-search-panorama` ya cubre delivery).
