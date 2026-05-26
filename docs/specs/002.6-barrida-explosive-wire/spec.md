# Spec 002.6 — Wire BARRIDA_OPPORTUNITY + EXPLOSIVE_CORRECTION en V3-REVERSAL + endpoint

> **Status:** CODE COMPLETE 2026-05-26
> **Owner:** Fernando
> **Severity:** P1 — completar wire de Spec 002.5 (helpers existen, no integrados)
> **Origen:** Backlog Spec 002.5 — sección "Non-goals"

## Contexto

Spec 002.5 dejó `regime_transitions.py` standalone con:
- `is_explosive_correction_setup(ticker, sp500, vix)` — True si AMARILLA→VERDE reciente + ticker en EXPLOSIVE_TICKERS
- `is_barrida_opportunity(cluster, sp500, vix, drop_pct)` — True si VERDE_BULL_DORMANT + cluster ai_infra/nuclear + drop≥2%
- Tag visual `⚡ EXPLOSIVE_CORRECTION` ya wired en `stock_analyzer.py`

Faltaba:
1. Boost confluence Spec 021 cuando EXPLOSIVE matches
2. Relax gates Spec 016 cuando BARRIDA active
3. Endpoint `/api/metrics/regime_transitions` para dashboard

## Goals

1. **EXPLOSIVE_CORRECTION boost en V3-REVERSAL** (`strategies.py`):
   - En el bloque `_boost` Spec 021 (post-CVD/Social/Whale/HMM), agregar:
     ```python
     if regime_transitions.is_explosive_correction_setup(sym_base, sp500_proxy, vix):
         _boost += 1.5
         _boost_reasons.append("EXPLOSIVE_CORRECTION (post régimen AMARILLA→VERDE)")
     ```
   - Boost +1.5 (vs +1.0 del resto) porque setup raro y robusto históricamente.

2. **BARRIDA_OPPORTUNITY relax gates en V3-REVERSAL** (`strategies.py`):
   - Antes de los gates HMM/CVD, computar `_barrida_active`.
   - Si activo + cluster del símbolo ∈ {ai_infra, nuclear}:
     - **NO** bloquear por HMM STRONG_TREND
     - **NO** bloquear por CVD BEARISH
     - SÍ seguir bloqueando por funding (volatilidad real) + Social EUPHORIA
   - Log: `⚡ [V3-Reversal] {sym}: BARRIDA_OPPORTUNITY active — relajando HMM+CVD gates`

3. **Helper `get_cluster_for_symbol(sym_base)`** en `regime_transitions.py`:
   - Lookup reverso de `SECTOR_CLUSTERS` config
   - Returns cluster name (e.g. "ai_infra") o `None`

4. **Endpoint `/api/metrics/regime_transitions`** en `app.py`:
   - Llama `get_state_summary()` + `detect_transition(SP500, VIX)` con valores actuales
   - SP500 source: `app_helpers.get_macro_price("SPY") * 10` o fallback 7000
   - Returns JSON: current/previous/transition/since_iso + EXPLOSIVE_TICKERS list + BARRIDA_CLUSTERS

## Non-goals

- Wire en V2-AI/V4-EMA/SWING — Spec 002.7 (V3 cripto es prueba; los otros tocan stocks donde aplica más BARRIDA)
- Tracking real-time de `intraday_drop_pct` — Spec 002.7. Por ahora se llama con `drop_pct=0` (BARRIDA queda dorment para cripto hasta que haya feed real)
- yfinance directo `^GSPC` para SP500 real — Spec 002.7
- EXPLOSIVE_TICKERS a config — Spec 002.7
- Backtest histórico filtros — Spec 002.8

## Cluster lookup — caveat documentado

V3-REVERSAL opera SOLO cripto (BTC/ETH/SOL/ZEC/TAO). De estos, ninguno está en SECTOR_CLUSTERS["ai_infra"] ni "nuclear" (sí en "crypto_proxy" pero ese cluster NO está en BARRIDA_CLUSTERS).

→ BARRIDA effectively DORMENT en V3 hasta Spec 017.5 extienda intel a strategies que tocan stocks. Wire queda en place ready-to-fire cuando aplique.

## Dependencias

- `regime_transitions.py` ✅ (Spec 002.5)
- `config.SECTOR_CLUSTERS` ✅
- `strategies.py` V3-REVERSAL block ✅
- `app.py` endpoint pattern ✅ (Spec 020)

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| `is_explosive_correction_setup` llama `detect_transition` → persiste state cada V3 alert. Aceptable: ya se llama ciclo `stock_watchdog` | OK, state file write idempotent |
| Boost +1.5 alto puede inflar conf_score a >7 (max badge DIAMANTE prematuro) | `calculate_confluence_score` ya tiene `min(7, score)`. Boost post-cap no tiene check — log si conf_score>7 para auditar |
| BARRIDA dorment para cripto (no feed drop_pct) | Documentado en spec. Wire ready cuando Spec 002.7 agregue tracking |
| Relax HMM+CVD gates puede generar señales malas en stocks futuros | BARRIDA solo activo en VERDE_BULL_DORMANT + cluster específico + drop≥2% — triple gate restrictivo |
| Endpoint sin SP500 real → fallback 7000 puede mentir | Documentar en JSON response field `source: "spy_proxy" | "default"` |

## Criterio de aceptación

1. `python3 -m py_compile strategies.py app.py regime_transitions.py` → OK
2. Smoke `import regime_transitions; print(regime_transitions.get_state_summary())` → dict válido (o `{"status": "no_data"}` si primer run)
3. Smoke `regime_transitions.get_cluster_for_symbol("UUUU")` → `"nuclear"`
4. Smoke `regime_transitions.get_cluster_for_symbol("BTC")` → `None`
5. V3-REVERSAL alert con ticker explosivo post-transition → log boost `⭐ ... EXPLOSIVE_CORRECTION` visible
6. V3-REVERSAL en BARRIDA active + cluster match → log `⚡ ... BARRIDA_OPPORTUNITY active — relajando` visible
7. `GET /api/metrics/regime_transitions` → 200 con keys `current_regime`, `transition`, `explosive_tickers`, `barrida_clusters`
