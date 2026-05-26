# Plan 006 — Funding Rate Filter para V3-Reversal

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Estrategia

Cambio quirúrgico. Una constante en `config.py` + 10 líneas de gate en `strategies.py:497` (post-RSI trigger, pre-signal). Cero riesgo de regresión — si funding_data no está disponible, fallback al comportamiento previo (allow).

## Decisiones técnicas

### 1. Threshold = 30% en lugar de 10% (NotebookLM)

NotebookLM 4 Prompt 3 recomendó "10% anualizado persistente". Empiezo en **30%** conservador.

Razón:
- Funding rates en cripto suben fácil a 10-20% en momentum normal sin ser latigazo.
- WR del bot V3 es ya pésimo (0% para SHORT, 22.4% LONG global) — no podemos darnos el lujo de killear 80% de alerts V3 sin validar.
- Plan: si 7 días en producción bloquea <10% de V3 alerts, bajar threshold a 20%. Si bloquea >50% alerts, subir a 50% o quitar gate.

### 2. Gate solo V3-REVERSAL, NO V2/V4/SWING/COMMODITY

NotebookLM específicamente mencionó V3-REVERSAL como vulnerable a latigazos. Otras estrategias:
- V2-AI: tiene macro_bias + Cuadrilla Zenith → ya tiene protección
- V4: blocklist ETH/ZEC ya activo
- SWING: ichimoku + EMA50 ya filtra
- COMMODITY: backtested 53-61% WR

V3-REVERSAL es el RSI extreme play (≤30 o per-symbol). Es el más propenso a "cuchillos cayendo" — caso exacto donde funding elevado predice volatilidad adversa.

### 3. Gate ANTES de `register_signal_event` + `calculate_confluence_score`

Razón: si el gate bloquea, no incrementamos contadores ni hacemos cálculos AI costosos. Skip clean.

### 4. Logging visible

```python
print(f"⏸️ [V3-Reversal] {sym}: funding {_funding_ann:.1f}% > {_FRB}% — bloqueando (latigazo volatilidad inminente)")
```

`print` en lugar de `logger.info` por consistencia con otros gates del archivo (`⏸️ [HourFilter]`, `⏸️ [Position Guard]`, etc.). Visible en Railway logs para tuning.

### 5. Try/except fallback

```python
try:
    from config import FUNDING_REVERSAL_BLOCK_ANNUALIZED as _FRB
    ...
except Exception:
    pass  # fallback al comportamiento previo
```

Razón: si `funding_data` cache está vacío (Binance API hiccup), no queremos bloquear todas las alerts V3. Fallback = allow. NotebookLM gate prioritiza false negatives (perder oportunidad) > false positives (entrar a latigazo).

## Implementación

### config.py (línea 393, después de `FUNDING_EXTREME_SHORT`)

```python
FUNDING_REVERSAL_BLOCK_ANNUALIZED = 30.0  # % anualizado. > threshold = skip V3 reversal.
```

### strategies.py (línea 497, dentro de `if rsi <= reversal_rsi:`)

```python
if rsi <= reversal_rsi:
    # Spec 006: Funding Rate gate
    try:
        from config import FUNDING_REVERSAL_BLOCK_ANNUALIZED as _FRB
        _sym_funding = (funding_data or {}).get(sym, {})
        _funding_ann = _sym_funding.get("annualized", 0.0)
        if _funding_ann > _FRB:
            print(f"⏸️ [V3-Reversal] {sym}: funding {_funding_ann:.1f}% > {_FRB}% — bloqueando ...")
            continue
    except Exception:
        pass
    register_signal_event(...)
    ...
```

## Verificación

Smoke tests pasados:
1. ✅ `python3 -m py_compile config.py strategies.py`
2. ✅ Constante `FUNDING_REVERSAL_BLOCK_ANNUALIZED = 30.0` importable
3. ✅ Dispatcher 5 casos: 5%/35%/30.1%/29.9%/missing → allow/block/block/allow/allow

Verificación producción pendiente (próxima alerta V3 reversal).

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(v3): spec-006 funding rate filter — block V3 reversal if annualized > 30%` |

## Tuning plan

Después de 7 días en producción:
- Si bloqueo < 10% V3 alerts → bajar a 20%
- Si bloqueo 10-30% V3 alerts → mantener 30%
- Si bloqueo > 50% V3 alerts → subir a 50% o evaluar quitar gate
- Si V3 WR mejora >5pp → mantener gate, considerar gate también en V4

Spec 007 siguiente: Liquidity Sweeps (FVG matemático).
