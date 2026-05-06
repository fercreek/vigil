# _NEXT.md — Scalp Bot / Zenith
> Update: 2026-05-06 · Prev: CHANGELOG.md#v4.3

## ⚡ En proceso — retomar aquí

Nada abierto. Sesión cerrada limpia. Bot prod corriendo en Railway `v4.3.2`.

---

## 💡 Backlog (en orden de impacto)

### A. `conf_score=5 → 0% WR` — investigar cuando muestra > 20 trades
- Solo 7 trades con score=5 hoy — muestra insuficiente
- Hipótesis: score 5 requiere Elliott "Onda 3" bonus → entra tarde, near peak
- Acción cuando tengamos 20+ trades score=5: revisar `calculate_confluence_score()`

### B. Pack 4 — PTS Crypto Triggers
- BTC @ 79,917 + ETH @ 2,520 como triggers LONG one-way (metodología PTS)
- Módulo `pts_crypto_triggers.py` o integrar en `strategies.py`
- Comando: `/cryptoadd BTC LONG 79917 69919 93000,101000 85000`

### C. OPEC Calendar — actualizar antes de próxima reunión
- Próxima fecha estimada: `2026-06-01`
- `commodities_bot.py::OPEC_MEETING_DATES` — actualizar manualmente
- Considerar `/opec add YYYY-MM-DD` para evitar editar código

### D. Economic Calendar generalizado
- FOMC ya suprime cripto. OPEC ya suprime OIL.
- Pendiente: CPI, NFP, earnings por símbolo
- `ECONOMIC_CALENDAR_SUPPRESSIONS = {"CPI": [...], "NFP": [...]}` en config.py

### E. SIM tracking — primeras semanas
- `/winrate` ya muestra Real vs SIM comparison
- Necesita ~2 semanas de skips para tener datos estadísticos
- Target: >30 señales skiadas para evaluar gap

---

## ✅ Completado esta sesión (2026-05-06)

### v4.3.0 — Snappy UX + Alert Lifecycle
- `_PENDING_SIGNALS` store + Activate/Skip en todas las señales V1-V5
- `get_signal_keyboard` / `get_management_keyboard` en `alert_manager.py`
- Storage unificado manual (`trades.db` is_manual=1, JSON eliminado)
- `/open` picker 3-tap + `/pos` compact/full
- Menu principal row 1: `[📂 /pos][➕ /open][🎯 Setup]`
- Migrate script `scripts/migrate_manual_to_db.py`
- `docs/SIGNAL_FLOW.md` — lifecycle completo

### v4.3.1 — Stock alerts Activate/Skip
- `stock_analyzer.py` ENTRY_ALERT → signal keyboard (Activate/Skip)
- BE/TP/SL alerts → management keyboard si hay trade abierto
- `activate` callback fetchea precio live (yfinance) para stocks al tap

### v4.3.2 — is_sim filter + Win Rate Real vs SIM
- `get_win_rate()` / `get_audit_metrics()` / `get_alert_stats()` filtran `is_sim=0`
- `get_winrate_comparison()` — dict real vs SIM con gap pp y verdict
- `/winrate` muestra sección "Real vs SIM (Activate/Skip)" al final

### OIL Post-Mortem + Commodities fixes
- OPEC suppression ±24h (`OPEC_MEETING_DATES`)
- RSI SHORT fix: `45<rsi<65` (bullish zone) → `rsi>62` (overbought real)
- SL per instrumento: GOLD=1.5x ATR, OIL=2.5x ATR + MIN_SL_PCT=2%
- Post-rally filter: OIL +15% en 10d → RSI<45 para LONG
- `docs/STRATEGY_AUDIT.md` — post-mortem documentado

---

## 🔒 Bloqueado / Pendiente decisión

1. **Volume mount Railway** — `trades.db` persiste entre deploys (ok en Railway con volumen)
   → Sin volumen: DB se resetea en cada redeploy. Riesgo bajo (Railway rara vez redeploya sin push)
2. **GitHub branch protection main** — 3 min UI, pendiente desde v1.x
3. **@ZenithDevBot** — bot separado para dev (evitar conflicto getUpdates local vs prod)

---

## 📊 Estado del bot (cierre sesión)

| Métrica | Valor |
|---------|-------|
| Tag prod | `v4.3.2` |
| Branch main | `bcc6bf4` |
| WR real (90 trades) | 17.8% (16W / 74L) |
| WR SIM | sin datos aún (0 skips) |
| Trades OPEN | 0 |
| OPEC próximo | 2026-06-01 (actualizar en code) |
| Railway | UP — auto-deploy activo |
