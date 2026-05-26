# Plan 002.5 — Regime Transitions

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26 (MVP)

## Decisiones técnicas

### 1. Módulo standalone vs hook directo en strategies

Standalone. Razones:
- Reutilizable en stocks + cripto + dashboard
- Testeable aislado sin runtime del bot
- State machine separada de business logic strategies

### 2. Persistencia JSON file en `data/macro_state.json`

Más simple que SQLite para 1 row state. Sobrevive Railway restart porque `data/` está en el repo (no /tmp).

Estructura:
```json
{
  "current": "VERDE_BULL_DORMANT",
  "previous": "AMARILLA_INDECISA",
  "since_ts": 1716696543,
  "last_check_ts": 1716700123,
  "sp500_price": 7150.5,
  "vix": 15.8
}
```

### 3. 4 régimens canonicales

- `VERDE_BULL` — SP500 > 7000, sin info VIX o VIX ≥ 22
- `VERDE_BULL_DORMANT` — SP500 > 7000 + VIX < 22 (barridas son oportunidad)
- `AMARILLA_INDECISA` — SP500 entre 6800 y 7000
- `NARANJA_BEAR` — SP500 < 6800
- `UNKNOWN` — sin datos

`VERDE_BULL_DORMANT` es subset de `VERDE_BULL` con VIX bajo. NotebookLM 4 lo trata distinto (barridas son oportunidad).

### 4. EXPLOSIVE_TICKERS hardcoded

Subset de DEFENSIVE_SECTORS con beta alta:
- Crypto-tier: RKLB, HOOD, ASTS, COIN, MP
- AI infra: CRWV, IREN, CORZ, CIFR
- Nuclear: OKLO, SMR, UUUU
- Quantum: IONQ, RGTI

Set de 14 tickers. NotebookLM Prompt 6 los mencionó como "explosive". Movible a config en Spec 002.6.

### 5. is_bullish_transition + is_bearish_transition flags

Bullish: AMARILLA → VERDE (cualquiera) o NARANJA → VERDE/AMARILLA.
Bearish: VERDE → AMARILLA, AMARILLA → NARANJA, VERDE → NARANJA.

Flags expuestos en el dict de `detect_transition` para que callers no tengan que parsear el string `transition`.

### 6. Freshness window 24h para EXPLOSIVE_CORRECTION

```python
age_seconds = int(time.time()) - t["since_ts"]
return age_seconds < 86400
```

Patrón histórico: recovery vertical dura ~3-7 días. Boost solo aplica primeras 24h post-transition (más fresco = más impulso). Después de 24h, ya es trending normal.

### 7. SP500 price via SPY proxy

stock_analyzer.py tiene `current_prices.get("SPY")`. SP500 ≈ SPY × 10 (aproximación).

NO oficial pero close enough para régimen classification.

Mejor sería integrar yfinance directo del SPX index. Spec 002.6 candidate.

### 8. Wire MVP solo en stock_analyzer ENTRY_ALERT

Tag `⚡ EXPLOSIVE_CORRECTION` solo. NO afecta logic de alert (no boost, no skip). Solo visibilidad.

Spec 002.6:
- Wire BARRIDA_OPPORTUNITY en V3-REVERSAL gates (relax thresholds)
- Boost confluence Spec 021 cuando EXPLOSIVE_CORRECTION matches ticker
- Endpoint `/api/metrics/regime_transitions`

## Verificación

- ✅ py_compile regime_transitions.py + stock_analyzer.py
- ✅ Smoke: get_current_macro_state 4 régimens ✓
- ✅ detect_transition con previous → bullish_transition correcto
- ✅ is_explosive_correction_setup acepta ticker correctamente
- ✅ is_barrida_opportunity acepta drop_pct ≥ 2

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(macro): spec-002.5 regime transitions — EXPLOSIVE_CORRECTION + BARRIDA helpers` |

## Backlog Spec 002.6

- Wire BARRIDA_OPPORTUNITY en V3-REVERSAL gates (Spec 016 extension)
- Boost confluence cuando EXPLOSIVE matches (Spec 021 extension)
- Endpoint `/api/metrics/regime_transitions`
- SP500 real index via yfinance (`^GSPC`) en lugar de SPY × 10
- EXPLOSIVE_TICKERS a config.py
- Backtest histórico de los 2 filtros (NotebookLM 4 P5 dijo no validation aún)
- intraday_drop_pct tracking (5min vs hora actual) para BARRIDA wire
