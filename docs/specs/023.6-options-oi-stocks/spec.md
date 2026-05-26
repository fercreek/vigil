# Spec 023.6 — Options OI Volume Profile para Stocks vía yfinance

> **Status:** CODE COMPLETE 2026-05-26
> **Owner:** Fernando
> **Severity:** P2 — agrega 4ta/5ta capa de confluencia para stock ENTRY_ALERTs
> **Origen:** Spec 023.5 backlog (CVD-like volume profile stocks vía yfinance options chain)

## Contexto

Stocks no tienen tape público comparable a Binance trades (cripto cuenta con CVD segmented vía Spec 012). NotebookLM 4 propuso en backlog Spec 023.6: yfinance expone options chain con Open Interest (OI) por strike por expiration → agregar calls OI vs puts OI por las primeras N expirations es proxy directo de positioning institucional / dark pool sentiment.

Lógica: institucionales acumulan options antes de moves grandes. Ratio call/put OI elevado = sesgo bullish institucional. Inverso = bearish hedging.

Spec 023.6 wirea esto como tag visual en `stock_analyzer.stock_watchdog` ENTRY_ALERT, posicionado después del `_hmm_tag` (Spec 023.5), formando confluencia cuádruple:

```
🔥 PRIORIDAD ALTA      (Spec 003)
💀 Social              (Spec 023)
⚡ EXPLOSIVE_CORRECTION (Spec 002.5)
📊 HMM régimen          (Spec 023.5)
📈 Options OI           (Spec 023.6) ← NEW
🚨 ALERTA DE ENTRADA
```

## Goals

1. **Nuevo módulo `options_oi.py`** (standalone, no toca otros módulos):
   - Lazy import `yfinance` con `_YFINANCE_AVAILABLE` flag (patrón Spec 023.5)
   - `get_options_oi_ratio(ticker, expirations_lookback=2)` retorna dict:
     ```python
     {
         "ticker": str,
         "total_call_oi": int,
         "total_put_oi": int,
         "call_put_ratio": float,
         "signal": "CALL_HEAVY" | "PUT_HEAVY" | "BALANCED",
         "expirations_analyzed": list[str],
         "last_update_ts": int,
     }
     ```
   - Lógica core:
     * `yf.Ticker(t).options` retorna lista de expirations disponibles
     * Tomar las primeras N (default 2 — más cercanas en tiempo)
     * Para cada: `tk.option_chain(date)` retorna struct con `.calls` y `.puts` DataFrames
     * Sum `openInterest` column de calls y puts across expirations
   - Signal classification:
     * `CALL_HEAVY` si `call_put_ratio >= 2.0` (bullish positioning)
     * `PUT_HEAVY` si `call_put_ratio <= 0.5` (bearish hedging)
     * `BALANCED` entre 0.5–2.0 (no edge, no tag emitido)
   - Cache TTL 30min via module-level `_CACHE` keyed por `(ticker, expirations_lookback)`
   - Helpers `_cache_get` / `_cache_set` con eviction max 32 entries
   - Empty dict `{}` on failure (caller decide fallback)

2. **Wire en `stock_analyzer.py:stock_watchdog` ENTRY_ALERT**:
   - Llamada `options_oi.get_options_oi_ratio(t.upper(), expirations_lookback=2)`
   - Después del `_hmm_tag`, antes del header `🚨 ALERTA DE ENTRADA`
   - Si signal != "BALANCED" → emite tag `📈 Options OI: CALL_HEAVY (ratio 2.3x) — bullish institutional` o `📉 PUT_HEAVY`
   - BALANCED → no tag (evita ruido en alerts neutrales)
   - Try/except graceful — sin yfinance o fallo de chain = skip tag, alert continúa

3. **Spec docs** spec.md / plan.md / tasks.md siguiendo template Spec 023.5

## Non-goals

- **Gate logic por OI signal** — solo tag visual MVP. Bloquear long si PUT_HEAVY sería over-engineering pre-validación. Spec 023.7 candidate después de backtest.
- **Inyectar OI a Cuadrilla Zenith Salmos** — solo wire visual stock_analyzer por ahora. Spec 023.7.
- **Cripto options OI** — Deribit tendría que parsearse. Out of scope, foco stocks.
- **OI por strike granular / max pain calculation** — agregamos suma sola. Strike-level analysis es Spec 023.7+.
- **IV (Implied Volatility) rank percentile** — yfinance expone `impliedVolatility` pero IV rank requiere histórico. Spec 023.7.
- **Unusual options activity scanner** — comparar OI delta vs N días atrás. Requires DB persistence, Spec 023.7.
- **Soporte cripto via Deribit** — out of scope.

## Dependencias

- `yfinance==1.2.0` ✅ (ya en requirements.txt desde Spec 023.5)
- `stock_analyzer.py:stock_watchdog ENTRY_ALERT block` ✅
- pandas (transitive via yfinance) ✅

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| yfinance rate-limit (Yahoo bloquea IPs agresivas) | Cache TTL 30min (más conservador que HMM 15min — OI cambia lento). ~16 stocks × 2/h = 32 calls/h debajo del limit |
| ETFs sin options chain (IWM tiene, algunos sectoriales no) | `tk.options` retorna `()` empty → return `{}` graceful, tag se omite |
| Tickers con expirations 0-DTE (mismas-day options) — OI distorsiona | Default `expirations_lookback=2` toma 2 expirations cercanas, suaviza single-day noise |
| Stock con baja liquidez de options (OI < 100 strikes total) | Ratio puede ser ruidoso. Mitigación parcial: thresholds 2.0/0.5 son conservadores. Future: min_total_oi gate |
| yfinance `option_chain()` puede fallar mid-day Yahoo updates | Try/except per-expiration + skip a la siguiente. Si TODAS fallan → empty dict graceful |
| OI total puts = 0 (ticker brand new options) | Guard `max(total_put_oi, 1)` evita div by zero. Ratio resultante será huge → CALL_HEAVY válido |
| Cache TTL 30min muy largo si Fernando quiere ver shifts intradía | OI institucional realmente NO cambia minute-by-minute. 30min es razonable. Override con clear `_CACHE.clear()` si debug |
| `getattr(chain, 'calls', None)` para defensa schema yfinance changes | Robust: si yfinance refactor renombra attributes, no crash — solo skip tag |
| Yahoo Finance ticker no listado (`AAA` inexistente) | `tk.options` raise exception → caught → empty dict |

## Criterio de aceptación

1. `python3 -m py_compile options_oi.py stock_analyzer.py` → OK
2. `options_oi.get_options_oi_ratio("NVDA")` retorna dict válido con `signal` y `call_put_ratio` (con yfinance instalado + market hours)
3. `options_oi.get_options_oi_ratio("NONEXISTENT_XYZ")` retorna `{}` graceful
4. Sin yfinance (`_YFINANCE_AVAILABLE = False`) → `get_options_oi_ratio("NVDA")` retorna `{}` sin crashear
5. `options_oi._classify_signal(2.5)` → `"CALL_HEAVY"`. `_classify_signal(0.4)` → `"PUT_HEAVY"`. `_classify_signal(1.0)` → `"BALANCED"`
6. Stock ENTRY_ALERT próxima (NVDA/TSLA/OKLO) muestra tag `📈 Options OI: ...` si signal != BALANCED
7. Cache TTL 30min: segunda llamada inmediata mismo ticker no re-fetch yfinance
8. No regression: tags Spec 023 / 023.5 / 002.5 siguen apareciendo en alerts

## Smoke local (sin yfinance instalado)

```python
>>> import options_oi
>>> options_oi._YFINANCE_AVAILABLE
False
>>> options_oi._classify_signal(2.5)
'CALL_HEAVY'
>>> options_oi._classify_signal(0.3)
'PUT_HEAVY'
>>> options_oi._classify_signal(1.5)
'BALANCED'
>>> options_oi.get_options_oi_ratio("NVDA")
# [OPTIONS_OI] yfinance no instalado — skip NVDA
{}
```

Graceful degradation: bot Railway tiene yfinance; dev local sin la lib no se rompe.
