# Spec 008 — Fair Value Gaps (FVG) Detection

> **Status:** CODE COMPLETE 2026-05-26
> **Owner:** Fernando
> **Severity:** P1 — Mes 2 Sem 6 roadmap NotebookLM 4 (anticipado)
> **Origen:** `docs/research/notebook-lm-4/RESULTS.md` Prompt 2 (SMC híbrido) + Prompt 6 Spec 010

## Contexto

NotebookLM 4 Prompt 2 veredicto HÍBRIDO sobre SMC: implementar Fair Value Gaps + Liquidity Sweeps. Spec 007 cubrió Sweeps. Spec 008 cubre FVG — el segundo componente del bundle SMC útil.

Un FVG es un patrón de 3 velas donde la vela central deja un "gap" entre la high de la anterior y la low de la siguiente (o inverso). Los FVG no rellenados actúan como **imanes de precio** — el precio tiende a regresar a llenar el gap. Si nearest_bullish_top está entre TP1 y TP2 de un setup V3-Reversal LONG, es razonable considerar el FVG como target intermedio probable.

## Goals

1. `indicators.detect_fair_value_gaps(symbol, timeframe, lookback, max_gaps)` retorna dict con `bullish_fvgs`, `bearish_fvgs`, `nearest_bullish_top`, `nearest_bearish_bot`, `current_price`.

2. Filtrado de FVG ya rellenados (si vela posterior tocó el gap, se descarta).

3. Wire en `strategies.py:V3-REVERSAL`: si `nearest_bullish_top` cae entre TP1 (ATR-based) y TP2, tag visual `🎯 FVG imán @ $X.XX (entre TP1 y TP2 — target probable)`.

4. NO override de TP1/TP2 ATR-based — solo enriquecimiento informativo.

## Non-goals

- Ejecución parcial close en FVG target — solo TAG visual en alert
- BOS / CHoCH / Order Blocks — descartados NotebookLM (frágil)
- Wire en V2-AI/V4/SWING — solo V3-Reversal este spec
- FVG en stocks NYSE — solo cripto por ahora (NotebookLM SMC research = cripto)

## Dependencias

- `indicators.get_df()` ✅
- pandas DataFrame con `high/low/close` ✅
- `strategies.py:V3-Reversal msg builder` ✅

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Algoritmo O(N²) por inner loop de filter de rellenado | lookback=30 con max_gaps=3 → 30 × 30 = 900 ops max. Negligible. |
| FVG falso por baja liquidez en cripto small caps | Solo cripto majors en bot (BTC/ETH/SOL/ZEC/TAO). Baja prob de noise. |
| Tag de "target probable" puede confundir si FVG falla | Mensaje explicito "entre TP1 y TP2 — target probable" (no "garantizado") |
| Backlog de FVG no rellenados acumula y degrada signal/noise | max_gaps=3 limita a los 3 más recientes |

## Criterio de aceptación

1. `python3 -m py_compile indicators.py strategies.py` → OK
2. AST: `detect_fair_value_gaps` en indicators, called desde strategies
3. Variables `_fvg_tag`, `_fvg_target` en strategies V3-REVERSAL block
4. msg V3-Reversal contiene `{_fvg_tag}` justo después de `{_sweep_tag}`
5. Production deploy: próximas alerts V3 LONG con nearest_bullish_top válido → Telegram msg muestra línea 🎯 FVG imán
