# _NEXT.md — Scalp Bot / Zenith

> Update: 2026-05-27 · Último commit: `a2fd110`
> **Sesión: bot muerto 5 semanas → resucitado + spec kit pro + monitor ZEC/TAO/TON + señales working.**

---

## ⚡ En proceso (retomar aquí)

### P0 — Sesión 2026-05-27 — Pendientes Fernando

- [ ] **Env vars Railway** — `ETHERSCAN_API_KEY` + `REDDIT_CLIENT_ID/SECRET/USER_AGENT` (specs 010/013)
- [ ] **PTS article auth** — `protradingskills.com/analysis/...` requiere login para WebFetch. Pegar texto manualmente si quieres más actualizaciones en CLAUDE.md
- [ ] **Posiciones portfolio** — revisar SUI (-$486) y FIL (-$103): sin catalizador PTS. Definir si cortar o hold
- [ ] **ZEC SL $520** — monitor activo, próxima alerta si cae bajo $521
- [ ] **Validar reportes Telegram** — 16:00 UTC llega Market Status con ZEC/TAO/TON, verificar formato en cel

### P1 — Validaciones automáticas (heredadas)

- [ ] **A/B framework 7d** — `curl /api/metrics/intel_ab` → `total > 0` tras primer ciclo Sentinel
- [ ] **Outcome auto-update** — `sqlite3 trades.db "SELECT alert_id, outcome FROM intel_outcomes WHERE outcome IS NOT NULL LIMIT 5;"`

---

### P0 — Fernando hace estos manualmente (heredado)

- [ ] **Env vars Railway** — `ETHERSCAN_API_KEY` (Etherscan.io/myapikey) + `REDDIT_CLIENT_ID/SECRET/USER_AGENT` (reddit.com/prefs/apps). Desbloquea Specs 010/013/019.
- [ ] **Test UX Telegram cel** — reiniciar Telegram desktop, mandar `/pos` → verificar 6 botones reply keyboard nuevos (📂 💰 📊 🔬 🛡️ 🏛️). Mandar `/status`, `/audit`, `/intel BTC` → confirmar responden.

### P1 — Validaciones automáticas (esperar datos)

- [ ] **A/B framework 7d** — `curl https://web-production-75508.up.railway.app/api/metrics/intel_ab` → `total > 0` después del primer ciclo Sentinel (~4h). `with_outcome > 0` después de un trade cerrado.
- [ ] **Sentinel con intel visible** — próxima alerta ZEC/TAO debe incluir línea `🔬 HMM ... · CVD ... · Social ...` (fix `cbbfeb0`).
- [ ] **Outcome auto-update funciona** — tras trade FULL_WON/LOST: `sqlite3 trades.db "SELECT alert_id, outcome, outcome_pnl FROM intel_outcomes WHERE outcome IS NOT NULL LIMIT 5;"` muestra rows (fix `25a9140`).
- [ ] **Schedule task 13:35 UTC** — verificar `docs/specs/004-notebooklm-findings-integration/VERIFICATION_2026-05-26.md` post-trigger.

---

## 💡 Backlog Spec X.7+ — Próxima sesión

Orden por valor + dependencias. Ver `docs/SPEC_WIRE_AUDIT.md` para estado completo de wires.

### Sprint A (alto valor, validación A/B)

- [ ] **Spec 022.7** — Expected Value per boost bucket (`WR × avg_pnl + (1-WR) × avg_pnl_losses`). Métrica definitiva A/B. Sin esto, no se distingue boost que gana raro pero alto vs boost frecuente pequeño.
- [ ] **Spec 002.7** — `intraday_drop_pct` real tracking en `GLOBAL_CACHE["intraday_high"]` por símbolo. Activa BARRIDA fire (hoy dormant en V3 cripto + futuro V2/V4 stocks).
- [ ] **Spec 022.6.3** — `log_intel_event` en V1/V2/V4 strategies (17.5 ya inyecta intel al LLM, falta loguear para A/B).

### Sprint B (cobertura stocks)

- [ ] **Spec 023.7** — IV rank percentile + unusual options activity scanner. Extiende Spec 023.6 con historic IV percentile. Requiere DB persist daily OI snapshots.
- [ ] **Spec 023.8** — Gate stocks alerts por PUT_HEAVY OI (post-backtest validation).

### Sprint C (Pydantic completeness)

- [ ] **Spec 005.6** — Pydantic para `get_top_setup` + `get_expert_advice` + `get_macro_shield`. Schemas más complejos (conditional fields).
- [ ] **Spec 005.7** — Deprecate `voice_compactor.parse_sentinel_json` cuando Pydantic primary path > 95% success en 30d.

### Sprint D (UX + dashboard)

- [ ] **Spec 011.6** — `media_group_id` Telegram detection (multi-photo single update). Spec 011.5 ya cubre via filesystem workflow, esto es upgrade UX.
- [ ] **Spec 015.5** — HTTP Basic auth dashboard (si Railway URL becomes discoverable).
- [ ] **Spec 020.7** — Multi-line chart WR overlapped por régimen HMM (cross WR × regime).
- [ ] **Spec 020.8** — Notif Telegram cuando boost segment achieves stat significance (N≥30, Δ≥5pp).

### Sprint E (low priority)

- [ ] **Spec 009.7** — Telegram `/regime SYMBOL` command (debug rapid).
- [ ] **Spec 014.6** — Persist grounded_search counter SQLite (sobrevive Railway restarts).
- [ ] **Spec 019.5** — BTC + SOL whale tracking (blockchain.com + SolanaFM gratis).
- [ ] **Spec 010.6** — ERC-20 stablecoin support (USDT/USDC inflows).

---

## ✅ Sesión 2026-05-26 — Pipeline NotebookLM 4 + 37 specs

### Commits batch

| Commit | Specs |
|--------|-------|
| `2692562` | Spec 004 NotebookLM findings (MAX_PER_CLUSTER_BY_CLUSTER, QUANTUM_SUPPRESSED_UNTIL, BTC gate, bonds watch) |
| `1544eb6` | Notebook 1 PTS Watchlist Deep Dive docs |
| `aa42ad9` | Notebook 3 Bot Performance Audit pipeline |
| `5101ce6` | fix(stock) watchdog restart loop |
| `7d306a7` | fix(sentinel) alerts vacías ZEC |
| `06a7f9d` | Notebook 4 Trading Strategies Research |
| `7cb1961` | Spec 005 Pydantic Sentinel |
| `a2e9fae` | Spec 006 Funding Rate Filter |
| `48668d7` | Spec 007 Liquidity Sweeps |
| `858406e` | Spec 008 Fair Value Gaps |
| `d745c79` | Spec 009 HMM Regime Classifier |
| `127d2b4` | Spec 011 Multi-image BitLobo |
| `fc8f6cc` | Spec 010 Whale Netflows Etherscan |
| `478c4f1` | Spec 014 Grounded Search |
| `22b9add` | Spec 013 Social Sentiment |
| `1f27f13` | Spec 015 Live Metrics Dashboard |
| `64490bb` | Spec 012 Spot CVD Segmentado |
| `b8336e7` | Spec 016 V3 Multi-Gate Hooks |
| `2d29faf` | Spec 017 Cuadrilla Intel Injection |
| `2f8553d` | Spec 018 Grounded Search Panorama |
| `8902a61` | Spec 019 Whale Netflows V3 INTEL |
| `113aead` | Spec 020 Dashboard Intel Endpoints |
| `21c2fe0` | Spec 021 V3 Confluence Boost |
| `305f550` | Spec 017.5 INTEL a V2/V4/SWING |
| `1ac3dbc` | Spec 009.6 HMM TTL Cache |
| `20187cd` | Spec 022 A/B Test Framework |
| `4964cc8` | Spec 023 Intel Stocks Social |
| `f4e2756` | Spec 002.5 Regime Transitions |
| `6e7fbc8` | Spec 011.5 /bitlobomulti |
| `322ee24` | Spec 020.5 Dashboard Intel Cards |
| `d111695` | Spec 023.5 HMM Stocks yfinance |
| `fad56e4` | Spec 002.6 + 020.6 BARRIDA/EXPLOSIVE + Chart.js |
| `c50a0db` | Spec 022.5 Outcome Auto-Update |
| `33205b9` | Spec 023.6 + 022.6 + 005.5 Options OI + PnL + Pydantic Panorama |

---

## 🔒 Bloqueado

- NotebookLM 3 Performance Audit prompts ejecución (Fernando manual)
- Validation A/B framework requiere ≥30 trades cerrados (semanas)
- ETHERSCAN_API_KEY env var configuración Railway (recommended para Spec 010+019)
- REDDIT_CLIENT_ID/SECRET env vars Railway (recommended para Spec 013)

---

## 📊 Cost Estimation API (post-deploy)

Ver `docs/COST_ESTIMATION_2026-05-26.md` para análisis detallado. Resumen:

- **Gemini Flash 2.5:** ~$0.40-1.50/mes
- **Grounded Search:** ~$0.015/mes (cap 5/día)
- **Anthropic Claude:** $0 (SDK no instalado)
- **Externas (yfinance/Etherscan/Reddit/Trends/Binance):** $0 (free tiers)
- **Total estimado:** **~$0.50-$1.50/mes**
- **Budget configurado:** $10/mes
- **Margen:** ~85-95% libre

Riesgo: si bot busy mode cripto volátil, +V3 alerts × 4 strategies podría duplicar. Mitigaciones:
- HMM cache Spec 009.6 reduce overhead 4x
- CVD/Social/Whale TTL caches absorben
- Gates V3 (Spec 016) filtran alerts
- Grounded cap 5/día protege

Validación real: monitor `/api/ai_budget` en dashboard 7 días post-deploy.
