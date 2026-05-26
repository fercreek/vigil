# Spec 002.5 — Regime Transitions (EXPLOSIVE_CORRECTION + BARRIDA_OPPORTUNITY)

> **Status:** CODE COMPLETE 2026-05-26 (MVP)
> **Owner:** Fernando
> **Severity:** P1 — NotebookLM 4 Prompt 5 filtros pending
> **Origen:** NotebookLM 4 Prompt 5 + Plan Sprint 2

Nota: numbered 002.5 porque Spec 002 fue el audit alert-noise. Esto es el siguiente backlog item de ese spec, ahora consolidado en módulo standalone.

## Contexto

NotebookLM 4 Prompt 5 sugirió 2 filtros macro-state-aware:

1. **EXPLOSIVE_CORRECTION**: cuando régimen SP500 transitionó AMARILLA→VERDE, boost
   alerts long de tickers explosive (RKLB, HOOD, ASTS, IONQ-tier). Patrón histórico:
   beta-alta tras corrección recuperan +30%/sem post macro confirmation.

2. **BARRIDA_OPPORTUNITY**: en VERDE_BULL_DORMANT (VIX<22 + SP500>7000), caídas
   intradía en ai_infra/nuclear son re-entradas, no breaks. NO filtrar por stops
   rígidos, alertar como oportunidad.

Spec 002.5 implementa state machine + helpers + wire MVP en stock_analyzer.

## Goals

1. Módulo standalone `regime_transitions.py`:
   - `get_current_macro_state(sp500, vix)` → VERDE_BULL / VERDE_BULL_DORMANT / AMARILLA_INDECISA / NARANJA_BEAR / UNKNOWN
   - `detect_transition(sp500, vix)` → detecta cambio vs previous state, persiste a JSON
   - `is_explosive_correction_setup(ticker, sp500, vix)` → True si AMARILLA→VERDE reciente + ticker en EXPLOSIVE_TICKERS
   - `is_barrida_opportunity(cluster, sp500, vix, drop_pct)` → True si VERDE_BULL_DORMANT + cluster ai_infra/nuclear + caída ≥2%
   - `get_state_summary()` para dashboard/telemetría

2. Persistencia: `data/macro_state.json` con previous/current/since_ts. Sobrevive Railway restarts.

3. Wire MVP en `stock_analyzer.py:stock_watchdog` ENTRY_ALERT:
   - Tag `⚡ EXPLOSIVE_CORRECTION` cuando setup activo para el ticker

## Non-goals

- Wire BARRIDA_OPPORTUNITY en strategies.py V3-REVERSAL — Spec 002.6 (requiere refactor de los gates Spec 016 para considerar barrida override)
- Boost confluence cuando EXPLOSIVE_CORRECTION (Spec 021 extension)
- Endpoint `/api/metrics/regime_transitions` — Spec 002.7
- Auto-update SPY/VIX cada N ciclos del bot — el state se actualiza al llamar las helpers
- Backtest histórico de los 2 filtros — Spec 002.8 (requiere replay datos)

## Dependencias

- `config.SP500_VERDE_THRESHOLD`, `SP500_NARANJA_THRESHOLD`, `VIX_DORMANT_THRESHOLD` ✅ (Spec 004)
- `logger_core.logger` ✅
- `stock_analyzer.py:stock_watchdog` ✅

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| State file corrupted → no detection | try/except + retorno {} → re-grabba en próximo call |
| Threshold régimen vs realidad muy ajustada | Constantes en config (Spec 004), tunable |
| EXPLOSIVE_TICKERS hardcoded → no se actualiza | Spec 002.6 candidato: leer de config.DEFENSIVE_SECTORS o spec dict |
| SP500 price proxy via SPY × 10 (NO oficial) | OK como aproximación; Spec 002.6 puede pasar SP500 real de spy_data |
| Transition detected en cada ciclo (oscila 6999↔7001) | since_ts solo se actualiza si current != previous. Mismo régimen = no spam |
| Barrida intraday_drop_pct requires real-time tracking (no implementado) | Spec 002.6 backlog. MVP solo expone helper, no wire |

## Criterio de aceptación

1. `python3 -m py_compile regime_transitions.py stock_analyzer.py` → OK
2. `get_current_macro_state(7100, 16)` → "VERDE_BULL_DORMANT"
3. `get_current_macro_state(6900, 20)` → "AMARILLA_INDECISA"
4. `get_current_macro_state(6700, 30)` → "NARANJA_BEAR"
5. `detect_transition` con previous distinto → is_bullish_transition o is_bearish_transition correcto
6. `is_explosive_correction_setup("RKLB", 7100, 16)` luego de transition AMARILLA→VERDE → True
7. `is_barrida_opportunity("ai_infra", 7100, 16, 3.5)` → True
8. Stock ENTRY_ALERT con explosive ticker post-transition muestra tag `⚡ EXPLOSIVE_CORRECTION`
9. Producción: file `data/macro_state.json` se crea, sobrevive restart
