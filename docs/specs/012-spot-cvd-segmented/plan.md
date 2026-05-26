# Plan 012 — Spot CVD Segmentado

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Decisiones técnicas

### 1. Procesamiento síncrono sin pandas

Los 1000 trades de Binance fit en memoria fácilmente como list[dict]. Loop simple Python > pandas DataFrame para volumen tan pequeño. Cero dependencia extra.

### 2. Bucket thresholds en módulo, no config.py

```python
RETAIL_MAX_USD = 1_000.0
WHALE_MIN_USD = 100_000.0
CVD_DIVERGENCE_MIN_USD = 50_000.0
CVD_CACHE_TTL = 60
```

Razón: estos son números técnicos derivados de la metodología NotebookLM (líneas amarilla/naranja/marrón), no parámetros de negocio. Si validamos en producción y cambian, Spec 012.5 los moverá a config.

### 3. side="buy"/"sell" semantics

ccxt convención: `side` del trade = lado del **taker** (agresor que cruzó el spread).
- `side="buy"` → taker compró a precio market (alguien aceptó la ask)
- `side="sell"` → taker vendió a precio market (alguien aceptó la bid)

CVD = sum(buy_cost) - sum(sell_cost) = positive cuando taker dominante es comprador → presión alcista.

### 4. Threshold divergence = $50k

Más bajo que el bucket whale ($100k) pero mayor que mid average. Lógica: una divergencia es accionable cuando AMBOS lados (retail + whale) acumulan magnitud significativa. $50k es threshold conservador inicial.

Tuning: Spec 012.5 puede subir threshold si false positives en producción.

### 5. Cache 60s

Trades son volátiles — pero el CVD agregado de 1000 trades no debería cambiar dramáticamente en 60s para activos líquidos (BTC/ETH).

Para activos menores (ZEC/TAO) 1000 trades pueden cubrir varias horas — cache 60s = sobra.

### 6. Empty dict on failure pattern

Consistencia con Spec 007/008/009/010/013/014: caller decide fallback. Nunca raise.

### 7. format_cvd_summary helper

Función companion que retorna string compacto:
```
"CVD 1000 trades · WHALE +$45,000 · RETAIL -$12,000 · signal=BULLISH"
```

Pensado para inyectar en prompts de Cuadrilla Zenith (voz Genesis o Salmos) en Spec 012.5. Tener el helper listo evita que el caller tenga que conocer la estructura del dict.

## Verificación

- ✅ py_compile cvd_segmented.py
- ✅ Bucket classification 3 tiers
- ✅ Divergence BEARISH/BULLISH/NEUTRAL
- ✅ format_cvd_summary output legible
- ✅ Empty dict graceful sin exchange_singleton

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(intel): spec-012 spot CVD segmented — buckets retail/mid/whale + divergence detection` |

## Backlog Spec 012.5

- Wire en Cuadrilla Zenith voz Genesis: inyectar `format_cvd_summary` al prompt para BTC/ETH/SOL/ZEC/TAO. Razón: voz Genesis = "capital institucional".
- Wire en `strategies.py:V3-REVERSAL`:
  - BEARISH CVD divergence + V3 LONG candidate → skip (top probable, no entrar a cuchillo)
  - BULLISH CVD divergence + V3 LONG candidate → boost confluence_score +1 (bottom confirmation)
- Telegram command `/cvd SYMBOL` para inspección manual
- Mover thresholds a `config.py` si validado en producción

## Backlog Spec 012.6

- Multi-window CVD (1h vs 4h) para confirmar tendencia
- CVD por exchange (Binance vs Coinbase) — divergencia exchange-to-exchange
- Alerta cuando CVD whale + RSI extremo coinciden (señal compuesta)
