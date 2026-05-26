# Plan 023.5 — HMM Regime Classifier para Stocks vía yfinance

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Decisiones técnicas

### 1. Source routing por presence de `/` en symbol

`symbol contains "/"` es el discriminator de hecho: cripto en Binance siempre es `BASE/QUOTE` (`BTC/USDT`, `TAO/USDT`). Stocks NYSE/NASDAQ jamás usan slash (`NVDA`, `TSLA`, `BRK.B`).

```python
is_crypto = "/" in symbol
if is_crypto:
    df = get_df(symbol, ...)  # ccxt
else:
    df = _fetch_ohlcv_stock(symbol, ...)  # yfinance
```

Alternativa rechazada: registry explícito de tickers stock. Más fragil (cada stock nuevo requiere update). Slash heuristic es DRY y cero-config.

### 2. yfinance lookback más corto (100 vs cripto 200)

Cripto: ccxt da 200 candles 1h sin friction (Binance API permisivo).
Stocks: yfinance `1h` interval limitado a 730 días + NYSE solo ~7 candles/día. 100 candles = ~15 días = window saludable que cabe en `period="21d"` con margen.

Trade-off: HMM con menos datos = fits levemente menos estables, pero 100 candles + 3-state HMM converge consistentemente.

### 3. Mismo cache TTL 15min para cripto + stocks

`_CACHE` keyed por `(symbol, timeframe, lookback)`. No hay colisión porque cripto siempre lleva slash en `symbol`. Cleanup LRU max 64 entries cubre ~16 stocks + 5 cripto × multiple lookbacks sin presión.

15min TTL razonable: HMM regime cambia lentamente (NotebookLM 4 Prompt 4: régimen institucional ≠ ruido intradía). Reducir a 5min sería overkill, aumenta calls yfinance sin valor.

### 4. `_yf_interval_period` mapper

yfinance API toma `(interval, period)`, ccxt toma `(timeframe, limit)`. Mapper traduce:

| timeframe ccxt | yfinance interval | period (lookback=100) |
|----------------|-------------------|-----------------------|
| `1m` | `1m` | `~9d` |
| `15m` | `15m` | `~9d` |
| `1h` / `60m` | `1h` | `~21d` |
| `4h` | `1h` (fallback) | `~21d` |
| `1d` | `1d` | `~110d` |
| `1w` | `1wk` | (no calc) |

`4h` no soportado nativo por yfinance → fallback a `1h`. Stock_analyzer pasa `1h` siempre así que no es issue. Future spec puede resample 1h→4h manualmente si necesario.

### 5. `auto_adjust=False` en yfinance.history

Default `auto_adjust=True` aplica splits/dividends al `Close`. Para HMM features (log returns, vol) **NO queremos eso** — queremos precio raw consistente con candles intraday tal cual mercado los vio.

Cripto en ccxt no tiene splits, no hay decision equivalente. Misma escala lógica.

### 6. Lazy import yfinance al top del módulo

```python
try:
    import yfinance as _yf
    _YFINANCE_AVAILABLE = True
except ImportError:
    _YFINANCE_AVAILABLE = False
    _yf = None
```

Mismo pattern que `_HMMLEARN_AVAILABLE`. Dev local sin yfinance sigue pudiendo importar `regime_hmm` para cripto regime (e.g. inspect cache). Production Railway tiene ambas → full flujo.

### 7. Wire en stock_analyzer: tag visible, NO gate logic

```python
_hmm_tag = ""
try:
    import regime_hmm
    _hmm = regime_hmm.detect_regime(t.upper(), timeframe="1h", lookback=100) or {}
    if _hmm.get("regime"):
        _hmm_tag = f"📊 <b>HMM régimen:</b> {regime} (conf {conf*100:.0f}%)\n"
except Exception:
    pass
```

MVP: solo tag visual. NO bloquea alert si STRONG_TREND vs RANGE. Razón:
- NotebookLM 4 dijo wire HMM stocks pero validation backtest pending
- Stocks operan diferente a cripto V3-REVERSAL (zona BitLobo es la señal primaria)
- Tag visible es info para Fernando decidir manual; gate sería over-engineering pre-validation

Spec 023.6 candidate: gate por HMM regime después de backtest histórico.

### 8. Posición del tag en mensaje

```
{_priority_tag}        ← Spec 003
{_social_tag}          ← Spec 023
{_explosive_tag}       ← Spec 002.5
{_hmm_tag}             ← Spec 023.5 (NEW)
🚨 ALERTA DE ENTRADA   ← header
```

Tags macro/intel van antes del header — Fernando ve contexto institucional primero, luego setup ticker.

## Verificación

- ✅ `python3 -m py_compile regime_hmm.py stock_analyzer.py` → OK
- ✅ Local smoke sin libs: `_YFINANCE_AVAILABLE=False`, `_HMMLEARN_AVAILABLE=False`, `detect_regime("NVDA")` → `{}` graceful
- ✅ `_yf_interval_period` mapper retorna pairs válidos para todos timeframes comunes
- ✅ `_fetch_ohlcv_stock("NVDA")` sin yfinance instalado retorna `None` con log claro
- ✅ Cripto path intacto: `detect_regime("BTC/USDT", ...)` sigue usando `indicators.get_df` (verified by code inspection del branch `if is_crypto`)
- ⏳ Producción Railway (siguiente deploy): HMM tag aparece en próxima ENTRY_ALERT NVDA/TSLA/OKLO

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(hmm): spec-023.5 yfinance adapter para stocks regime + wire stock_analyzer tag` |

## Backlog Spec 023.6

- Gate stocks alerts por HMM regime (block long si STRONG_TREND bajista) — requires backtest validation
- Inyectar HMM regime stocks a Cuadrilla Zenith Salmos (analog a Spec 017.5 cripto)
- CVD-like volume profile stocks vía yfinance options chain (open interest aggregation)
- Override `lookback` por strategy (V3-REVERSAL podría querer 200 candles, scalper 50)
- Soporte timeframe `4h` real vía resample 1h→4h en `_fetch_ohlcv_stock`
- Endpoint `/api/metrics/hmm_stocks` para dashboard
- Backtest histórico: validar que HMM regime stocks predice price action (precision/recall por regime label)
