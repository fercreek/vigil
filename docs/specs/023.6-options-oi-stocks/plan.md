# Plan 023.6 — Options OI Volume Profile (stocks)

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Decisiones técnicas

### 1. Thresholds 2.0 / 0.5 para signal classification

Ratio = `total_call_oi / max(total_put_oi, 1)`.

- `>= 2.0` → CALL_HEAVY (calls duplican o más a puts = sesgo bullish claro)
- `<= 0.5` → PUT_HEAVY (puts duplican o más a calls = sesgo bearish / hedging)
- Entre `0.5–2.0` → BALANCED (sin edge, no tag emitido)

Alternativas evaluadas:
- **1.5/0.66 (más sensible)** → demasiados tags BALANCED reclasificados como direccionales. Genera ruido.
- **3.0/0.33 (más estricto)** → pierde señales válidas (un PUT_HEAVY 0.45 es accionable).
- **2.0/0.5 (default)** → simétrico (recíprocos), umbral conservador que distingue positioning real vs noise.

Validación: PTS metodología sugiere que ratios extremos correlacionan con resoluciones de zones. Backtest histórico es Spec 023.7.

### 2. `expirations_lookback=2` default

Tomamos las 2 primeras expirations cercanas en tiempo. Razones:

- **Una sola expiration** = vulnerable a 0-DTE distortion (high volume mismo día caduca).
- **3+ expirations** = OI lejana dilute el sesgo direccional cerca del precio actual.
- **2 expirations** = sweet spot: típicamente próximo viernes + viernes siguiente = ~1-3 semanas forward, ventana donde positioning institucional accionable es claro.

Stocks como NVDA tienen weeklies (expirations cada viernes), TSLA igual. Tickers menos líquidos (UUUU, OKLO) pueden tener monthlies solo → 2 lookback toma current + next month, también válido.

### 3. Cache TTL 30min (vs HMM 15min)

OI no cambia minute-by-minute. Es positioning institucional que se acumula días. 30min razonable:

| TTL | Calls/h por stock | Pros | Cons |
|-----|-------------------|------|------|
| 5min | 12 | Realtime-ish | Yahoo rate-limit risk |
| 15min | 4 | Balanceado | Overkill para OI |
| **30min** | **2** | **Conservative + accurate** | Posible miss de shift intra-30min |
| 60min | 1 | Min API calls | Stale en news events |

30min con 16 stocks watchlist = 32 calls/h — bien debajo del Yahoo ~500/h soft limit.

### 4. Módulo standalone vs extender regime_hmm

Decisión: módulo nuevo `options_oi.py`. Razones:

- Separation of concerns: regime_hmm es HMM features. OI es volume profile institucional. Lógicas independientes.
- Cache TTL diferente (30min vs 15min) sin interferencia
- Testing aislado más simple
- Backwards compat trivial — no toca regime_hmm

### 5. Defensive parsing yfinance schema

```python
calls_df = getattr(chain, "calls", None)
if calls_df is not None and "openInterest" in calls_df.columns:
    call_oi = int(calls_df["openInterest"].fillna(0).sum())
```

Razones:
- yfinance puede cambiar attribute names en updates → `getattr` con default `None`
- DataFrames pueden carecer column en tickers con options brand new → `in columns` check
- `fillna(0)` por strikes nuevos sin OI registrada
- Try/except per-expiration → si una falla, otra puede pasar

### 6. Empty dict on failure (caller-decides pattern)

Mismo contrato que `regime_hmm.detect_regime`, `social_quant.get_social_sentiment`. Caller hace:

```python
_oi = options_oi.get_options_oi_ratio(t.upper()) or {}
_oi_signal = _oi.get("signal")
if _oi_signal == "CALL_HEAVY": ...
```

Esto significa stock_analyzer NO necesita try/except interno excepto el outer wrap (que está). Si OI falla → empty dict → `.get("signal")` retorna `None` → ninguna rama matchea → no tag emitido. Silencio gracefully.

### 7. BALANCED NO emite tag

Decisión deliberada de UX: alert ya tiene 4+ tags potenciales antes del header. Agregar un 5to "BALANCED" sin información accionable = ruido visual.

Solo emit cuando hay señal real: CALL_HEAVY o PUT_HEAVY. Esto sigue el patrón Spec 002.5 EXPLOSIVE_CORRECTION (solo tag si setup activo, no si neutral).

### 8. Posición del tag en mensaje

```
{_priority_tag}        ← Spec 003 (PRIORIDAD ALTA)
{_social_tag}          ← Spec 023 (EUPHORIA/FEAR)
{_explosive_tag}       ← Spec 002.5 (EXPLOSIVE_CORRECTION)
{_hmm_tag}             ← Spec 023.5 (HMM régimen)
{_options_oi_tag}      ← Spec 023.6 (Options OI) NEW
🚨 ALERTA DE ENTRADA   ← header
```

Tags institucional/macro acumulan antes del header. Fernando lee top-down: contexto macro → confluencia institucional → setup ticker específico.

## Verificación

- ✅ `python3 -m py_compile options_oi.py stock_analyzer.py` → OK
- ✅ `_classify_signal(2.5)` → `'CALL_HEAVY'` (correct threshold logic)
- ✅ `_classify_signal(0.4)` → `'PUT_HEAVY'`
- ✅ `_classify_signal(1.5)` → `'BALANCED'`
- ✅ Function list AST inspection: `get_options_oi_ratio`, `_classify_signal`, `_cache_get`, `_cache_set` exposed
- ✅ Lazy yfinance: `_YFINANCE_AVAILABLE` flag patrón Spec 023.5 idéntico
- ✅ Wire stock_analyzer: tag posicionado entre `_hmm_tag` y `🚨 ALERTA DE ENTRADA` header
- ⏳ Producción Railway (siguiente deploy): tag aparece en próxima ENTRY_ALERT NVDA/TSLA/OKLO/COIN si signal != BALANCED

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(options): spec-023.6 OI volume profile stocks via yfinance + wire stock_analyzer tag` |

## Backlog Spec 023.7

- IV (Implied Volatility) rank percentile via yfinance — requires histórico OI/IV snapshots para percentile
- Unusual options activity scanner — comparar OI delta sesión actual vs N días atrás (requires DB persistence)
- Strike-level analysis — max pain calculation, gamma exposure (GEX)
- Gate logic por OI signal (block long si PUT_HEAVY extremo) — requires backtest validation
- Inyectar OI signal a Cuadrilla Zenith Salmos (analog Spec 017.5)
- Endpoint `/api/metrics/options_oi` para dashboard
- min_total_oi gate — descartar signals si OI total < 1000 (low liquidity stocks)
- Soporte cripto via Deribit options chain (BTC/ETH)
- Skew analysis — call OI vs put OI weighted by strike distance to spot price (vertical positioning)
