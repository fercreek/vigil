# PLAN — Gemini Optimization Wins
> Fecha: 2026-04-29

## Decisiones de arquitectura

### Win 1+2+3: Cambios de parámetros (bajo riesgo)
Ediciones quirúrgicas en funciones existentes. No hay cambio de interfaz pública.
Orden: Win 2 primero (más simple), luego Win 1, luego Win 3 (más llamadas).

### Win 4: Consolidación 4 calls → 1
Opción A: Nueva función `get_multi_persona_single_call()` que reemplaza el loop.
  ↳ PRO: Limpio, testeable, no rompe nada.
  ↳ CON: Las 4 personas pierden historial individual.
Opción B: Paralelizar las 4 llamadas con `concurrent.futures.ThreadPoolExecutor`.
  ↳ PRO: Mantiene historial individual, 4x más rápido que secuencial.
  ↳ CON: Más código, posible rate limiting de Gemini free tier.

**Decisión: Opción B** (ThreadPoolExecutor) — mantiene calidad de señales con historial,
y evita el problema de contexto perdido. Max 4 workers concurrentes.

### Win 5: Circuit breaker pattern
Extraer check `_gemini_backoff_until` a función helper `_gemini_is_available()`.
Reusar en todas las funciones que hacen loops de personas.

## Orden de implementación
1. Win 2 (memory trim) — 1 línea
2. Win 1 (temperature) — 1 línea
3. Win 5 (circuit breaker helper) — función nueva + checks
4. Win 3 (max_output_tokens) — recorrer todas las calls
5. Win 4 (ThreadPoolExecutor) — más complejo, al final

## Tests de verificación
```bash
cd ~/Documents/ideas/scalp_bot
./venv/bin/python -c "import gemini_analyzer; print('import OK')"
./venv/bin/python -c "from gemini_analyzer import _save_memory, _load_memory; _save_memory('TEST', []); print('memory OK')"
./venv/bin/python -c "from gemini_analyzer import _gemini_is_available; print('cb OK:', _gemini_is_available())"
```
