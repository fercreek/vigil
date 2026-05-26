# Plan 009 — HMM Regime Classifier

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE (module only) 2026-05-26

## Estrategia

Módulo standalone `regime_hmm.py` análogo a `bitlobo_agent.py` (no toca core). Una función pública `detect_regime()` con dependencias mínimas. Sin side-effects — wire-in se hace en Spec 009.5 cuando el módulo esté validado en producción.

## Decisiones técnicas

### 1. `covariance_type="diag"` (no `"full"` ni `"tied"`)

- `"diag"` asume independencia entre features → menos parámetros (3·n_states vs 6·n_states para "full") → menor riesgo de overfit con solo 200 muestras.
- Las 3 features (log_ret, rolling_vol, range_pct) **no son ortogonales** (vol y range están correlacionados), pero `"diag"` ha sido el default en literatura HMM para regime detection (NotebookLM Prompt 4 referencias).
- Spec 009.5 candidato: A/B con `"full"` si convergence estable en 30d.

### 2. 3 estados (no 2 ni 4)

- 2 estados: típico para bull/bear — pierde el modo "squeeze" pre-breakout.
- 4 estados: difícil de mapear semánticamente. Casos degenerados en datasets pequeños.
- 3 estados (TREND / RANGE / SQUEEZE) matchea exactamente el roadmap de Salmos (semáforo verde/amarillo/rojo) y la taxonomía PTS (MACRO PHY trending vs ZR ranging vs barrida volátil).

### 3. Features = log_ret + rolling_std(10) + range_pct

```python
log_ret  = np.log(close / close.shift(1))    # momentum
vol      = log_ret.rolling(10).std()         # volatilidad realizada
rng_pct  = (high - low) / close              # rango intra-vela
```

- log_ret + vol: standard en regime detection (Hamilton 1989, Rydén 1998).
- range_pct: adicional para capturar barridas / wicks (típico crypto). Información de high/low que mean/vol no captura.
- Window=10 para rolling std → ~10h en 1h timeframe, captura volatilidad de corto plazo sin reflejar ruido de 1-2 velas.

### 4. Mapeo state→regime determinista

```python
trend_state    = argmax( mean(log_ret per state) )       # STRONG_TREND
squeeze_state  = argmax( mean(vol per state)  ) entre los restantes  # VOLATILE_SQUEEZE
range_state    = el restante                             # RANGE
```

Razones:
- No usar labels hardcoded (state 0 = TREND) porque hmmlearn no garantiza orden de estados.
- Mean log_ret separa trending (positivo o negativo grande) vs lateral (≈0).
- Mean vol separa squeeze (alta vol, low mean ret) vs range puro (baja vol).
- Determinista con `random_state=42` para reproducibilidad.

### 5. Lookback=200 (default)

- 200 candles en 1h = 8.3 días = ~1 ciclo macro semanal.
- Suficiente para que HMM converja (literatura: 100-500 muestras óptimo).
- Caller puede pasar 100 (corto plazo) o 500 (régimen estructural).

### 6. `training_loss = model.score(features)` = log-likelihood

- HMM no tiene "loss" tradicional → log-likelihood es el equivalente.
- Mayor (menos negativo) = mejor fit. Útil para alarmas si el modelo deja de converger.
- Spec 009.5: si `training_loss < -X` por 3 días → enviar warning Telegram (régimen inestable).

### 7. Empty dict on failure

Patrón consistente con `indicators.detect_fair_value_gaps()` y `detect_liquidity_sweep()`:
- Caller chequea `if not result:` → fallback a comportamiento sin regime
- No raise — bot debe degradar gracefully

### 8. NO cache este spec

- Cache 15min → Spec 009.5 cuando se valide el overhead real en Railway.
- HMM fit 200 candles · 3 features · 3 estados ≈ 100-500ms. Aceptable en loop principal cada 5min.

### 9. Lazy import de `indicators.get_df`

- Permite que `python3 -m py_compile regime_hmm.py` pase sin tener ccxt instalado localmente.
- Patrón ya usado en `telegram_commands.py` (lazy import de `scalp_alert_bot`).

## Verificación

- ✅ py_compile regime_hmm.py
- ✅ AST: `detect_regime`, `_build_features`, `_map_states_to_regimes`
- ✅ requirements.txt contiene `hmmlearn>=0.3.0`
- ✅ Otros archivos del bot intactos

Producción pendiente: Spec 009.5 wire en V3-REVERSAL.

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(regime): spec-009 HMM regime classifier (standalone module + requirements)` |

## Tuning post-7d (Spec 009.5)

- Si `training_loss` estable por símbolo → mapeo deterministic OK
- Si V3-REVERSAL bloqueado por STRONG_TREND ahorra WR ≥5pp → success
- Si > 70% del tiempo es RANGE → 3 estados muy pegados, probar 4 estados
- Si HMM convergence falla > 10% símbolos → reducir features a 2 (log_ret + vol)

## Próximos specs roadmap

- **Spec 009.5** — Hook a `strategies.py:V3-REVERSAL` (gate por regime != STRONG_TREND) + cache 15min
- **Spec 010** — Whale Netflows on-chain Etherscan
- **Spec 011** — Multi-image BitLobo Gemini
- **Spec 012** — Spot CVD Segmentado
