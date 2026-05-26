# Spec 016 — V3-REVERSAL Multi-Gate Hooks (HMM + CVD + Social)

> **Status:** CODE COMPLETE 2026-05-26
> **Owner:** Fernando
> **Severity:** P0 — wire-up de specs 009, 012, 013 (que quedaban standalone)
> **Origen:** Roadmap NotebookLM 4 — Spec X.5 backlogs de 009/012/013 consolidados

## Contexto

Specs 009 (HMM), 012 (CVD), 013 (Social Sentiment) quedaron como módulos standalone con backlog "Spec X.5 — wire al bot". Spec 016 cablea los 3 a V3-REVERSAL en un solo commit coordinado.

Razón de batch único en lugar de 3 specs separados:
- Mismo archivo (`strategies.py:V3-REVERSAL` block)
- Patrón idéntico (try import → check signal → continue if matches kill condition)
- Revertir/rollback más limpio si una falla rompe alerts (1 commit revert vs 3)
- Cada gate es independiente y con try/except graceful — failure de uno no afecta otros

## Goals

3 gates nuevos en `strategies.py:V3-REVERSAL` (post Spec 006 funding gate, pre signal generation):

1. **HMM Regime gate (Spec 009.5):**
   - Llamada `regime_hmm.detect_regime(sym, "1h", 200)`
   - Si `regime == "STRONG_TREND"` → skip + log con confidence
   - Razón: V3 reversal en STRONG_TREND = cuchillo cayendo, sigue cayendo

2. **CVD Segmented gate (Spec 012.5):**
   - Llamada `cvd_segmented.compute_cvd_segmented(sym, 1000)`
   - Si `divergence_signal == "BEARISH"` → skip + log con whale/retail
   - Razón: whales vendiendo + retail comprando = top inminente, no entrar LONG

3. **Social Sentiment gate (Spec 013.5):**
   - Llamada `social_quant.get_social_sentiment(sym.replace("/USDT", ""), 24)`
   - Si `signal == "EUPHORIA"` → skip + log con reddit/trends
   - Razón: fade the crowd, EUPHORIA precede top

## Non-goals

- Wire a voces Cuadrilla Zenith (inyectar contexto al prompt Gemini) — Spec 017 candidato
- Wire a V2-AI / V4 / SWING / COMMODITY — solo V3-REVERSAL este spec
- Boost confluence para signals BULLISH (FEAR social, BULLISH CVD) — implementar después de validar gates BEARISH
- Persistir métricas de bloqueos por gate — Spec 016.5 candidato

## Order del check (early exit más barato primero)

1. Funding Rate (Spec 006) — local data, no API call
2. HMM Regime (Spec 016) — local fit OHLCV ya cacheado
3. CVD Segmented — API call fetch_trades (cache 60s)
4. Social Sentiment — API call praw/pytrends (cache 30min)

Razón: si funding bloquea (más barato), no llamamos HMM. Si HMM bloquea, no llamamos CVD. Si CVD bloquea, no llamamos Social.

## Dependencias

- `regime_hmm.py` ✅ (Spec 009)
- `cvd_segmented.py` ✅ (Spec 012)
- `social_quant.py` ✅ (Spec 013)
- `strategies.py:V3-REVERSAL block` ✅

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| 3 gates en serie pueden killear 90%+ de V3 alerts | Cada uno try/except. Si combinación demasiado restrictiva, threshold tuning post-7d. Logs visibles para identificar cuál bloqueó más. |
| HMM lento en cada loop (fit ~100-500ms) | Cache externo en `regime_hmm.py` candidato Spec 009.6. Por ahora OK porque V3 trigger ≠ continuo (RSI extremo solo a veces). |
| Social Sentiment requiere REDDIT_CLIENT_ID env var | Si missing → `social_quant` retorna `{}` → `_social.get('signal')` = None → gate skip silent. |
| CVD requiere exchange_singleton + ccxt | Si import falla → empty dict → skip silent. |
| Combinación gates puede crear silencio total V3 | Logs claros qué gate disparó. Dashboard Spec 015 puede mostrar gate metrics futuro. |

## Criterio de aceptación

1. `python3 -m py_compile strategies.py` → OK
2. Verificar en src: gates `regime_hmm`, `cvd_segmented`, `social_quant` invocados
3. Order: funding → HMM → CVD → Social → register_signal_event
4. Logs distintivos por gate (✓ stages):
   - `⏸️ [V3-Reversal] {sym}: funding ...`
   - `⏸️ [V3-Reversal] {sym}: HMM regime=STRONG_TREND ...`
   - `⏸️ [V3-Reversal] {sym}: CVD divergence=BEARISH ...`
   - `⏸️ [V3-Reversal] {sym}: Social=EUPHORIA ...`
5. Producción pendiente 7d: verificar conteo bloqueos por gate + WR V3 con/sin gates
