# Tasks 023 — Intel a Stocks

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26

## Esta sesión

- [x] `social_quant._SUBREDDITS_BY_SYMBOL` extendido con 16 stock tickers:
  NVDA, TSLA, PLTR, SIL, HOOD, COIN, RKLB, XBI, OKLO, SMR, UUUU, IONQ,
  MP, SOFI, CRWV, IREN
- [x] Cada ticker mapped a wallstreetbets + sector subs específicos
- [x] `stock_analyzer.py:stock_watchdog` ENTRY_ALERT block:
  * Llamada `social_quant.get_social_sentiment(t.upper(), 24)`
  * Tag 🔥 EUPHORIA si signal == "EUPHORIA"
  * Tag 💀 FEAR si signal == "FEAR"
  * NEUTRAL/None → sin tag
  * try/except graceful
- [x] Tag prepended después de `_priority_tag`, antes de header
- [x] NO tag en ZONE_ALERT (solo ENTRY_ALERT)
- [x] py_compile stock_analyzer.py + social_quant.py OK
- [ ] Commit `feat(stocks): spec-023 social sentiment tag stock entries`
- [ ] Push origin/main

## Verificación post-deploy

- [ ] Próxima entry alert NVDA/TSLA/etc con social signal accionable → tag visible
- [ ] Logs Railway: `[grounded_search]` o similares NO aparecen (social ≠ grounded)
- [ ] REDDIT creds env vars configurados en Railway (recommended)
- [ ] Si creds missing → alert sigue sin social tag (graceful)

## Backlog Spec 023.5

- [ ] HMM regime stocks via yfinance adapter
- [ ] Gate alerts por EUPHORIA stocks (post-validation)
- [ ] Twitter/X sentiment API
- [ ] Insider trading Form 4 SEC
- [ ] ZONE_ALERT social tag (post-validation no ruido)
- [ ] Boost confluence stocks (necesita scoring stocks-specific)
