# Groq TPM stagger — análisis (FOCUS-228)
> 2026-06-06 · análisis, NO se tocó prod. Propuesta para revisar con Fernando.

## Hallazgo

La ráfaga de TPM NO viene del loop normal (los `for s in SYMBOLS` en `app.py` son secuenciales → 1 llamada a la vez, no topan).

**La fuente real de concurrencia:** `gemini_analyzer.py:707` →
```python
with ThreadPoolExecutor(max_workers=4) as executor:   # 4 símbolos en paralelo
```
Cuando ese batch enruta a Groq (vía `llm_client.groq_text`), son **hasta 4 llamadas concurrentes** → suma de tokens/min de los 4 prompts a la vez puede topar el free tier Groq (6k-8k TPM), disparando 429.

`llm_client._post` es `requests` síncrono sin throttle global → no hay nada que limite el burst cuando lo llaman 4 hilos.

## Propuesta (a revisar — NO aplicada)

Opción mínima (1 línea, menor riesgo): bajar `max_workers=4 → 2` en `gemini_analyzer.py:707`. Mitad de burst, casi mismo wall-time (las llamadas LLM no son el cuello).

Opción robusta: token-bucket global en `llm_client` (un `threading.Semaphore` + sleep entre llamadas Groq) para que aunque N hilos llamen, el ritmo a Groq se mantenga < TPM. ~15 líneas, centralizado.

⭐ Recomiendo empezar por la mínima (max_workers=2) + medir 429 antes de meter el semáforo. Verificar contigo antes de tocar (es bot vivo).
```
