# Plan 016 — V3 Multi-Gate Hooks

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Estrategia

Batch wire de 3 specs standalone (009 HMM + 012 CVD + 013 Social) a V3-REVERSAL en un solo commit. Cada gate envuelto en try/except — failure de uno no afecta otros.

## Decisiones técnicas

### 1. Por qué wire en V3-REVERSAL solamente

V3-REVERSAL es la estrategia más sensible a "cuchillos cayendo" (entra en RSI extremo). Los 3 gates atacan exactamente ese caso:
- HMM STRONG_TREND → no entrar contra tendencia
- CVD BEARISH → smart money sale, no compres
- Social EUPHORIA → fade crowd, top probable

V2-AI, V4, SWING, COMMODITY tienen filtros propios y no son reversal plays.

### 2. Orden early-exit barato → caro

```
funding (local data)
  ↓
HMM (local fit, ~100-500ms)
  ↓
CVD (Binance API, cached 60s)
  ↓
Social (Reddit+Trends API, cached 30min)
  ↓
register_signal_event → calculate_confluence_score → AI consensus
```

Razón: si el gate más barato bloquea, evitamos las llamadas caras. Salvataje computacional + de presupuesto API.

### 3. Try/except por gate

Cada gate envuelto independiente:
```python
try:
    import regime_hmm
    _hmm = regime_hmm.detect_regime(...)
    if _hmm.get("regime") == "STRONG_TREND":
        print(f"⏸️ ...")
        continue
except Exception:
    pass
```

Si `hmmlearn` no está instalado → import falla → `except pass` → gate inactivo, alerta normal. Cero crash.

### 4. Logs visibles distintivos

Cada gate loguea con prefijo claro:
- `⏸️ [V3-Reversal] {sym}: funding ...`
- `⏸️ [V3-Reversal] {sym}: HMM regime=STRONG_TREND ...`
- `⏸️ [V3-Reversal] {sym}: CVD divergence=BEARISH ...`
- `⏸️ [V3-Reversal] {sym}: Social=EUPHORIA ...`

Permite grep en logs Railway para conteo por gate post-7d:
```bash
railway logs | grep "V3-Reversal" | grep -oE "(funding|HMM|CVD|Social)" | sort | uniq -c
```

### 5. NO gate para BULLISH/FEAR (boost) en este spec

NotebookLM sugirió que FEAR social podría BOOSTEAR confluence (+1) y BULLISH CVD también. PERO eso requiere modificar `calculate_confluence_score` que toca más sites.

Spec 016.5 candidate: agregar boost path después de validar que gates BEARISH no killean demasiadas alerts.

### 6. Social usa `sym.replace("/USDT", "")` porque praw subreddits no incluyen "/USDT"

`social_quant._SUBREDDITS_BY_SYMBOL` mapea por ticker pelado (BTC, ETH, ZEC, TAO).

## Verificación

- ✅ py_compile strategies.py
- ✅ regime_hmm, cvd_segmented, social_quant imports en src
- ✅ STRONG_TREND, BEARISH, EUPHORIA literals en src
- Producción pendiente 7d: medir bloqueos por gate

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(v3): spec-016 multi-gate hooks — HMM + CVD + Social wired to V3-REVERSAL` |

## Tuning plan post-7d

Métricas a observar via Railway logs:
- Conteo bloqueos por gate por símbolo por día
- % alerts V3 que pasan todos los gates (espero 30-60%, no 0%)
- WR de alerts que pasan (espero >40%, vs 22.4% baseline LONG)

Acciones:
- Si gate X bloquea >70% alerts → tunear threshold (subir/bajar)
- Si combinación bloquea 100% alerts por 3+ días → desactivar el más restrictivo
- Si WR mejora >10pp → mantener configuración + considerar wire en V2-AI

## Backlog Spec 016.5+

- Boost confluence con BULLISH CVD + FEAR social (en lugar de solo gates BEARISH)
- Métricas por gate persistidas en SQLite (no solo logs)
- Dashboard Spec 015 mostrar gate stats
- Wire selectivo a V2-AI swing (RSI menos extremo, gates más permissivos)
