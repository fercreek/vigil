# Plan 002.6 — Wire BARRIDA + EXPLOSIVE en V3-REVERSAL + endpoint

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Decisiones técnicas

### 1. Helper `get_cluster_for_symbol` en `regime_transitions.py` (no en strategies)

Razones:
- Lookup reverso de SECTOR_CLUSTERS reutilizable (V3 ahora, V2/V4/SWING futuro)
- Mantiene `regime_transitions.py` como home único de toda la lógica régimen
- Si config.SECTOR_CLUSTERS no importable (test env), fallback `{}` → returns None safe

### 2. Boost +1.5 para EXPLOSIVE vs +1.0 para CVD/Social/Whale

EXPLOSIVE es setup raro (requiere transición macro reciente). Cuando matches, es señal de mayor convicción que un single intel signal. +1.5 lo coloca above CVD/Social/Whale individuales pero below combo de 2-3 signals (que pueden sumar +2.5-3.0).

Alternativa rechazada: +2.0. Demasiado disruptivo en confluence cap (max=7 ya saturado fácil con HMM+CVD+EXPLOSIVE).

### 3. BARRIDA relax: NO bloquear HMM+CVD, SÍ funding+Social

Funding = señal de volatilidad LIQUIDATION inminente (latigazos). BARRIDA es relax DE STOPS HISTÓRICOS, no de risk management de derivados.

Social EUPHORIA = top retail, NO sirve relax (BARRIDA es bottom-of-correction, no top-of-rally).

HMM STRONG_TREND + CVD BEARISH son los gates que MÁS falsos-positivos generan en barridas verticales (HMM clasifica caída vertical como "trend", CVD detecta venta retail panic).

### 4. Cluster lookup timing — antes de gates

`_barrida_active` se computa UNA vez al inicio del bloque V3-REVERSAL (post `reversal_rsi` check, antes del funding gate). Single function call → reused en todos los gates.

### 5. Endpoint sin auth (consistencia con Spec 020)

Otros `/api/metrics/*` son públicos. Dashboard interno → no requiere auth.

### 6. SP500 source en endpoint — fallback robust

```python
try:
    from scalp_alert_bot import GLOBAL_CACHE
    spy = GLOBAL_CACHE.get("macro_metrics", {}).get("spy", 0.0)
    sp500 = spy * 10 if spy > 0 else 7000.0
    vix = GLOBAL_CACHE.get("macro_metrics", {}).get("vix", 0.0)
    source = "spy_proxy" if spy > 0 else "default"
except Exception:
    sp500 = 7000.0
    vix = 0.0
    source = "default"
```

Endpoint NO debe crashear si bot no inicializado.

### 7. NO modificar `regime_transitions.py` core API

Solo ADD helper `get_cluster_for_symbol`. Spec dice "(only ADD helper si necesario)". No tocamos detect_transition, is_explosive_correction_setup, is_barrida_opportunity, EXPLOSIVE_TICKERS, BARRIDA_CLUSTERS, _STATE_FILE.

## Verificación

- ✅ py_compile 3 archivos
- ✅ Smoke get_state_summary + get_cluster_for_symbol
- ✅ Smoke imports en strategies.py no rompen circular

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(macro): spec-002.6 wire BARRIDA+EXPLOSIVE en V3-REVERSAL + endpoint regime_transitions` |

## Backlog Spec 002.7

- Wire en V2-AI/V4-EMA/SWING (cuando Spec 017.5 extienda intel)
- intraday_drop_pct real-time tracking (5min vs hora actual)
- SP500 via yfinance `^GSPC` (no SPY × 10)
- EXPLOSIVE_TICKERS a config.py
