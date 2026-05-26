# Plan 013 — Social Sentiment Quant

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE (module only) 2026-05-26

## Estrategia

Módulo standalone `social_quant.py` análogo a `regime_hmm.py` (no toca core). Una función pública `get_social_sentiment()` con tres fuentes (Reddit, Google Trends, VADER). Sin side-effects en otros archivos — wire-in se hace en Spec 013.5 cuando el módulo esté validado en producción + Reddit credentials estén en Railway.

## Decisiones técnicas

### 1. VADER over transformer NLP (FinBERT, RoBERTa)

- VADER es rule-based + lexicon (~7,500 palabras anotadas), incluye slang internet ("lol", "wtf", "moon", "rekt").
- Latencia: ~0.1ms por texto vs 50-200ms por transformer. Con 50 posts/símbolo, VADER = 5ms, transformer = 2.5-10s.
- FinBERT requiere ~500MB modelo + GPU para latencia razonable en Railway → infra cost prohibitivo este spec.
- VADER suficiente para señal direccional (compound -1 a 1). Si Spec 013.5 tracking muestra que falla en sarcasmo crypto → upgrade Spec 013.6.

### 2. Reddit subreddits configurables por símbolo

```python
_SUBREDDITS_BY_SYMBOL = {
    "BTC":  ["CryptoCurrency", "Bitcoin", "wallstreetbets"],
    "ETH":  ["CryptoCurrency", "ethereum", "wallstreetbets"],
    "SOL":  ["CryptoCurrency", "solana", "wallstreetbets"],
    "TAO":  ["TaoBittensor"],
    "ZEC":  ["zec"],
}
```

- Major coins: mix de generalistas (CryptoCurrency) + dedicado (Bitcoin/ethereum) + retail euphoria (wallstreetbets).
- Small caps (TAO, ZEC): solo subreddit dedicado — generalistas tienen poco volumen para estos símbolos.
- Filtro de mención: si NO es subreddit dedicado → requiere símbolo en text. Dedicated → toma todo (todo el sub es sobre ese símbolo).

### 3. Reddit auth vía env vars (NO hardcoded)

- `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` en Railway env.
- `read_only=True` — bot no necesita user auth, solo app-level read access.
- Si missing → log + skip Reddit. Google Trends sigue funcionando solo.
- Patrón consistente con `os.getenv("ETHERSCAN_API_KEY")` en `whale_netflows.py` (Spec 010).

### 4. pytrends timeframe='now 1-d'

- 1 día = ~180 puntos (cada 8min). Suficiente granularidad para detectar spike en última hora.
- Split 75/25: prior 75% vs recent 25% → delta % = ((recent - prior) / prior) × 100.
- Edge case: si prior_avg == 0 → delta = 100% (cualquier interés es spike).
- timeframe más largo (`'today 1-m'`) capturaría tendencias de fondo pero perdería el spike intra-día que es la señal de Exodo.

### 5. Cache 30min módulo-level

```python
_CACHE = {}  # {cache_key: {"data": result, "last_update": ts}}
cache_key = f"{symbol}:{lookback_hours}"
```

- TTL = 1800s (30min). praw + pytrends combinados ~5-10s por símbolo → necesita cache.
- Patrón idéntico a `market_intel._CACHE` (funding/regime cache).
- Razonamiento TTL: sentimiento retail no cambia en minutos. 30min es granularidad útil para señal de régimen.

### 6. Signal classification con doble gate

```python
EUPHORIA  ← compound > 0.5 AND trends_delta > 30%
FEAR      ← compound < -0.3 AND trends_delta > 30%
NEUTRAL   ← otherwise
```

- **Trends delta es el "filtro de atención":** retail sentiment alto sin spike de búsqueda = noise crónico.
- Solo dispara EUPHORIA/FEAR cuando hay atención REAL (búsquedas suben) + sentiment direccional.
- Fear threshold (-0.3) más permisivo que Euphoria (0.5) porque negative sentiment en crypto es más raro (sesgo bullish inherente) → cuando aparece, es señal fuerte.

### 7. VADER apply a title + selftext[:500]

- Title carga la mayor parte del signal (titulares son polarizantes en Reddit).
- selftext truncado a 500 chars: posts largos diluyen el compound. Primeros 500 chars = lead + thesis.
- Combinar como `f"{title}. {selftext}"` ayuda a VADER a contextualizar (period entre title y body).

### 8. Empty dict on failure

Patrón consistente con `regime_hmm.detect_regime`, `indicators.detect_fair_value_gaps`:
- Caller chequea `if not result:` → fallback a comportamiento sin social signal
- No raise — bot debe degradar gracefully

### 9. Graceful degradation por dep

- 3 flags independientes: `_PRAW_AVAILABLE`, `_PYTRENDS_AVAILABLE`, `_VADER_AVAILABLE`.
- VADER es required (sin él no hay clasificación). praw + pytrends son combinables: con uno solo, devuelve parcial.
- Si ambos external sources fallan → empty dict.

### 10. Constants en módulo, NO en config.py

Razonamiento: estas constantes son **internas al algoritmo de sentiment**. config.py debe ser thresholds **operativos del bot** (RSI, ATR, etc.) que un trader puede tunear. Los thresholds VADER son de implementation detail.

Si Spec 013.5 confirma que Fernando quiere tunearlas live → mover entonces.

## Verificación

- ✅ py_compile social_quant.py
- ✅ AST: `get_social_sentiment`, `_scan_reddit`, `_scan_google_trends`, `_classify_signal`
- ✅ requirements.txt contiene `praw>=7.7.0`, `pytrends>=4.9.0`, `vaderSentiment>=3.3.2`
- ✅ Importable sin deps → empty dict + log warning
- ✅ Otros archivos del bot intactos
- ✅ `_classify_signal` test unit manual: EUPHORIA, FEAR, NEUTRAL casos OK

Producción pendiente:
- Reddit credentials en Railway env
- Spec 013.5: wire a voz Exodo + gate strategies + /social Telegram

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(social): spec-013 Social Sentiment Quant (Reddit + Trends + VADER, standalone)` |

## Tuning post-7d (Spec 013.5)

- Si `signal == EUPHORIA` correlaciona con tops locales (>60% accuracy) → activar gate contrarian.
- Si VADER falla en sarcasmo (manual review de top_3_titles vs compound) → upgrade FinBERT.
- Si pytrends da 429 en producción → reducir frecuencia + aumentar TTL a 60min.
- Si Reddit posts/sub < 5 frecuentemente → expandir lista de subreddits.

## Próximos specs roadmap

- **Spec 013.5** — Hook a voz Exodo en `gemini_analyzer.py:get_ai_consensus` + gate `strategies.py` EUPHORIA → 50% size + comando Telegram `/social SYMBOL`
- **Spec 013.6** — Upgrade VADER → FinBERT si tracking muestra fallos en sarcasmo crypto
- **Spec 014** — Twitter/X integration (post NotebookLM 5 research)
- **Spec 015** — Backtest histórico de social signal vs forward returns
