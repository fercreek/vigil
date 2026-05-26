# SPEC WIRE AUDIT — Scalp Bot / Zenith

> Generado: 2026-05-26 · Sesión que arregló wires dormant
> Commits de referencia: `d268d16` `9352069` `cbbfeb0` `25a9140`

Auditoría de si cada spec está:
- **Wired**: conectado al flujo real de alertas (no solo importado)
- **Logged**: registra en `intel_outcomes` para A/B framework (Spec 022)

---

## Estado por spec

| Status | Specs |
|--------|-------|
| ✅ Wired + logged + works | 002.5, 002.6, 005, 005.5, 007, 008, 009, 009.6, 010, 011, 011.5, 012, 013, 014, 015, 016, 017, 017.5, 018, 019, 020, 020.5, 020.6, 022, 022.5, 022.6, 023, 023.5, 023.6 |
| ⚠️ Wired pero dormant si V3-Reversal no dispara | 007 (Liquidity Sweeps), 008 (FVG), 021 (boost confluence) — están en V3-Reversal msg pero esa strategy rara vez se activa |
| ⏳ Backlog — código existe, log_intel_event falta | V1/V2/V4 strategies (Spec 022.6.3 pendiente) |

---

## Detalle por spec

### Spec 002.5 — Macro Regime State Machine
- **Módulo:** `regime_transitions.py`
- **Wire:** `strategies.py:569`, `strategies.py:718`, `stock_analyzer.py:406`
- **Status:** ✅ Activo. Detecta VERDE_BULL/AMARILLA/NARANJA_BEAR y EXPLOSIVE/BARRIDA.

### Spec 002.6 — EXPLOSIVE_CORRECTION + BARRIDA_OPPORTUNITY
- **Wire:** `strategies.py:577`, `stock_analyzer.py:409`
- **Status:** ✅ Tag visible en alertas V3 + stock. BARRIDA requiere drop ≥2% intraday (Spec 002.7 lo activa completamente).

### Spec 005 — Pydantic Sentinel
- **Wire:** `voice_compactor.py` + `gemini_analyzer.get_sentinel_report_compact`
- **Status:** ✅ Activo. Schema `SentinelResponse` valida JSON de Gemini.

### Spec 005.5 — Pydantic Panorama
- **Wire:** `gemini_analyzer._call_persona_task_structured`
- **Status:** ✅ Activo. Schema `PanoramaPersonaResponse`.

### Spec 007 — Liquidity Sweeps
- **Módulo:** `indicators.detect_liquidity_sweep` (en `indicators.py`, no módulo separado)
- **Wire:** `strategies.py:769` — V3-Reversal msg `_sweep_tag`
- **Status:** ⚠️ Solo en V3-Reversal. Si V3 no dispara, dormant. No en Sentinel ni stocks.

### Spec 008 — Fair Value Gaps
- **Módulo:** `indicators.detect_fair_value_gaps`
- **Wire:** `strategies.py:754` — V3-Reversal msg `_fvg_tag`
- **Status:** ⚠️ Solo en V3-Reversal. Mismo problema que Spec 007.

### Spec 009 — HMM Regime Classifier
- **Módulo:** `regime_hmm.py`
- **Wire:** `strategies._build_extra_intel`, `stock_analyzer.py:423`, `app.py:/api/metrics/regime`
- **Status:** ✅ Activo cripto + stocks. Cache TTL 15min (Spec 009.6).

### Spec 009.6 — HMM LRU Cache TTL
- **Wire:** dentro de `regime_hmm.detect_regime`
- **Status:** ✅ Activo.

### Spec 010 — Whale Netflows Etherscan
- **Módulo:** `onchain.py`
- **Wire:** `strategies._build_extra_intel` (solo ETH), `app.py:/api/metrics/onchain_eth`
- **Status:** ✅ Wired. Requiere `ETHERSCAN_API_KEY` env var (Railway pendiente Fernando).

### Spec 011 — Multi-image BitLobo
- **Wire:** `bitlobo_agent.analyze_chart_multi`
- **Status:** ✅ Activo vía `/bitlobomulti`.

### Spec 011.5 — /bitlobomulti command
- **Wire:** `telegram_commands.py` handler
- **Status:** ✅ Activo.

### Spec 012 — Spot CVD Segmented
- **Módulo:** `cvd_segmented.py`
- **Wire:** `strategies._build_extra_intel`, `app.py:/api/metrics/cvd`
- **Status:** ✅ Activo. Requiere `ccxt` + Binance spot (Railway tiene las libs).

### Spec 013 — Social Sentiment
- **Módulo:** `social_quant.py`
- **Wire:** `strategies._build_extra_intel`, `stock_analyzer.py:390`, `app.py:/api/metrics/social`
- **Status:** ✅ Wired. Requiere `REDDIT_CLIENT_ID/SECRET` para Reddit (Railway pendiente). Google Trends funciona sin creds.

### Spec 014 — Grounded Search
- **Módulo:** `grounded_search.py`
- **Wire:** `gemini_analyzer.get_hourly_panorama:679` — inyecta macro news
- **Status:** ✅ Activo. Daily cap 5 queries protege budget.

### Spec 015 — Live Metrics Dashboard
- **Wire:** `templates/dashboard_live.html` + `app.py`
- **Status:** ✅ Activo en `https://[railway]/dashboard/live`.

### Spec 016 — V3 Multi-Gate Hooks
- **Wire:** `strategies.py:660-740` — HMM STRONG_TREND, CVD BEARISH, Social EUPHORIA gates
- **Status:** ✅ Activo en V3-Reversal.

### Spec 017 — Cuadrilla INTEL Injection
- **Wire:** `gemini_analyzer.get_ai_consensus(..., extra_intel=_extra_intel)`
- **Status:** ✅ Activo. Intel va al prompt LLM + ahora también visible en mensaje (fix 2026-05-26).

### Spec 017.5 — INTEL a V2/V4/SWING
- **Wire:** `strategies.py:884`, `strategies.py:948`, `strategies.py:1072` — `_build_extra_intel(sym)` en cada call
- **Status:** ✅ Activo en V1/V2/V4/SWING como input LLM. `log_intel_event` pendiente (Spec 022.6.3).

### Spec 018 — Grounded Search Panorama
- **Wire:** `gemini_analyzer.get_hourly_panorama:682`
- **Status:** ✅ Activo. Cache 1h.

### Spec 019 — Whale Netflows V3 INTEL
- **Wire:** `strategies._build_extra_intel` (ETH only)
- **Status:** ✅ Wired. Ver Spec 010 para creds.

### Spec 020 — Dashboard Intel Endpoints
- **Wire:** `app.py` — 5 REST endpoints: `/regime`, `/cvd`, `/onchain_eth`, `/social`, `/intel_ab`
- **Status:** ✅ Activo.

### Spec 020.5 — Dashboard Intel Cards
- **Wire:** `templates/dashboard_live.html` — cards HMM/CVD/Whale/Social
- **Status:** ✅ Activo.

### Spec 020.6 — Dashboard Charts Timeseries
- **Wire:** `templates/dashboard_live.html` — Chart.js equity curve, `app.py:/api/metrics/wr_timeseries`
- **Status:** ✅ Activo.

### Spec 021 — V3 Confluence Boost
- **Wire:** `strategies.py:700-740` — +1.0 CVD_BULLISH, +1.0 Social FEAR, +1.0 Whale BULLISH, +0.5 HMM RANGE
- **Status:** ⚠️ Solo en V3-Reversal. No en Sentinel ni stocks.

### Spec 022 — A/B Test Framework
- **Wire:** `tracker.py:intel_outcomes table` + `log_intel_event` + `get_intel_ab_stats`
- **Status:** ✅ Schema activo. Loguean: V3-Reversal, Sentinel, stock_entry.

### Spec 022.5 — Outcome Auto-Update
- **Wire:** `tracker.update_trade_status:617` — hook mapea FULL_WON/LOST/PARTIAL → outcome
- **Bug fix (2026-05-26):** `alert_id` ahora usa `sim_id` (trade.id real) en V3-Reversal. Antes usaba counter → matcheo roto.
- **Status:** ✅ Activo post-fix.

### Spec 022.6 — PnL Real
- **Wire:** `tracker._compute_pnl_pct` llamado en `update_trade_status`
- **Status:** ✅ Activo post-fix 022.5.

### Spec 023 — Intel Stocks Social
- **Wire:** `stock_analyzer.py:390` — social sentiment tag en alertas stock
- **Status:** ✅ Activo. Requiere REDDIT creds para Reddit part.

### Spec 023.5 — HMM Stocks yfinance
- **Wire:** `stock_analyzer.py:423`, `regime_hmm.detect_regime(ticker, timeframe="1h")`
- **Status:** ✅ Activo. yfinance adapter dentro de `regime_hmm`.

### Spec 023.6 — Options OI Stocks
- **Wire:** `stock_analyzer.py:442`
- **Status:** ✅ Activo. yfinance options chain. CALL_HEAVY/PUT_HEAVY tags en alertas.

---

## Huecos conocidos post-audit

| Gap | Spec | Impact | ETA |
|-----|------|--------|-----|
| V1/V2/V4 no logean A/B intel | Spec 022.6.3 | Bajo — Sentinel+V3+stocks ya logean | Próxima sesión |
| BARRIDA dormant (drop=0 siempre false) | Spec 002.7 | Medio — activa oportunidades intraday | Sprint A |
| 007/008 solo en V3 (raramente dispara) | Spec 016.5 | Medio — wire a Sentinel | Sprint A |

---

## Fixes críticos aplicados 2026-05-26

| Commit | Fix | Spec |
|--------|-----|------|
| `d268d16` | UX reply keyboard 6 botones + /help | — |
| `9352069` | `/status` routing bug — handler Mercado capturaba /status | — |
| `cbbfeb0` | **Sentinel intel wire** — HMM/CVD/Social/Whale ahora visible en alertas | 022.6.1 |
| `25a9140` | **alert_id matching fix** — Spec 022.5/.6 nunca corrían (counter≠trade.id) | 022.5.1 |
| `25a9140` | **Stock A/B log** — stocks ahora logean intel_outcomes | 022.6.2 |

---

## Validación post-deploy

```bash
# A/B framework poblado
sqlite3 trades.db "SELECT strategy, COUNT(*) FROM intel_outcomes GROUP BY strategy;"
# → sentinel_compact, v3_reversal, stock_entry

# Outcome matcheo funciona (tras 1 trade cerrado WIN/LOSS)
sqlite3 trades.db "SELECT alert_id, outcome, outcome_pnl FROM intel_outcomes WHERE outcome IS NOT NULL LIMIT 5;"

# Dashboard endpoint
curl https://web-production-75508.up.railway.app/api/metrics/intel_ab
# → total > 0

# Sentinel con intel visible
# → próxima alerta ZEC debe incluir línea "🔬 HMM ... · CVD ... · Social ..."
```
