# Tasks 013 — Social Sentiment Quant

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE (module only) 2026-05-26

## Esta sesión

- [x] `social_quant.py` creado con:
  - `get_social_sentiment(symbol, lookback_hours)` función pública
  - `_scan_reddit(symbol, lookback_hours)` — praw + VADER por subreddit configurable
  - `_scan_google_trends(symbol)` — pytrends now 1-d con split 75/25 prior/recent
  - `_classify_signal(reddit_compound, trends_delta)` — EUPHORIA/FEAR/NEUTRAL
  - `_get_vader()` — lazy singleton de VADER analyzer
  - `_get_reddit_client()` — praw.Reddit desde env vars REDDIT_CLIENT_ID/SECRET/USER_AGENT
  - Flags `_PRAW_AVAILABLE`, `_PYTRENDS_AVAILABLE`, `_VADER_AVAILABLE` para importabilidad sin deps
  - Cache 30min módulo-level `_CACHE` por (symbol, lookback_hours)
  - Try/except por subreddit + por scan → empty dict on full failure
- [x] `praw>=7.7.0`, `pytrends>=4.9.0`, `vaderSentiment>=3.3.2` añadidos a `requirements.txt`
- [x] py_compile + AST verification + classify_signal manual test (4 casos)
- [ ] Commit `feat(social): spec-013 Social Sentiment Quant (Reddit + Trends + VADER, standalone)`
- [ ] Push origin/main (Railway instala deps en deploy)
- [ ] Configurar `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` en Railway env

## Verificación post-deploy

- [ ] Railway build OK (praw + pytrends + vaderSentiment instalados sin errores)
- [ ] `python3 -c "from social_quant import get_social_sentiment; print(get_social_sentiment('BTC'))"` en Railway shell devuelve dict válido
- [ ] Log NO error `[SOCIAL REDDIT INIT ERROR]` (creds bien configurados)
- [ ] Log NO error `[SOCIAL TRENDS ERROR]` repetido (no rate-limit)
- [ ] Signal distribution después de 24h: ¿% EUPHORIA / FEAR / NEUTRAL? Si > 95% NEUTRAL → ajustar thresholds.

## Spec 013.5 — Wire-in pendiente

- [ ] Hook a `gemini_analyzer.py:get_ai_consensus` voz **Exodo**: inyectar `signal` y top_3_titles al prompt narrativa
- [ ] Gate en `strategies.py:V3-REVERSAL`: si `signal == "EUPHORIA"` en LONG → reducir tamaño 50% (contrarian)
- [ ] Gate en `strategies.py`: si `signal == "FEAR"` en LONG → refuerza confluencia (capitulación = oportunidad)
- [ ] Comando Telegram `/social SYMBOL` para inspect manual
- [ ] Logging por símbolo cada vez que se llama: `[SOCIAL] BTC: EUPHORIA (compound=0.62, trends_delta=+45%)`
- [ ] Alert Telegram si `signal == "EUPHORIA"` por 2h consecutivas en BTC/ETH (tops locales probables)

## Tuning post-7d (en Spec 013.5)

- [ ] Si EUPHORIA correlaciona con tops locales > 60% → activar gate firme
- [ ] Si EUPHORIA correlaciona < 50% → aflojar threshold compound a 0.4 + delta a 40%
- [ ] Si VADER misclassify obvio en top_3_titles → upgrade FinBERT (Spec 013.6)
- [ ] Si pytrends 429 frecuente → aumentar TTL a 60min + reducir simbolos en scan paralelo

## Backlog Spec 013.6+

- [ ] FinBERT upgrade si VADER falla en sarcasmo crypto / financial slang
- [ ] Twitter/X integration (post NotebookLM 5 research)
- [ ] Backtest histórico de social signal vs forward returns 6h/24h
- [ ] Cross-symbol contagion detection (BTC EUPHORIA → ETH EUPHORIA con lag)
- [ ] Sentiment delta velocity (no solo nivel, sino aceleración del cambio)
- [ ] Cobertura de stocks NYSE (subreddits: r/stocks, r/SecurityAnalysis, r/investing)

## Próximos specs roadmap

- [ ] **Spec 013.5** — Wire-in voz Exodo + gate strategies + /social Telegram (1-2 días)
- [ ] **Spec 013.6** — VADER → FinBERT upgrade si tracking muestra fallos (1 día)
- [ ] **Spec 014** — Pre-event volatility filter (post FOMC/CPI/Earnings) — NotebookLM 4 Spec 015
- [ ] **Spec 015** — Backtest histórico de social signal vs forward returns (3-4 días)
