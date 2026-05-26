# Next Session Plan — Post-Sprint 2026-05-26

> Estado: 37+ specs done. Pipeline NotebookLM 4 completo + wires + A/B framework.
> Foco próxima sesión: **validation primero**, luego features X.7.

## Checklist arranque próxima sesión

1. **Verificar producción Railway** (5 min):
   ```bash
   railway logs --service web 2>&1 | tail -100 | grep -E "WATCHDOG|Sentinel|V3-Reversal|intel_outcomes"
   ```
   Buscar:
   - `🛡️ WATCHDOG [RESTART]` → ❌ regresión Spec 5101ce6
   - `[Sentinel Compact]` warnings → ❌ Pydantic Spec 005 fail
   - `⏸️ [V3-Reversal]` skips → ✅ gates Spec 016 funcionando
   - `⭐ [V3-Reversal] boost +X.X` → ✅ Spec 021 active
   - `📊 [intel_outcomes] auto-updated` → ✅ Spec 022.5 hook funcionando

2. **Verificar budget API** (2 min):
   ```bash
   curl https://[railway]/api/ai_budget
   # Esperar <$1.50/mes después de 7 días
   ```

3. **Verificar A/B framework** (2 min):
   ```bash
   curl https://[railway]/api/metrics/intel_ab
   # Esperar total > 0, with_outcome > 0 si bot operó
   ```

4. **Dashboard live** (1 min):
   - `https://[railway]/dashboard/live`
   - Verificar: WR + intel cards + Chart.js charts populados

## Sprint priority next session

### Sprint A — Validación + Métricas (alto valor, low effort)

**Spec 022.7 — Expected Value boost analysis**

EV = WR × avg_pnl_pct_win + (1-WR) × avg_pnl_pct_loss.

Extender `tracker.get_intel_ab_stats` con EV per bucket. Endpoint `/api/metrics/intel_ab` retorna también EV.

Justificación: WR sola no distingue boost que gana raro pero alto vs boost frecuente pequeño. EV es métrica definitiva.

**Tiempo:** 45 min · **Files:** `tracker.py` + `templates/dashboard_live.html` (mostrar EV)

**Spec 002.7 — `intraday_drop_pct` tracking real**

Buffer `GLOBAL_CACHE["intraday_high"]` por símbolo + compute drop_pct por ciclo. Activa BARRIDA_OPPORTUNITY fire real (hoy dormant).

**Tiempo:** 60 min · **Files:** `scalp_alert_bot.py` (main loop) + `strategies.py` (wire en V3+V2/V4)

### Sprint B — Cobertura stocks completa

**Spec 023.7 — IV rank percentile**

DB tabla `options_iv_history` persist daily IV snapshots. Helper percentile last 30d.

Tag stocks: `📊 IV rank: 78%ile (alto, options caras)`.

**Tiempo:** 90 min · **Files:** `options_oi.py` extender + `tracker.py` schema + `stock_analyzer.py` tag

**Spec 023.8 — Gate stocks por extreme OI**

Si `PUT_HEAVY` ratio ≤ 0.3 (extreme bearish hedging) → skip stock long alert.

**Tiempo:** 30 min post-validation Spec 023.6 7d.

### Sprint C — Pydantic completeness

**Spec 005.6 — Pydantic restantes** (`get_top_setup`, `get_expert_advice`, `get_macro_shield`)

Schemas más complejos con `conditional fields`, `Literal symbol`, `list[str]`.

**Tiempo:** 90 min · **Files:** `models/` (3 nuevos) + `gemini_analyzer.py`

**Spec 005.7 — Deprecate `parse_sentinel_json` legacy**

Si métricas muestran >95% Pydantic success en 30d producción → remove fallback parser.

**Tiempo:** 30 min · **Files:** `voice_compactor.py` (delete) + `gemini_analyzer.py` (cleanup)

### Sprint D — UX (medium priority)

- Spec 011.6 — `media_group_id` Telegram (multi-photo single update)
- Spec 020.7 — Multi-line chart WR × régimen HMM cross
- Spec 020.8 — Notif Telegram boost segment significance
- Spec 015.5 — HTTP Basic auth dashboard

### Sprint E — Low priority

- Spec 009.7 — `/regime SYMBOL` Telegram debug
- Spec 014.6 — Persist grounded counter SQLite
- Spec 019.5 — BTC + SOL whale tracking
- Spec 010.6 — ERC-20 stablecoin support
- Spec 002.6 — EXPLOSIVE_TICKERS movible a `config.py`

## Anti-patterns a evitar

1. **No agregar más AI calls** sin medir cost actual. Wait 7d validation.
2. **No deprecate parsers legacy** sin 95% Pydantic success.
3. **No subir cap grounded** sin métricas que justifiquen.
4. **No introducir gates V3 más estrictos** sin medir A/B framework primero.
5. **No wire intel a stocks adicional** sin validar Spec 023.x funciona.

## NotebookLM pendientes

- [ ] **Notebook 3 Performance Audit** ejecutar prompts. Corpus listo en `docs/research/notebook-lm-3/`. Necesario para validar A/B framework con data histórica.
- [ ] **Notebook 5 (potencial)** — Backtest results post-Spec 016 vs pre. Comparativo WR + EV.

## Schedule tasks activas

- 13:35 UTC daily verif Spec 003+004 (ya activa, ID: `scalp-bot-spec003-004-verification`)

## Validation gate — 7 días

ANTES de implementar Sprint A/B/C:

1. ✅ Bot estable (no crashes, no watchdog loops)
2. ✅ Budget API < $2/mes
3. ✅ A/B framework graba ≥30 trades con outcome+pnl
4. ✅ `boost_3+ WR > boost_0 WR + 5pp` (Spec 021 helps)
5. ✅ Gates Spec 016 bloquean 20-50% V3 alerts (not 0%, not 100%)

Si falla cualquier check → debug + tune ANTES de nuevos specs.
