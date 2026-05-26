# Plan 008 — Fair Value Gaps

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Estrategia

Análoga a Spec 007 (sweeps). Función nueva en `indicators.py` + tag visual en `strategies.py:V3-Reversal`. Cero side-effects en otros flows.

## Decisiones técnicas

### 1. Definición matemática FVG (3-bar pattern)

```python
# Vela N-1 (c0), Vela N (c1, ignorada), Vela N+1 (c2)
bullish_FVG = c2.low > c0.high   # gap entre c0.high y c2.low
bearish_FVG = c2.high < c0.low   # gap entre c2.high y c0.low
```

c1 (vela central) ignorada — la condición es 3-bar SMC standard.

### 2. Filtrado de FVG ya rellenados

Inner loop verifica si vela posterior (idx > i+2) tocó el gap:
```python
for j in range(i + 3, n):
    if recent.iloc[j]['low'] <= c0_high:   # bullish FVG llenado
        filled = True; break
```

Solo retorna FVGs NO rellenados (siguen siendo imanes activos).

### 3. nearest_bullish_top vs nearest_bearish_bot

```python
for g in bullish:
    if g["bot"] > current_price:   # FVG está por encima del precio actual
        # candidate como target alcista
```

Solo cuenta como "nearest" si el FVG está fuera del rango actual (above para bullish, below para bearish). Imán de precio = magnetismo donde precio aún no llegó.

### 4. Wire en V3-Reversal: tag solo si FVG entre TP1 y TP2

```python
if tp1 <= _nearest_bull <= tp2:
    _fvg_target = round(_nearest_bull, 2)
    _fvg_tag = f"🎯 FVG imán @ ${_fvg_target:,.2f} (entre TP1 y TP2 — target probable)\n"
```

Razón del filtro `tp1 <= nearest <= tp2`:
- FVG abajo de TP1 → ya pasamos, irrelevante para el setup
- FVG arriba de TP2 → demasiado lejos, no es realistic target intermedio
- FVG entre TP1 y TP2 → sweet spot: realistic + actionable

### 5. NO override de TPs ATR-based

`tp1` y `tp2` siguen calculándose ATR-based. `_fvg_target` es solo INFO visual. Razón:
- Mantener consistencia con risk management actual (ATR-based proven)
- Spec 008.5 candidato: usar _fvg_target como TP1 si pasa validación 7d
- Conservative shift to avoid breaking existing strategy logic

### 6. Lookback=30, max_gaps=3

- 30 velas en 1h = 30h ≈ 1.25 días
- max_gaps=3 evita backlog de FVG viejos contaminando señal

Tunable en backlog.

## Verificación

- ✅ py_compile indicators.py strategies.py
- ✅ AST: detect_fair_value_gaps, _fvg_tag, _fvg_target
- ✅ msg V3 incluye {_fvg_tag}

Producción pendiente: próxima alerta V3 con FVG cumpliendo `tp1 ≤ nearest ≤ tp2`.

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(indicators): spec-008 fair value gaps detection + V3 target tag` |

## Tuning post-7d

- Si tag aparece <10% V3 alerts → bueno, raro pero útil
- Si tag aparece >50% V3 alerts → lookback=30 muy permissivo, subir 40+
- Si V3 alerts con FVG tag tienen WR >5pp mejor → Spec 008.5: override TP1 a FVG nearest
- Si no hay diff de WR → mantener solo informativo

Spec 009 siguiente: HMM Regime Classifier (más complejo, 2-3 días).
