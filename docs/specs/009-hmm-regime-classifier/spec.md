# Spec 009 — HMM Regime Classifier (Salmos Semáforo Maestro)

> **Status:** CODE COMPLETE (module only — hooks pending Spec 009.5) 2026-05-26
> **Owner:** Fernando
> **Severity:** P1 — Mes 2 Sem 7-8 roadmap NotebookLM 4
> **Origen:** `docs/research/notebook-lm-4/RESULTS.md` Prompt 4 (HMM ganador vs RF/SVM/LSTM)

## Contexto

NotebookLM 4 Prompt 4 veredicto: **HMM (Hidden Markov Models)** es el ganador como detector de régimen de mercado. NHHMM logra RMSE volatilidad 0.015. El bot deja de predecir precio → predice **condición** de mercado y prende/apaga estrategias acordemente.

Caso de uso central — **Salmos semáforo maestro**:
- Si HMM detecta `STRONG_TREND` → bloquear V3-REVERSAL (las reversiones fallan en trending limpio).
- Si HMM detecta `RANGE` → habilitar SCALPER + V3-REVERSAL.
- Si HMM detecta `VOLATILE_SQUEEZE` → reducir tamaño de posición, esperar resolución.

Esta spec entrega el módulo `regime_hmm.py` standalone. Wire-in a `strategies.py` queda para Spec 009.5 para evitar romper flujos en una sola sesión.

## Goals

1. `regime_hmm.detect_regime(symbol, timeframe, lookback)` retorna dict con `regime`, `confidence`, `current_state`, `training_loss`, `regime_history_last_10`.
2. 3-state GaussianHMM (`covariance_type="diag"`) sobre features log returns + rolling vol + range pct.
3. Mapeo automático state→regime por mean log return + mean volatility (sin labels hardcoded).
4. Robusto: empty dict `{}` en cualquier fallo (caller decide fallback).
5. Lazy import de `indicators.get_df` para que el módulo sea importable sin ccxt local.
6. `hmmlearn>=0.3.0` añadido a `requirements.txt` (Railway lo instala en deploy).

## Non-goals

- Wire en `strategies.py:V3-REVERSAL` → Spec 009.5
- Wire en `gemini_analyzer.py:FOMC_CONTEXT` voz Salmos → Spec 009.5
- Cache LRU 15min por símbolo → Spec 009.5 (simple, sin cache este spec)
- NHHMM (non-homogeneous) — solo Gaussian estándar este spec
- Backtest histórico de regime classifier — sesión separada
- Cobertura de stocks NYSE — solo cripto (donde el bot tiene minute-level data fluida)
- LSTM híbrido — futuro Spec 011+

## Dependencias

- `hmmlearn>=0.3.0` ✅ (añadido a requirements.txt)
- `numpy`, `pandas` ✅ (ya en stack)
- `indicators.get_df()` ✅ (lazy import dentro de función)

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| HMM convergence falla en datos con poca varianza | try/except alrededor de `model.fit` + return `{}` |
| Mapeo state→regime incorrecto (e.g. STRONG_TREND clasificado como RANGE) | Mapeo determinista por mean log return + mean vol. random_state=42 fijo. |
| Lookback=200 es demasiado corto/largo para 1h | Default razonable (8.3 días). Tunable por caller. Plan: validar en 7d. |
| hmmlearn no disponible localmente (dev) | Flag `_HMMLEARN_AVAILABLE` + import lazy. Módulo importable sin hmmlearn. |
| Latencia de inferencia (~100-500ms) acumula en loop principal | Spec 009.5 añadirá cache 15min para amortizar. |
| Overfitting a régimen reciente (200 candles) | `n_iter=100` razonable. `random_state=42` reproducible. Validación 7d en producción. |

## Criterio de aceptación

1. `python3 -m py_compile regime_hmm.py` → OK
2. AST: `detect_regime`, `_build_features`, `_map_states_to_regimes` definidos
3. Importable sin ccxt instalado (lazy import de `indicators.get_df`)
4. Importable sin hmmlearn instalado (flag `_HMMLEARN_AVAILABLE = False`, devuelve `{}`)
5. `hmmlearn>=0.3.0` en `requirements.txt`
6. NO modificación de otros archivos del bot (strategies/indicators/gemini_analyzer intactos)
7. Producción pendiente Spec 009.5: wire en V3-REVERSAL + log de regime por símbolo
