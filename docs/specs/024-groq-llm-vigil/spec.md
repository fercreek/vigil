# Spec 024 — Groq Multi-Provider LLM Vigil + Data Source Hardening

> **Status:** CODE COMPLETE 2026-06-01
> **Owner:** Fernando
> **Severity:** P0 — Sentinel muerto 202min (Gemini free-tier 429 + "voices empty" parse fail)
> **Origen:** Outage en vivo 2026-06-01 (Market Status: "ERROR parse failed / voices empty hace 202min", régimen UNKNOWN)
> **Research:** `apocalipsis/venom/reports/llm-api-comparison-2026-06-01/SYNTHESIS.md`

## Contexto

El 2026-06-01 el Sentinel del bot llevaba ~3.4h sin emitir alertas válidas. Diagnóstico vía Railway logs reveló 3 fallas concurrentes:

1. **Gemini Flash 2.5 429 RESOURCE_EXHAUSTED** — NO spend cap (ai_budget marcaba $0.0004). Era el **free tier 20 req/día/modelo** (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`). La key nueva `AQ.Ab8R…` (sesión 05-31) no tenía billing activado → tope free. Resultado: el social sentinel pedía voices → 429 → voices vacías → `parse failed`.
2. **Binance 451 geo-block** — `indicators.get_rsi` + `get_macro_trend` llamaban a `binance_spot.fetch_ohlcv` DIRECTO, saltando el fallback OKX→KuCoin→Bybit→Binance (Spec dfa68d3). Spam de error `[RSI ERROR] ZEC/15m: binance GET exchangeInfo 451` cada ciclo.
3. **HMM régimen UNKNOWN** — `regime_hmm.detect_regime("ZEC")` (bare symbol, sin slash) ruteaba a yfinance (`Spec 023.5`), que no tiene cripto → `history vacía` → régimen UNKNOWN en ZEC Monitor.

Research paralelo (3 agentes: web + docs oficiales + comunidad) comparó Groq / DeepSeek / OpenRouter / Gemini-paid. Veredicto: **Groq primario** (free tier 14,400 RPD vs 250 de Gemini + JSON constrained decoding que elimina el "voices empty"), **Gemini fallback**. DeepSeek y OpenRouter descartados.

## Goals

### 1. Multi-provider LLM con Groq primario en vigilancia

- **`llm_client.py` nuevo** — cliente Groq vía REST (OpenAI-compat), sin dep nueva (usa `requests`):
  - `groq_text(prompt, system, model, ...)` → (texto, ok). Default `llama-3.1-8b-instant` (free 14,400 RPD).
  - `groq_structured(prompt, pydantic_model, ...)` → (instancia validada, ok). Default `openai/gpt-oss-120b` con `response_format=json_schema strict` (constrained decoding).
  - `_strictify_schema()` — Groq strict exige `additionalProperties:false` + todas las props en `required` en CADA objeto del schema. Pydantic no lo hace; este helper lo inyecta recursivo.
  - `groq_available()` → bool (key presente).
  - Cada llamada se loguea en `ai_budget.log_ai_call(provider="groq", ...)`.

- **Wire `gemini_analyzer.get_sentinel_report_compact`** — Groq primario (structured `SentinelResponse`), Gemini fallback automático abajo si Groq falla o sin voices reales.

- **Wire `social_analyzer._analyze_sentiment_with_gemini`** — Groq primario (texto), Gemini fallback. Gemini client ahora **lazy** (solo se crea en el fallback) → no crashea si falta `GEMINI_API_KEY`, permite fallback real.

### 2. Tracking per-API (monitoreo de uso por proveedor)

- **`ai_budget.COST_PER_TOKEN`** — precios Groq (gpt-oss-120b, llama-3.1-8b, llama-3.3-70b).
- **`ai_budget.get_monthly_cost`** — split per-provider: `groq_usd`, `gemini_usd`, `groq_calls`, `gemini_calls`.
- **`get_budget_summary_html`** (`/budget` Telegram) — línea `Groq ⚡vigil` con calls.
- venom monitorea vía endpoint `/api/ai_budget` (auto-expone los nuevos campos).

### 3. Data source hardening (matar binance 451 + HMM UNKNOWN)

- **`indicators.get_rsi`** → `fetch_ohlcv_with_fallback` (era binance directo).
- **`indicators.get_macro_trend`** (1h/4h/1d) → `fetch_ohlcv_with_fallback`.
- **`regime_hmm.detect_regime`** — cripto-detección robusta: `"/" in symbol` OR `base in config.SYMBOLS`. Normaliza a bare symbol para `get_df` (evita doble-slash). Bare "ZEC" ahora rutea a OKX OHLCV, no yfinance.

### 4. venom al tanto

- `registry/token-inventory.md` — fila scalp_bot Groq (archivo + key name, NUNCA valor).
- `_MONITOR-APIS.md` — sección Groq (costo/límites/decisión/descartados).
- Reporte research completo en `reports/llm-api-comparison-2026-06-01/`.

## Non-goals

- **Groq como ÚNICO proveedor** — Gemini queda como fallback (resiliencia multi-provider). Decisión B: Groq primario, NO reemplazo total.
- **Activar billing Gemini** — opcional; el fallback ya no depende de Gemini para el path feliz. Pendiente Fernando si quiere subir el cap.
- **Stagger de llamadas para TPM** — free tier TPM (6k llama / 8k gpt-oss) se topa en burst → cae a Gemini graceful. Solo se bajó `max_tokens` sentinel 2500→1200. Stagger queda backlog.
- **Claude provider** — SDK no instalado, $0. No se toca.

## Criterios de aceptación

| # | Criterio | Estado |
|---|----------|--------|
| 1 | Groq key válida, modelos gpt-oss-120b + llama-3.1-8b disponibles | ✅ probado |
| 2 | `groq_structured` retorna `SentinelResponse` con voices reales | ✅ probado local |
| 3 | Sentinel + social usan Groq primario en prod, fallback Gemini en TPM 429 | ✅ logs prod 22:52 |
| 4 | `ai_budget` split per-provider visible en `/budget` | ✅ probado |
| 5 | `get_rsi('ZEC','15m')` sin binance 451 | ✅ probado (RSI 48.0) |
| 6 | `get_df('ZEC')` retorna velas (HMM data fix) | ✅ 60 velas, $547.67 |
| 7 | HMM ZEC régimen ≠ UNKNOWN en prod | ⏳ validar post-redeploy (requiere hmmlearn Railway) |
| 8 | venom registry + monitor actualizados | ✅ |

## Riesgos / notas

- **Groq free TPM burst**: con todos los símbolos a la vez se topa TPM → fallback Gemini. Carga ahora se reparte entre 2 providers = más resiliente, ningún cap diario se agota. Si Groq pasa a primario duro, considerar stagger o billing Groq ($0.05/$0.08 por 1M, barato).
- **Doble-slash latente**: el fix de `regime_hmm` también corrige un bug potencial donde "BTC/USDT" → get_df → fetch construía "BTC/USDT/USDT". Ahora normaliza a base.
