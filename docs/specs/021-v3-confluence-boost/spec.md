# Spec 021 — V3 Confluence Boost (BULLISH CVD + FEAR Social + Whale + HMM RANGE)

> **Status:** CODE COMPLETE 2026-05-26
> **Owner:** Fernando
> **Severity:** P1 — convertir intel modules de killers a boosters
> **Origen:** Spec 016.5 backlog + NotebookLM 4 Prompt 1

## Contexto

Specs 016 + 019 cablearon HMM/CVD/Social/Whale como GATES — si dispararan kill condition (STRONG_TREND, BEARISH, EUPHORIA, BEARISH whale) → skip alert.

Pero los modules también tienen signals OPUESTOS (BULLISH CVD, FEAR Social, BULLISH Whale, HMM RANGE) que son **confirmaciones de calidad** para V3-Reversal LONG. Hasta ahora estos signals se inyectaban al prompt INTEL (Spec 017) pero NO afectaban el confluence_score.

Spec 021 los convierte en **boosters**: cuando aparecen signals BULLISH/FEAR/RANGE, suman puntos al confluence_score. Las alerts pasan con score mejor y Fernando puede priorizarlas (`MIN_CONFLUENCE_SCORE` queda igual pero alerts con boost destacan).

## Goals

Boost al `conf_score` (calculate_confluence_score + social_adj) en V3-REVERSAL después de pasar todos los gates:

| Signal | Boost | Razón |
|--------|-------|-------|
| CVD `BULLISH` | +1.0 | Ballenas acumulan, retail vende → bottom probable |
| Social `FEAR` | +1.0 | Capitulación retail = oportunidad histórica |
| Whale `BULLISH` (ETH only) | +1.0 | Outflow exchange = whales sacando para hold |
| HMM `RANGE` | +0.5 | Régimen mean-reversion ideal para V3 reversal |

Max boost teórico V3 ETH = +3.5 (todos los signals alineados).

## Non-goals

- Boost negativo (penalty) — solo positivo
- Override de `MIN_CONFLUENCE_SCORE` — alerts siguen requiriendo score mínimo
- Wire a V2-AI / V4 / SWING — solo V3-REVERSAL
- Override del `social_adj` existente del bot
- Boost dinámico (score adaptativo por símbolo) — Spec 021.5 candidato

## Dependencias

- Spec 017 `_extra_intel` builder — datos disponibles
- `_hmm`, `_cvd`, `_social`, `_whale` refs guardadas en V3-REVERSAL block
- `conf_score` ya calculado pre-boost

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Boost +3.5 max puede inflar conf_score above MAX (~10) | Trade-off aceptable. Display "9.5" más informativo que cap arbitrario |
| Boost demasiado generoso → todas alerts inflated | NotebookLM 4 sugiere +1pp en estudios. +1 por signal alineado es conservador |
| HMM RANGE boost +0.5 vs CVD/Social/Whale +1.0 | Razón documented: RANGE es contexto, no señal directa de capital flow. Half boost refleja eso |
| Log spam si boost se loggea cada alert | print solo si boost > 0 (línea única ⭐ por alert) |
| conf_score post-boost > MIN_CONFLUENCE → bypass score gate | OK, ese es el punto: boost ayuda alerts a pasar el gate |

## Criterio de aceptación

1. `python3 -m py_compile strategies.py` → OK
2. AST/grep: bloque "Spec 021" en V3-REVERSAL
3. Boost solo se aplica POST-gates (después de pasar Spec 016 + 019)
4. print log "⭐ [V3-Reversal] {sym}: boost +X.X (razones) → conf_score=Y.YY"
5. Si todos signals NEUTRAL → _boost = 0 → no log
6. Producción pendiente 7d: medir si V3 alerts con boost performan mejor que baseline
