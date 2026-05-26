# Plan 007 — Liquidity Sweeps

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Estrategia

Función nueva en `indicators.py` + tag visual en `strategies.py:V3-Reversal`. Cero gating. Cero side-effects en otras estrategias.

## Decisiones técnicas

### 1. Detección matemática simple (no full SMC)

NotebookLM recomendó NO implementar BOS/CHoCH/Order Blocks porque son frágiles en Python puro. Sólo Fair Value Gaps + Liquidity Sweeps son matemáticos limpios.

Liquidity Sweep algorithm:
```python
previous = df.iloc[-(lookback+1):-1]  # excluye la vela actual
swing_high = previous['high'].max()
swing_low = previous['low'].min()
swept_high = current['high'] > swing_high and current['close'] <= swing_high
swept_low = current['low'] < swing_low and current['close'] >= swing_low
```

- `swept_high`: precio wickeó arriba pero cerró debajo → falla del breakout, posible reversal SHORT.
- `swept_low`: precio wickeó abajo pero cerró encima → falla del breakdown, posible reversal LONG.

Tiempo de cómputo: O(N) donde N = lookback. Para lookback=20 = 20 comparisons. Negligible.

### 2. Solo V3-Reversal en este spec

Razón: V3-Reversal entra en RSI extremo (típicamente bajo, LONG en oversold). Si en ese momento hay swept_low confirmado, es exactly la confluencia que Daniel PTS llama "agotamiento + smart money huella".

No wire en V2-AI/V4/SWING/COMMODITY este spec porque:
- V2-AI ya tiene Cuadrilla Zenith
- V4 está en blocklist ETH/ZEC ya
- SWING usa Ichimoku + bias semanal
- COMMODITY backtested separadamente

Spec 007.5 candidato: extender wire a V2-AI swing entries cuando se valide V3 en prod.

### 3. Lookback = 20 velas en 1h timeframe

Lookback corto suficiente para captar swing reciente sin contaminar con structura macro. 20h ≈ 1 día de contexto intraday.

Alternativas consideradas:
- lookback=50 (mayor contexto, más raro de detectar) — backlog tuning
- timeframe=15m (más sensible) — backlog
- Multi-TF (sweep en 1h + confirmación 4h) — Spec 008 candidato

### 4. Tag visual prepended, no afecta lógica

```python
msg = (
    f"🏛️ ... SEÑAL V3 ...\n\n"
    f"{_sweep_tag}"   # <-- vacío si no hay sweep
    f"🌊 Onda: {elliott}\n"
    ...
)
```

Cero impacto en `_store_pending`, `_tc`, `_em.log_alert_episode`, etc. Solo el mensaje Telegram cambia.

### 5. Try/except envuelve la detección

```python
try:
    _sweep = indicators.detect_liquidity_sweep(sym, "1h", 20)
    ...
except Exception as _e:
    print(f"[V3-Reversal] {sym} sweep detect skip: {_e}")
```

Si detect falla (API hiccup, df vacío, columna missing), V3 alert sigue su flujo normal sin tag. Cero regresión.

## Verificación

- ✅ `python3 -m py_compile indicators.py strategies.py`
- ✅ AST: `detect_liquidity_sweep` en indicators
- ✅ AST: strategies llama función + tiene `_sweep_tag`
- Producción pendiente: próxima alerta V3-Reversal → log de detección + mensaje con/sin tag.

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(indicators): spec-007 liquidity sweeps detection + V3 tag` |

## Tuning post-7d

- Si tag aparece en <20% de V3 alerts → bueno, captura caso especial
- Si tag aparece en >80% V3 alerts → lookback=20 muy permissivo, subir a 40
- Si V3 alerts con tag tienen WR significativamente mejor → considerar boost en confluence_score
- Si V3 alerts con tag tienen WR igual o peor → revisar algoritmo o ampliar lookback

Spec 008 siguiente candidato: Whale Netflows on-chain Etherscan API (Mes 2 Sem 7 roadmap).
