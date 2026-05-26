# Spec 007 — Liquidity Sweeps Detection + Tag en V3-Reversal

> **Status:** CODE COMPLETE 2026-05-26
> **Created:** 2026-05-26
> **Owner:** Fernando
> **Severity:** P1 — Mes 1 Sem 4 roadmap NotebookLM 4 (commit deployable v1.1)
> **Origen:** `docs/research/notebook-lm-4/RESULTS.md` Prompt 2 (SMC híbrido) + Prompt 6 Spec 008

## Contexto

NotebookLM 4 Prompt 2 veredicto SMC = HÍBRIDO. Recomendó implementar SÓLO Fair Value Gaps + Liquidity Sweeps, no full Smart Money Concepts (BOS/CHoCH frágil en Python puro).

Spec 007 enfoca el sub-set "Liquidity Sweeps" — detección matemática simple de swing highs/lows previos cruzada con macro gate dinámico actual.

Una "sweep" ocurre cuando el precio rompe momentáneamente swing_high/low previo (wick) pero cierra de vuelta dentro del rango. Clásica trampa de stops + huella de Smart Money capturando liquidez. Combinable con macro VERDE_BULL_DORMANT (VIX<22 + SP500>7000) para confirmar oportunidad de entrada.

## Goals

1. Función `indicators.detect_liquidity_sweep(symbol, timeframe, lookback)` que retorna dict con `swept_high/swept_low/swing_high_level/swing_low_level/current_high/current_low/current_close`.

2. Wire en `strategies.py:V3-REVERSAL`: si `swept_low` detectado en momento de alert LONG, agregar tag visual `🌊 SWEEP LOW activo` al mensaje Telegram con el nivel exacto que rompió.

3. Cero gating — solo enriquecimiento visual de la alerta. Mantiene compatibilidad full con flow actual.

## Non-goals

- Fair Value Gaps (FVG) — Spec 008 candidato (también NotebookLM-recommended pero más complejo)
- BOS / CHoCH / Order Blocks — descartados por NotebookLM (frágil + ruidoso)
- Wire en V2-AI / SWING / V4 — solo V3-Reversal este spec
- Sweep como GATE (bloquear si no hay sweep) — solo tag visual, no decisión

## Dependencias

- `indicators.get_df(symbol, timeframe, limit)` ✅ ya existe
- pandas DataFrame con columnas `high/low/close` ✅
- `strategies.py:V3-Reversal msg builder` ✅ modificar

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| `get_df` cache miss en cada V3 alert → API extra cost | `get_df` ya tiene cache TTL. V3 alerts son pocos por hora — overhead negligible. |
| `detect_liquidity_sweep` falla por columna missing en df | Try/except envuelve la llamada en strategies. Skip tag silent en error. |
| Tag genera ruido visual si TODAS las V3 alerts tienen swept_low | Solo se agrega si swept_low=True. Si es 100% de las alerts, indica que lookback=20 es muy permissivo — tunear a 40. |
| Sweep en 1h timeframe es muy short-term para uso macro | Lookback=20 velas = 20h = ~1 día de contexto. Aceptable para intraday V3. |

## Criterio de aceptación

1. `python3 -m py_compile indicators.py strategies.py` → OK
2. AST: `detect_liquidity_sweep` definida en indicators.py
3. AST: strategies.py llama `detect_liquidity_sweep` + tiene variable `_sweep_tag`
4. Production deploy: si V3 alert dispara con swept_low detectado, mensaje Telegram inicia con `🌊 SWEEP LOW activo`
5. Si V3 alert dispara sin sweep, mensaje normal (sin línea sweep)
