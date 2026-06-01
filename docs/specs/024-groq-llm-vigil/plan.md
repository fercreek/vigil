# Plan — Spec 024 Groq LLM Vigil + Data Hardening

> Status: EXECUTED 2026-06-01

## Secuencia ejecutada

1. **Diagnóstico (ground-truth vivo)**
   - `/api/ai_budget` → confirmó NO spend cap ($0.0004, 3 calls). Gemini respondía.
   - `railway logs` → reveló 3 fallas: Gemini 429 free-tier 20/día, binance 451 en RSI, HMM yfinance vacío ZEC.

2. **Research paralelo** (skill `parallel-research`, 3 agentes bg)
   - web + docs oficiales + comunidad → `venom/reports/llm-api-comparison-2026-06-01/SYNTHESIS.md`
   - Conflicto web (Gemini primario) vs comunidad (Groq primario) → resuelto a Groq (community documentó el bug JSON de Gemini = el outage real).

3. **Registro venom** — token-inventory + _MONITOR-APIS + key en `.env` (gitignored).

4. **Build LLM layer**
   - `ai_budget.py` — precios Groq + split per-provider + `/budget` línea Groq.
   - `llm_client.py` — Groq REST, structured + text, `_strictify_schema`.
   - Probar key + structured `SentinelResponse` (voices reales).

5. **Wire (decisión B: Groq primario vigilancia)**
   - `gemini_analyzer.get_sentinel_report_compact` — Groq primario, Gemini fallback.
   - `social_analyzer` — Groq primario, Gemini lazy fallback.
   - Probar en vivo (social score 0.8, voices OK).

6. **Deploy** — Railway env var `GROQ_API_KEY` (Fernando) + commit `80e6097` + push → redeploy. Confirmado en logs 22:52: Groq OK primario.

7. **TPM optimization** — `max_tokens` sentinel 2500→1200 (commit `546306d`).

8. **Data hardening (#2 + #3)**
   - `indicators.get_rsi` + `get_macro_trend` → `fetch_ohlcv_with_fallback`.
   - `regime_hmm.detect_regime` → cripto-detección por config.SYMBOLS + bare normalize.
   - Probar con venv (RSI 48.0, get_df 60 velas). Commit `629eb2f` + push.

## Archivos tocados

| Archivo | Cambio |
|---------|--------|
| `llm_client.py` | NUEVO — cliente Groq multi-modelo |
| `ai_budget.py` | precios Groq + split per-provider + summary |
| `gemini_analyzer.py` | sentinel compact Groq primario |
| `social_analyzer.py` | social Groq primario + Gemini lazy |
| `indicators.py` | get_rsi + get_macro_trend → fallback |
| `regime_hmm.py` | cripto-detección robusta |
| `.env` | `GROQ_API_KEY` (gitignored) |
| venom `registry/token-inventory.md` | fila scalp_bot Groq |
| venom `_MONITOR-APIS.md` | sección Groq |

## Commits

- `80e6097` feat(llm): Groq primary for vigilance loop, Gemini fallback
- `546306d` perf(llm): lower Groq sentinel max_tokens 2500→1200
- `629eb2f` fix(data): route get_rsi/macro_trend + HMM crypto via OKX fallback
