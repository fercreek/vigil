# Tasks 001 — Bot Recovery

> Convención: `[ ]` open · `[~]` in-progress · `[x]` done · `[!]` blocked
> Cada task tiene owner (agent o Fernando) + síntoma referenciado (S1..S11)

## Fase 0 — Diagnóstico paralelo

- [x] **T0.1** — A1: investigar bot silence (S1). Owner: Backend Architect agent. Output: `reports/A1-bot-silence.md` ✅ **Bot proceso MUERTO (Apr 22 12:53). V2-AI huérfano dentro de branch V1_LONG_ENABLED=False (strategies.py:528-661). Format bug commodities_bot.py:180 `%.{dec}f` crash loop.**
- [x] **T0.2** — A2: auditar conf_score scoring (S2). Owner: Code Reviewer agent. Output: `reports/A2-scoring-audit.md` ✅ **conf_score Frankenstein, 3 escalas; GOLD Apr 15-22 mismo incidente; ATR +1 incondicional infla scores. Fix: reentry cooldown + drop ATR +1 + score_system column**
- [x] **T0.3** — A3: salud por símbolo (S3, S4, S5). Owner: Database Optimizer agent. Output: `reports/A3-symbol-health.md` ✅ **TAO 0/31 bot-generated (kill), ZEC Q3+Q4=0% chase del top (SWING_BLOCKLIST), SHORT 75% son TAO-SHORT (TAO_SHORT_ENABLED=False + SHORT_BLOCKED_IN_VERDE_BULL). Datos: rsi_entry=50 placeholder, events_json=NULL → pipeline indicadores roto.**

## Fase 1 — Fixes P0

- [x] **T1.1** — F1: aplicar fix bot silence. ✅ Format bug commodities_bot.py ya parcheado en disco (commit posterior al log). V2-AI desbloqueado: removido `is_valid_trend` veto en strategies.py:732, ahora AI decide regardless de EMA.
- [x] **T1.2** — F2: aplicar fix conf_score. ✅ ATR +1 incondicional en commodities_bot.py:472 ahora condicional (solo suma si ATR/price ∈ [0.5%, 3%]).
- [x] **T1.3** — F3: aplicar kill switches + retune. ✅ config.py: TAO_TRADING_ENABLED=False, TAO_SHORT_ENABLED=False, SWING_BLOCKLIST=["TAO","ZEC"], SHORT_BLOCKED_IN_VERDE_BULL=True, EARNINGS_SUPPRESS_24H. Wired en strategies.py loop + scalper_shorts_bot.py.

## Fase 2 — Wiring de gates

- [~] **T2.1** — F4: wire `DEFENSIVE_SECTORS` en `strategies.py` (no filtrar bias bajista) — *stock pipeline no tiene filtros macro existentes, DEFENSIVE_SECTORS queda como marker semántico; revisar en próxima iteración cuando se agregue macro_bias gating*
- [ ] **T2.2** — F4: wire `SECTOR_CLUSTERS` + `MAX_PER_CLUSTER` (exposure cap) — *next session: contar posiciones abiertas en stock_watchdog antes de send_alert*
- [x] **T2.3** — F5: wire `VIX_DORMANT_THRESHOLD` + SP500 regime gate ✅ wired en `scalper_shorts_bot.py` (block SHORT crypto cuando SP500>7000 + VIX<22)
- [x] **T2.4** — F6: extender FOMC suppression → `EARNINGS_SUPPRESS_24H` ✅ `stock_analyzer.py:stock_watchdog` suprime tickers en ventana 24h de earnings (OKLO 2026-05-27, NVDA 2026-05-21)

## Fase 3 — Niveles watchlist

- [x] **T3.1** — F7: ATR-based levels para RGTI. ✅ Price $26.42 ATR $2.60 | SL $21.23 BE $30.31 TP1 $34.21 TP2 $39.40
- [x] **T3.2** — F7: ATR-based levels para CORZ. ✅ Price $25.26 ATR $1.51 | SL $22.24 BE $27.53 TP1 $29.79 TP2 $32.81
- [x] **T3.3** — F7: ATR-based levels para CIFR. ✅ Price $21.97 ATR $1.86 | SL $18.25 BE $24.76 TP1 $27.56 TP2 $31.28
- [x] **T3.4** — F7: ATR-based levels para JNJ. ✅ Price $234.36 ATR $3.94 | SL $226.48 BE $240.27 TP1 $246.18 TP2 $254.06
- [x] **T3.5** — F7: ATR-based levels para KO. ✅ Price $81.49 ATR $1.11 | SL $79.26 BE $83.16 TP1 $84.83 TP2 $87.06
- [x] **T3.6** — F7: ATR-based levels para CL. ✅ Price $90.62 ATR $1.83 | SL $86.96 BE $93.37 TP1 $96.12 TP2 $99.78

## Fase 4 — Verificación

- [x] **V1** — `python3 -m py_compile` en config.py, strategies.py, scalp_alert_bot.py, scalper_shorts_bot.py, commodities_bot.py, stock_analyzer.py ✅ ALL COMPILE OK
- [ ] **V2** — Backtest 30d sample post-fixes — *manual, próxima sesión*
- [ ] **V3** — Deploy Railway + 72h monitor → confirmar S1 resuelto — *requiere git push + railway redeploy manual de Fernando*

## Métricas post-recovery (llenar al cerrar)

- Global WR: 18.7% → __
- conf_score=5 WR: 0% → __
- SHORT WR: 8.3% → __
- TAO status: ACTIVE → __
- Trades nuevos en últimas 72h: __

## Reports (creados por agents en Fase 0)

- `reports/A1-bot-silence.md`
- `reports/A2-scoring-audit.md`
- `reports/A3-symbol-health.md`
