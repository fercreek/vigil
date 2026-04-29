# TASKS — Gemini Wins
> Fecha: 2026-04-29

## Agent A — Parámetros (Win 1, 2, 3)
- [ ] A1: `_save_memory` línea 122: `context[-60:]` → `context[-20:]`
- [ ] A2: `_chat_with_persona` línea 345: `temperature=0.7` → `temperature=0.4`
- [ ] A3: `get_ai_consensus` línea 267: agregar `max_output_tokens=500`
- [ ] A4: `_chat_with_persona` config: agregar `max_output_tokens=400`
- [ ] A5: `bitlobo_agent.py` calls: agregar `max_output_tokens=300` donde falte
- [ ] A6: `stock_analyzer.py` calls: agregar `max_output_tokens=400`
- [ ] A7: `social_analyzer.py` calls: agregar `max_output_tokens=400`
- [ ] A8: Calls con JSON crítico en `gemini_analyzer.py`: `max_output_tokens=256`
- [ ] A9: Verificar `python -c "import gemini_analyzer"` sin errores

## Agent B — Arquitectura (Win 4, 5)
- [ ] B1: Crear `_gemini_is_available()` helper que encapsula el backoff check
- [ ] B2: Reemplazar checks manuales en `get_ai_consensus` con `_gemini_is_available()`
- [ ] B3: Identificar todas las funciones con `for persona in [...]` + Gemini calls
- [ ] B4: Agregar `if not _gemini_is_available(): return fallback` al inicio de cada una
- [ ] B5: Importar `concurrent.futures` en `gemini_analyzer.py`
- [ ] B6: Crear versión paralela del loop en `get_multi_persona_analysis` con ThreadPoolExecutor(max_workers=4)
- [ ] B7: Verificar que las 4 respuestas retornan correctamente en paralelo
- [ ] B8: Verificar `python -c "import gemini_analyzer"` sin errores

## Agent C — Documentación WA Agent
- [ ] C1: Analizar las 5 reglas del post y adaptarlas a stack n8n + Gemini/Claude
- [ ] C2: Documentar arquitectura de caching en n8n (HTTP Request con headers)
- [ ] C3: Documentar turn counter para flujos WA (max 3 turnos por sesión)
- [ ] C4: Documentar daily spend limits para Claude API en WA agent
- [ ] C5: Documentar model routing (Haiku para classify, Sonnet para respuesta)
- [ ] C6: Documentar ratio monitoring (webhook o log en n8n)
- [ ] C7: Escribir propuesta ejecutiva — "cómo reducir 90% costo agente WA"
- [ ] C8: Output: `context/notes/wa-agent-cost-optimization.md`
