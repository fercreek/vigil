# Spec 013 — Social Sentiment Quant (voz Exodo narrativa)

> **Status:** CODE COMPLETE (module only — hooks pending Spec 013.5) 2026-05-26
> **Owner:** Fernando
> **Severity:** P1 — Mes 3 Sem 9-10 roadmap NotebookLM 4
> **Origen:** `docs/research/notebook-lm-4/RESULTS.md` Prompt 1 strategy #3 + Prompt 6 Spec 014

## Contexto

NotebookLM 4 Prompt 1 strategy #3 + Prompt 6 Spec 014: cuantificar sentimiento Reddit + Google Trends para anticipar cambios de régimen **irracionales** antes de que el precio reaccione. Cuando el flujo institucional aún no ha movido el book pero retail empieza a entrar en estados emocionales extremos, el bot puede:

- Confirmar setups contra-tendencia con señal de **EUPHORIA** (fade the crowd)
- Reforzar entradas LONG con señal de **FEAR** (capitulación retail = oportunidad)
- Filtrar señales cuando NEUTRAL = no hay alpha social claro

Caso de uso central — **Exodo narrativa** en la Cuadrilla Zenith:
- Exodo es la voz que cuenta el "story" del activo (narrativa social, retail mood).
- Esta spec entrega el módulo `social_quant.py` standalone que alimenta a Exodo.
- WR esperado: +6-7pp sobre baseline cuando confirma euphoria/fear con setup técnico.

Esta spec entrega el módulo standalone. Wire-in a `gemini_analyzer.py:get_ai_consensus` voz Exodo + gate de tamaño en `strategies.py` queda para Spec 013.5.

## Goals

1. `social_quant.get_social_sentiment(symbol, lookback_hours)` retorna dict con `reddit_compound`, `reddit_post_count`, `reddit_top_3_titles`, `google_trends_score`, `google_trends_delta`, `signal`, `last_update_ts`.
2. Reddit scan vía praw sobre subreddits configurables por símbolo (BTC/ETH/SOL → CryptoCurrency + Bitcoin/ethereum + wallstreetbets, TAO → TaoBittensor, ZEC → zec).
3. Google Trends vía pytrends (sin API key) sobre `now 1-d`.
4. VADER compound score por post (title + 500 chars selftext) → promedio.
5. Clasificación: EUPHORIA (compound > 0.5 + trends_delta > 30%), FEAR (compound < -0.3 + trends_delta > 30%), NEUTRAL.
6. Cache 30min módulo-level (praw/pytrends son lentos: 2-5s cada uno).
7. Graceful degradation: si praw/pytrends/vader ausentes → empty dict + log warning. NO crash.
8. Reddit auth vía env vars `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` + `REDDIT_USER_AGENT`. Si missing → log warning, skip Reddit.

## Non-goals

- Wire en `gemini_analyzer.py:get_ai_consensus` voz Exodo → **Spec 013.5**
- Gate en `strategies.py`: EUPHORIA → reducir posición 50% (contrarian) → **Spec 013.5**
- Comando Telegram `/social SYMBOL` → **Spec 013.5**
- Twitter/X scraping — API cara + rate-limited brutal. NotebookLM Prompt 1 priorizó Reddit como señal limpia.
- Transformer NLP (FinBERT, RoBERTa) — overkill para títulos de Reddit. VADER 10x más rápido, suficiente para señal direccional.
- Cobertura de stocks NYSE — solo cripto este spec (subreddits ya configurados).
- Sentiment intra-hora — cache 30min = granularidad mínima razonable.

## Dependencias

- `praw>=7.7.0` ✅ (añadido a requirements.txt) — Reddit API wrapper
- `pytrends>=4.9.0` ✅ (añadido) — Google Trends sin key
- `vaderSentiment>=3.3.2` ✅ (añadido) — NLP rule-based
- Env vars: `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` (config en Railway)

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Reddit API rate limit (60 req/min en read-only) | Cache 30min + limit=10 posts/sub. 5 subs × 10 = 50 reqs por símbolo → cabe en quota. |
| pytrends 429 / IP ban por scraping intensivo | Cache 30min + timeout (5, 15). Solo se llama bajo demanda, no en loop. |
| VADER no entiende sarcasmo/memes crypto ("to the moon" = bullish ok, "rekt" = bearish ok) | VADER tiene buen lexicón de slang. Para casos extremos → upgrade a FinBERT en Spec 013.6. |
| Subreddits dedicados pequeños (r/TaoBittensor, r/zec) < 10 posts/día | Filtro `if not is_dedicated and symbol not in text` se relaja para dedicated subs (toma todo). |
| Trends delta noise por baja muestra (24 puntos / 1d) | Threshold 30% es agresivo. Solo dispara con cambios reales de búsqueda. |
| Reddit credentials leaked si hardcoded | Env vars only. `_get_reddit_client` retorna None si missing. |
| EUPHORIA signal disparada por noticias generales (no específicas del símbolo) | Filtro de mención de símbolo en text excepto subreddits dedicados al símbolo. |

## Criterio de aceptación

1. `python3 -m py_compile social_quant.py` → OK
2. AST: `get_social_sentiment`, `_scan_reddit`, `_scan_google_trends`, `_classify_signal` definidos
3. Importable sin praw/pytrends/vader (flags `_PRAW_AVAILABLE`, `_PYTRENDS_AVAILABLE`, `_VADER_AVAILABLE` = False, devuelve `{}`)
4. `praw>=7.7.0`, `pytrends>=4.9.0`, `vaderSentiment>=3.3.2` en `requirements.txt`
5. Constants documentadas en el módulo (NO en config.py): `SOCIAL_EUPHORIA_THRESHOLD = 0.5`, `SOCIAL_FEAR_THRESHOLD = -0.3`, `SOCIAL_TRENDS_DELTA_THRESHOLD = 30.0`, `SOCIAL_CACHE_TTL = 1800`
6. NO modificación de otros archivos del bot (config / gemini_analyzer / strategies / market_intel intactos)
7. Reddit auth solo vía env vars — NO credentials en código
8. Producción pendiente Spec 013.5: wire a voz Exodo + gate strategies + comando Telegram
