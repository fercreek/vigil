# Plan 021 — V3 Confluence Boost

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Decisiones técnicas

### 1. Boost positivo only (no penalty)

Filosofía: los gates (Spec 016/019) ya filtran negativos. Boost = recompensa confluencia adicional positiva. Doble penalty (gate + score penalty) sería overkill.

### 2. Valores: +1.0 / +0.5

- **+1.0**: signals que indican capital flow directo (CVD whales acumulan, retail vende, Whale outflow)
- **+0.5**: HMM RANGE — contexto, no señal directa de flujo

NotebookLM 4 Prompt 5 sugirió +1pp para BULLISH CVD + Whale + FEAR. Half boost para RANGE refleja menor weight.

Max teórico = +3.5 (ETH con todos signals alineados).

### 3. Boost POST-gates, pre-msg

Order en V3-REVERSAL block:
```
gates (Spec 016/019) → continue si bloqueo
register_signal_event → side="LONG"
funding_signal + calculate_confluence_score
+social_adj
+_boost (Spec 021) ← AQUÍ
sl_dist + tp1 + tp2
FVG tag + Sweep tag
msg build con conf_score final
```

Razón: el boost debe afectar el score que se muestra en el alert. Boost antes del msg.

### 4. Log único por alert con boost

```python
if _boost > 0:
    print(f"⭐ [V3-Reversal] {sym}: boost +{_boost:.1f} ({reasons}) → conf_score={conf_score:.2f}")
```

Solo logueamos si hay boost (evita spam de "boost +0"). Grep en Railway para conteo:
```bash
railway logs | grep "⭐ \[V3-Reversal\]" | wc -l
```

### 5. NO override de MIN_CONFLUENCE_SCORE

Bot ya tiene `MIN_CONFLUENCE_SCORE = 5` en config.py. Si conf_score base = 4 + boost = +2 → conf_score=6 pasa el filtro de envío.

Esto es por design: boost ayuda alerts borderline a pasar (alerts que con baseline serían skipped por score=4 ahora pasan con score=6 gracias a confluencia signal).

### 6. Display en HTML/Telegram

`format_confidence(conf_score)` ya usado en msg V3 → mostrará el score boosted. Trader ve "Confiabilidad: ⭐⭐⭐⭐⭐⭐ (6/10)" en lugar de "⭐⭐⭐⭐ (4/10)".

## Verificación

- ✅ py_compile strategies.py
- ✅ Bloque "Spec 021" presente después de social_adj
- ✅ Log condicional `if _boost > 0`

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(v3): spec-021 confluence boost — BULLISH/FEAR signals premiados +0.5 a +1.0` |

## Tuning post-7d

Métricas a observar:
- Distribución conf_score V3 alerts (baseline vs post-boost)
- WR V3 alerts boost > 0 vs WR V3 alerts boost = 0
- ¿Boost +3.5 (max) coincide con winners?

Acciones:
- Si V3 boost > 0 tiene WR significantly mejor → mantener
- Si distribución uniforme (boost no diferencia) → ajustar pesos
- Si boost +3.5 nunca → relajar conditions (HMM RANGE → cualquier no-TREND)

## Backlog Spec 021.5

- Penalty signals para V3 (CVD NEUTRAL + Social NEUTRAL = -0.5 vs baseline)
- Boost selectivo por símbolo (ETH whale boost mayor que TAO sin tracking)
- Boost dinámico ML (RL training de pesos)
- Wire boost a V2-AI/V4/SWING (más conservador, +0.5 only)
- Dashboard endpoint `/api/metrics/boost_stats` (Spec 015.5 candidato)
