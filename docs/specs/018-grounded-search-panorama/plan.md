# Plan 018 — Grounded Search en Panorama

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Decisiones técnicas

### 1. Wire en panorama, NO en sentinel

Sentinel Compact frecuencia alta (configurable, típicamente cada 5-15min). Si grounded en cada uno → cap 5/día se gasta en horas.

Panorama c/2h = 12 calls/día. Con cache 1h interno = 1 query real/día. Sustainable.

### 2. Query genérica única

```python
query = ("latest macro news today: FOMC decision rate, US inflation CPI, "
         "geopolitical risk affecting crypto and S&P 500. Resumen 4 oraciones.")
```

Razón:
- 1 query cubre todos los topics relevantes para las 4 voces
- Cache hit perfectamente — misma query cada panorama call
- Daily counter incrementa solo 1x (al primer query del día)

Alternativa rechazada: query por símbolo (5x queries × 12 panoramas = 60/día = exceede cap)

### 3. Bloque inyectado a TODAS las personas, no solo Apocalipsis

`get_hourly_panorama` envía el mismo `prompt` a las 4 personas vía ThreadPoolExecutor. Modificar el prompt = todas reciben.

Razón:
- Coherencia narrativa: si Apocalipsis dice "Fed hawkish hoy", Salmos y otros deberían saberlo
- Cero query extra
- Cada persona usa el macro en su perspectiva (Apocalipsis = riesgo, Scalper = volatility implications, Conservador = thesis structural)

### 4. Try/except graceful

```python
try:
    import grounded_search as _gs
    _news = _gs.query_grounded_search(...)
    if _news:
        macro_news_block = f"\n📡 MACRO NEWS HOY (grounded search):\n{_news}\n"
except Exception:
    pass
```

Si:
- `grounded_search` no importable → bloque vacío
- API key falta → returna None → bloque vacío
- Cap exhausted → None → bloque vacío
- Query falla → None → bloque vacío

Cero crash. Cero degradación del panorama existente.

### 5. Header explícito en el bloque

```
📡 MACRO NEWS HOY (grounded search):
[texto del modelo con citaciones]
```

`(grounded search)` marca a las voces que el dato viene de búsqueda web — más reciente que `FOMC_CONTEXT` hardcoded.

### 6. Cap diario 5 sigue siendo de protección

Aunque solo necesitamos 1 query/day de panorama, cap 5 reserva margen para futuros wires (Spec 014.5+ telegram /news comando, etc).

## Verificación

- ✅ py_compile gemini_analyzer.py
- ✅ grounded_search funciona end-to-end (test devolvió respuesta + incrementó counter 1/5)
- ✅ Bloque MACRO NEWS se inyecta solo si query retorna texto
- ✅ Graceful fallback sin API key / cap exhausted

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(macro): spec-018 grounded search en panorama — Apocalipsis macro real` |

## Tuning post-7d

- Verificar Railway logs: `grep "grounded_search" → contar queries reales/día`
- Si 1/day exactamente → perfecto
- Si >1/day → cache hit ratio bajo, investigar
- Si 0/day → cap exhausted o panorama no corre, investigar

## Backlog Spec 018.5

- Persist daily counter SQLite (sobrevive restart Railway)
- A/B test: medir si voces refieren al MACRO NEWS block
- Query parametrizable por hour (mañana macro EU, tarde US, noche Asia)
- Telegram `/news QUERY` con cap separado del panorama
