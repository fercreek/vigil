# Tasks — Spec 024 Groq LLM Vigil + Data Hardening

## ✅ Hecho (2026-06-01)

- [x] Diagnóstico outage: 429 free-tier + binance 451 + HMM yfinance vacío
- [x] Research paralelo 4 APIs → SYNTHESIS (venom/reports)
- [x] venom registry: token-inventory + _MONITOR-APIS + key en .env
- [x] `ai_budget`: precios Groq + split per-provider (groq_usd/calls) + /budget línea
- [x] `llm_client.py`: groq_text + groq_structured + _strictify_schema
- [x] Probar key Groq + structured SentinelResponse (voices reales)
- [x] Wire sentinel compact: Groq primario → Gemini fallback
- [x] Wire social: Groq primario → Gemini lazy fallback
- [x] Railway env var GROQ_API_KEY + deploy (commit 80e6097)
- [x] Confirmar Groq OK primario en prod (logs 22:52)
- [x] TPM opt: max_tokens sentinel 1200 (commit 546306d)
- [x] #2 binance 451: get_rsi + get_macro_trend → fallback
- [x] #3 HMM ZEC UNKNOWN: cripto-detección config.SYMBOLS + bare normalize
- [x] Probar #2+#3 con venv (RSI 48.0, get_df 60 velas) (commit 629eb2f)
- [x] Spec 024 documentado

## ⏳ Validación post-redeploy (en curso)

- [ ] Confirmar binance 451 GONE en logs prod (era ZEC/15m)
- [ ] Confirmar HMM ZEC régimen ≠ UNKNOWN (requiere hmmlearn Railway)
- [ ] `/budget` en Telegram muestra split Groq vs Gemini en vivo
- [ ] Market Status próximo: ZEC Monitor con regime real + sin parse fail

## 💡 Backlog (next session)

- [ ] **Stagger LLM calls** — espaciar símbolos para no topar Groq free TPM (6k llama / 8k gpt-oss) en burst. Hoy cae a Gemini graceful.
- [ ] **Promote Groq a primario duro** (decisión B+) si aguanta 7 días — medir groq_calls vs gemini_calls en /budget.
- [ ] **Billing Gemini** (opcional) — subir cap si se quiere Gemini robusto como fallback.
- [ ] **Spec 024.5** — agregar Groq a `api_health.py` watchdog (alertar si Groq cae igual que Gemini).
- [ ] **Otros call sites Gemini** — bitlobo_agent, grounded_search, stock_analyzer aún 100% Gemini. Evaluar si migran a multi-provider.
