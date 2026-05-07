# _NEXT.md — Scalp Bot / Zenith
> Update: 2026-05-06 (sesión noche) · Prev: v4.3.2 `bcc6bf4`

## ⚡ En proceso — retomar aquí

Nada abierto. Bot prod `0400ceb` corriendo Railway.

### 🔴 Acción urgente próxima sesión: registrar posiciones en bot
6 posiciones activas en Quantfy, ninguna en `trades.db` → `/check` no las ve:
```
/manual_add TON 2.524 LONG
/manual_add HBAR 0.09195 LONG
/manual_add FIL 1.089 LONG
/manual_add TAO 307.8 LONG
/manual_add SIL 93.12 LONG
/manual_add CLM6 98.78 LONG
```
⚠️ CLM6 urgente: -$64 sin stop. Poner stop ~$93-94. Revisar si LONG es intencional vs config SHORT $95.95.

---

## 💡 Backlog (en orden de impacto)

### A. Stops pendientes posiciones activas
- CLM6: stop ~$93 (urgente, ya -$64)
- HBAR: stop $0.085
- TAO: stop ~$290
- FIL: stop $1.00 o cierre (sin tesis clara)

### B. `conf_score=5 → 0% WR` — investigar cuando > 20 trades
- Solo 7 trades con score=5 — muestra insuficiente
- Hipótesis: Elliott "Onda 3" bonus → entra tarde near peak
- Acción: revisar `calculate_confluence_score()` con >20 trades

### C. Pack PTS Crypto Triggers
- BTC @ 79,917 + ETH @ 2,520 como triggers LONG (metodología PTS)
- Módulo `pts_crypto_triggers.py` o integrar en `strategies.py`

### D. OPEC Calendar — actualizar antes 2026-06-01
- `commodities_bot.py::OPEC_MEETING_DATES` — actualizar manualmente

### E. Economic Calendar generalizado
- FOMC suprime cripto. OPEC suprime OIL.
- Pendiente: CPI, NFP, earnings por símbolo

### F. SIM tracking — primeras semanas
- `/winrate` muestra Real vs SIM comparison
- Necesita ~2 semanas de skips para datos estadísticos

---

## ✅ Completado esta sesión (2026-05-06 noche)

### TON/USDT monitoring (`36b4596`)
- 9 touch points: SYMBOLS, MANUAL_SYMBOLS, V4_EMA_PROX_MAP, last_rsi
- update_dynamic_levels, fetch_tickers, extracción Binance+CoinGecko
- Loop indicadores 15m, sym_map aliases `ton`/`toncoin`

### 🔍 Check button (`bacafc9`)
- Reemplaza "🎯 Setup" en row 1 del menú principal
- `cmd_check_positions(prices)` en `manual_positions_monitor.py`
- Por posición: P&L%, SL sugerido 2×ATR 4H, TP 3×/5×ATR
- Flags BE (≥5%), parcial (≥8% con BE), drawdown (≤-10%)
- Fallback yfinance para stocks/ETFs
- Handler `/check` en dispatcher

### fix commodities GOLD (`0400ceb`)
- `ATR_SL` undefined → `NameError` en cada ciclo GOLD
- Fix: 3 ocurrencias R:R cálculo + label SL → `atr_sl_mult`

### Análisis posiciones reales (screenshots Quantfy)
- TON: +7.84% / +₮200, stop BE ✅ — mejor posición activa
- SIL: +1.68% / +$5, stop+target ✅
- TAO/FIL/HBAR: pérdidas menores, sin stops ⚠️
- CLM6: peor — LONG $98.78, ahora $95.83, -$64 total, sin stop 🔴

---

## ✅ Completado sesiones anteriores (2026-05-06 mañana)

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

## 📊 Estado del bot (cierre sesión noche 2026-05-06)

| Métrica | Valor |
|---------|-------|
| Branch main | `0400ceb` |
| WR real (último audit) | 17.8% |
| Posiciones manuales en DB | 0 (pendiente registrar) |
| TON monitoring | ✅ activo |
| /check button | ✅ activo |
| GOLD commodities error | ✅ fixed |
| OPEC próximo | 2026-06-01 (actualizar en code) |
| Railway | UP — auto-deploy activo |
