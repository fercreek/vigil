# SPEC — Gemini Optimization Wins (5 mejoras)
> Fecha: 2026-04-29 · Repo: scalp_bot · Stack: Python + Gemini 2.5 Flash

## Problema
Bot usa Gemini 2.5 Flash para todas las llamadas de IA (Claude key vacía).
5 problemas identificados que afectan velocidad, calidad de señales y confiabilidad.

## Objetivo
Reducir latencia, mejorar consistencia de decisiones de trading, y prevenir
fallos en cascada — sin cambiar el modelo ni el costo.

## Archivos principales
- `gemini_analyzer.py` — hub central (1,241 líneas), todos los calls Gemini
- `ai_budget.py` — tracking de costo/tokens

## Las 5 mejoras

### Win 1 — Temperature 0.7 → 0.4 en `_chat_with_persona`
**Archivo:** `gemini_analyzer.py:334`
**Problema:** `temperature=0.7` genera respuestas variables/"creativas" para decisiones financieras.
**Fix:** Cambiar a `0.4` en el `GenerateContentConfig` dentro de `_chat_with_persona`.
**Riesgo:** Ninguno. Solo hace las respuestas más deterministas.

### Win 2 — Memoria cortada a 20 entradas en `_save_memory`
**Archivo:** `gemini_analyzer.py:122`
**Problema:** `context[-60:]` guarda 60 entradas ≈ 6,000 tokens de historial inyectado en cada llamada.
**Fix:** Cambiar `context[-60:]` → `context[-20:]` en `_save_memory`.
**Riesgo:** Ninguno. Últimas 20 interacciones son suficientes para contexto intradiario.

### Win 3 — `max_output_tokens` en todas las calls sin límite
**Archivo:** `gemini_analyzer.py` (múltiples llamadas), `bitlobo_agent.py`, `stock_analyzer.py`, `social_analyzer.py`
**Problema:** Varios `generate_content` sin `max_output_tokens`. Gemini puede generar 2,000+ tokens innecesarios.
**Fix por tipo de call:**
| Tipo | `max_output_tokens` recomendado |
|------|---------------------------------|
| Decisión JSON crítica | 256 |
| Análisis de persona (chat) | 400 |
| Consenso 4 voces | 500 |
| Reporte institucional | 600 |
| Análisis técnico detallado | 800 |
**Riesgo:** Bajo. Verificar que las respuestas no se corten abruptamente. Ajustar si es necesario.

### Win 4 — `get_multi_persona_analysis` 4 calls → 1 call
**Archivo:** `gemini_analyzer.py:531-568`
**Problema:** Loop `for persona in [4 personas]` llama `_chat_with_persona` 4 veces en secuencia.
`get_ai_consensus` ya genera las 4 voces en 1 sola llamada — mismo patrón.
**Fix:** Crear función `_get_all_personas_single_call(prompt, context_data)` que genera
las 4 respuestas en un solo `generate_content` con system_instruction consolidado.
**Riesgo:** Medio. Las 4 personas pierden su historial individual de contexto.
Mitigación: inyectar el contexto relevante del día en el prompt único.

### Win 5 — Circuit breaker en loop de 4 personas
**Archivo:** `gemini_analyzer.py` — cualquier función con `for persona in [...]`
**Problema:** Si Gemini está caído, el loop falla 4 veces en lugar de 1.
**Fix:** Verificar `_gemini_backoff_until` al inicio de las funciones que usan el loop.
Mismo patrón que `get_ai_consensus` (línea 225-228).
**Riesgo:** Ninguno. Pure defensive check.

## Criterios de aceptación
- [ ] Win 1: `temperature=0.4` en `_chat_with_persona`, ningún otro call afectado
- [ ] Win 2: `context[-20:]` en `_save_memory`, archivos .json de memoria siguen funcionando
- [ ] Win 3: `max_output_tokens` en todas las calls, sin truncamiento de JSON crítico
- [ ] Win 4: `get_multi_persona_analysis` retorna las 4 respuestas en ≤1 Gemini call
- [ ] Win 5: Circuit breaker activo en todas las funciones con loop de personas
- [ ] `python -c "import gemini_analyzer"` sin errores después de cada cambio
