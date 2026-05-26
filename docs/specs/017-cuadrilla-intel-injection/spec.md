# Spec 017 — Cuadrilla Zenith Intel Injection (HMM + CVD + Social)

> **Status:** CODE COMPLETE 2026-05-26
> **Owner:** Fernando
> **Severity:** P1 — wire intel modules a Cuadrilla Zenith prompt
> **Origen:** Roadmap Spec X.5 backlogs + Spec 016 (gates) follow-up

## Contexto

Spec 016 cableó HMM + CVD + Social como GATES en V3-REVERSAL. Si alguno disparaba kill condition → skip alert. Si pasaban todos → la alerta se enviaba PERO los datos en vivo (régimen RANGE, CVD whale +$45k, social NEUTRAL) se descartaban.

Spec 017 los preserva y los inyecta como **bloque "INTEL EN VIVO"** en el prompt de Cuadrilla Zenith Debate. Las 4 voces (Genesis/Exodo/Salmos/Apocalipsis) ahora ven el contexto real y pueden referenciarlo en sus 12 palabras.

Mapeo:
- HMM régimen → Salmos (confluencia técnica)
- CVD whale/retail → Genesis (capital institucional)
- Social Reddit/Trends → Exodo (narrativa)
- Apocalipsis sigue con FOMC + risk_pulse (Spec 014.5 candidato wire grounded_search)

## Goals

1. Helper `_format_extra_intel(intel: dict) -> str` en `gemini_analyzer.py`:
   - Recibe dict con keys opcionales (hmm_regime, cvd_signal, social_signal, etc)
   - Retorna bloque texto formatado con header "📡 INTEL EN VIVO ..."
   - String vacío si dict vacío/None
2. Modificar signature `get_ai_consensus(..., extra_intel: dict | None = None)` — backwards compatible
3. Inyectar bloque entre `FOMC_CONTEXT` y `risk_ctx` en el prompt
4. En `strategies.py:V3-REVERSAL`:
   - Guardar `_hmm`, `_cvd`, `_social` refs (mod del Spec 016 que descartaba)
   - Construir `_extra_intel` dict con los datos que pasaron gates
   - Pasar a `get_ai_consensus(..., extra_intel=_extra_intel)`

## Non-goals

- Wire en otras 3 calls de `get_ai_consensus` (V2-AI, V4, SWING) — solo V3 este spec
- Inyectar a `get_sentinel_report_compact` — Sentinel ya tiene su propio prompt, scope separado
- Grounded search a Apocalipsis (Spec 014.5)
- Whale netflows a Genesis (Spec 010.5) — pendiente, requiere fetch onchain en V3 loop
- FVG/Sweep tags ya están como tags visuales (Spec 007/008), no necesitan ir al prompt

## Dependencias

- `regime_hmm.detect_regime` ✅ (Spec 009)
- `cvd_segmented.compute_cvd_segmented` ✅ (Spec 012)
- `social_quant.get_social_sentiment` ✅ (Spec 013)
- `gemini_analyzer.get_ai_consensus` (modificar signature)

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| `_extra_intel` puede crecer mucho y consumir tokens prompt | Solo claves con datos válidos se incluyen. Sin claves → bloque vacío |
| Voces ignoran el INTEL EN VIVO block | Header explícito + instrucción "úsalos para refinar opinión" |
| Breaking change si llaman get_ai_consensus sin kwarg | `extra_intel: dict | None = None` default — 100% backwards compatible |
| Strategies que NO pasan gates HMM/CVD/Social no llegan a este punto | Correcto. Los gates Spec 016 ya filtraron |
| `_format_extra_intel(None)` debe retornar "" sin crash | Test: `if not intel: return ""` |

## Criterio de aceptación

1. `python3 -m py_compile gemini_analyzer.py strategies.py` → OK
2. Smoke `_format_extra_intel`:
   - `None` → `""`
   - `{}` → `""`
   - Full dict → bloque con header + 3 líneas + newline
   - Partial dict (solo HMM) → bloque con header + 1 línea
3. `get_ai_consensus(..., extra_intel=None)` funciona igual que antes (backwards compat)
4. `get_ai_consensus(..., extra_intel={...})` inyecta el bloque al prompt
5. Producción pendiente: próxima alerta V3 → Telegram muestra debate con voces refiriéndose al INTEL EN VIVO
