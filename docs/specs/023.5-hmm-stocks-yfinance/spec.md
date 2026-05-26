# Spec 023.5 — HMM Regime Classifier para Stocks vía yfinance

> **Status:** CODE COMPLETE 2026-05-26
> **Owner:** Fernando
> **Severity:** P1 — cierra wire HMM en stock_analyzer (la mitad del bot operaba sin Salmos semáforo)
> **Origen:** Spec 023 backlog (HMM stocks defer)

## Contexto

Spec 009 + 009.6 implementó HMM 3-state regime classifier (`STRONG_TREND` / `RANGE` / `VOLATILE_SQUEEZE`) sobre OHLCV cripto vía `indicators.get_df` (ccxt Binance Spot). Spec 017.5 inyectó regime a las 4 strategies cripto.

Stocks NO tenían wire de HMM porque `regime_hmm.detect_regime` no podía resolver tickers tipo `NVDA` / `TSLA` / `OKLO` (ccxt no opera NYSE). Spec 023 wireó social sentiment para stocks pero dejó HMM defer porque requería yfinance adapter.

Spec 023.5 cierra ese gap: extender `regime_hmm.py` con source routing — cripto sigue ccxt, stocks usan yfinance adapter — y tagar `📊 HMM régimen: REGIME (conf X%)` en ENTRY_ALERT del `stock_watchdog`.

## Goals

1. **`regime_hmm.py` graceful extension** (backwards compatible):
   - Helper `_fetch_ohlcv_stock(ticker, timeframe, lookback_candles)` que descarga vía `yfinance.Ticker(t).history(...)`, normaliza columnas a lowercase (`open/high/low/close/volume`) — mismo schema que `indicators.get_df`. Returns `None` si falla.
   - Helper `_yf_interval_period(timeframe, lookback)` mapea `("1h", 100)` → `("1h", "21d")` (yfinance API differences vs ccxt).
   - `detect_regime(symbol, ...)` branchea por `"/" in symbol`:
     - Cripto (con slash) → `indicators.get_df`
     - Stock (sin slash) → `_fetch_ohlcv_stock`
   - Mismo cache TTL 15min sirve para ambos (key `(symbol, timeframe, lookback)`).
   - Lazy import `yfinance` (graceful si missing — bot dev local sin yfinance no crashea).

2. **Wire en `stock_analyzer.py:stock_watchdog` ENTRY_ALERT**:
   - Llamada `regime_hmm.detect_regime(t.upper(), timeframe="1h", lookback=100)`
   - Si retorna regime válido → tag `📊 HMM régimen: REGIME (conf X%)` en msg
   - Posicionado después de `_explosive_tag`, antes de header `🚨 ALERTA DE ENTRADA`
   - Try/except graceful — yfinance error o hmmlearn missing = skip tag, alert continúa

3. **No tocar otros módulos.** `indicators.py`, `strategies.py`, `gemini_analyzer.py`, `social_quant.py` intactos.

## Non-goals

- HMM wire stocks ZONE_ALERT — solo ENTRY_ALERT (más accionable, Spec 023 patrón)
- Gate stocks alerts por HMM regime (e.g. block long si STRONG_TREND bajista) — solo TAG visual MVP. Spec 023.6 candidato.
- Override `lookback` por strategy — usamos 100 fijo para stocks (vs 200 cripto). Spec 023.6.
- Soporte de stocks `BRK.B` o tickers con `.` (yfinance los acepta nativos pero detect_regime usa `t.upper()` que no toca el `.`)
- CVD-like stocks vía yfinance options chain — Spec 023.6
- Refactor `indicators.get_df` para soportar stocks (rompería ccxt cripto)

## Dependencias

- `yfinance==1.2.0` ✅ (ya en requirements.txt)
- `hmmlearn` ✅ (Spec 009)
- `regime_hmm.detect_regime` ✅ existente
- `stock_analyzer.py:stock_watchdog ENTRY_ALERT block` ✅

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| yfinance rate-limit (Yahoo bloquea IPs agresivas) | Cache TTL 15min ya existente. Stock_watchdog corre ~1x/min. Worst case = 1 fetch/15min/ticker. ~16 stocks × 4/h = 64 calls/h muy debajo del limit |
| yfinance `1h` history limit 730 días | Lookback 100 candles ≈ 15 días, well within. `_yf_interval_period` mapea sin exceder |
| yfinance returns Adj Close confuso | Usamos `auto_adjust=False` + leemos `Close` raw para consistencia con indicators.get_df |
| Stock fuera market hours yfinance retorna data parcial / NaN | `.dropna()` + check `len(df) < 50` → return None gracefully → tag se omite |
| Tickers ETF tipo SPY / QQQ vs single stocks behave igual? | yfinance trata ETFs igual que stocks. Same OHLCV schema, mismos features HMM válidos |
| HMM features (log_ret, vol, range_pct) sensibles a gap-down stocks pre/post market | Features se calculan sobre 1h candles solo regular hours (NYSE). Gaps overnight aparecen como single large log_ret — HMM tiende a clasificarlos como VOLATILE_SQUEEZE, lo cual es accionable correcto |
| Cache key collision cripto vs stocks si alguien hace `detect_regime("BTC")` sin slash | NO — `BTC` sin slash entra rama stocks y yfinance.Ticker("BTC") retorna stock ETF / 404 → return None graceful. Cripto SIEMPRE usa formato `BTC/USDT` |
| HMM training_loss en stocks vs cripto comparable? | NO directamente — escalas distintas. Por eso no exponemos training_loss en tag visible al usuario; sólo regime + confidence |

## Criterio de aceptación

1. `python3 -m py_compile regime_hmm.py stock_analyzer.py` → OK
2. `regime_hmm._fetch_ohlcv_stock("NVDA")` retorna DataFrame con cols `open/high/low/close/volume` lowercase (con yfinance instalado)
3. `regime_hmm.detect_regime("NVDA", timeframe="1h", lookback=100)` retorna dict válido con regime label
4. `regime_hmm.detect_regime("BTC/USDT", timeframe="1h", lookback=200)` sigue funcionando (cripto path intacto — backwards compat)
5. Sin yfinance (`_YFINANCE_AVAILABLE = False`) → `detect_regime("NVDA", ...)` retorna `{}` gracefully sin crashear el bot
6. Stock ENTRY_ALERT (próxima alerta NVDA/TSLA/OKLO) muestra tag `📊 HMM régimen: REGIME (conf X%)`
7. Cache TTL 15min funciona para stocks — segunda llamada inmediata mismo ticker no re-fetch yfinance
8. Producción Railway: logs muestran HMM fits para stocks sin errores yfinance

## Smoke local (sin yfinance/hmmlearn instalado)

```python
>>> import regime_hmm
>>> regime_hmm._YFINANCE_AVAILABLE
False
>>> regime_hmm._yf_interval_period("1h", 100)
('1h', '21d')
>>> regime_hmm._fetch_ohlcv_stock("NVDA")
# [HMM YFINANCE] yfinance no instalado — skip stock regime para NVDA
None
>>> regime_hmm.detect_regime("NVDA", timeframe="1h", lookback=100)
# [HMM ERROR] hmmlearn no instalado...
{}
```

Graceful degradation: bot principal en Railway tiene ambas libs; dev local sin ellas no se rompe.
