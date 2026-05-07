# _NEXT.md — Scalp Bot / Zenith
> Update: 2026-05-07 · Prev: `1628c15`

## ⚡ En proceso — retomar aquí

Bot prod `aaee63c` corriendo Railway.

### 🔴 Acción urgente: registrar posiciones en bot
6 posiciones activas en Quantfy, ninguna en `trades.db` → `/check` no las ve:
```
/manual_add TON 2.524 LONG
/manual_add HBAR 0.09195 LONG
/manual_add FIL 1.089 LONG
/manual_add TAO 307.8 LONG
/manual_add SIL 93.12 LONG
/manual_add CLM6 98.78 LONG
```
⚠️ CLM6: revisar si aún está abierta y si aplica stop (precio actual ~$92.80, entrada $98.78 = -6%).

---

## 💡 Backlog (en orden de impacto)

### A. OPEC Calendar — actualizar antes 2026-06-01
- `commodities_bot.py::OPEC_MEETING_DATES` — próxima reunión `"2026-06-01"` ya está, confirmar fecha exacta

### B. `conf_score=5 → 0% WR` — investigar cuando > 20 trades
- Solo 7 trades con score=5 — muestra insuficiente
- Hipótesis: Elliott "Onda 3" bonus → entra tarde near peak
- Acción: revisar `calculate_confluence_score()` con >20 trades

### C. Pack PTS Crypto Triggers
- BTC @ 79,917 + ETH @ 2,520 como triggers LONG (metodología PTS)
- Módulo `pts_crypto_triggers.py` o integrar en `strategies.py`

### D. Economic Calendar generalizado
- FOMC suprime cripto, OPEC suprime OIL
- Pendiente: CPI, NFP, earnings por símbolo

### E. SIM tracking — acumular datos
- `/winrate` muestra Real vs SIM — necesita ~2 semanas de skips para estadística válida
- Skipear señales activamente para alimentar el comparador

### F. Volume mount Railway
- `trades.db` sin volumen = reset en cada redeploy con cambio de slug
- Configurar Railway Volume para persistencia garantizada

---

## ✅ Completado esta sesión (2026-05-07)

### Diagnóstico Oil vs Gold alerts
- Gold alerta porque LONG=4/5: EMA cross ✅, Price>EMA200 ✅, DXY<103 ✅, ATR ✅
- Oil en empate 3/3 — EMA50<EMA200 + price<EMA200 → SHORT; RSI 30+DXY<104 → LONG
- Oil correctamente en "sin señal" (indecisión). No era un bug.

### Backtests (`backtester.py`)
- V4 crypto: BTC 28.6% WR +6.3%, ZEC 23.1% -2.8%, ETH 12.5% -7.1%, TAO 27.3% +2.9%
- Commodities (EMA/RSI/ATR 1H): GOLD 46.9% +16.7%, OIL 52.7% +40.2%
- NG 53.5% +67.8% 🔥, SLV 61.5% +36.5% 🔥, HG 40.5% +25.5%

### Commodities expansion (`c4a46e8`)
- Agregar NG=F, SLV, HG=F a `INSTRUMENTS`
- DXY routing: SLV→gold lógica, NG→neutral, HG→oil lógica
- ATR_SL: NG=2.5x, MIN_SL_PCT_NG=3%
- Silver bull lock via GOLD status cache

### TAO fix (`c4a46e8`)
- Causa raíz: circuit breaker resetea en restart → 14 entradas TAO en 3 días (April 7-9)
- Fix 1: cooldown 4H en DB tras 3 LOST consecutivos (DB-persisted, sobrevive restarts)
- Fix 2: filtro 1D EMA200 — bloquea LONGs cuando tendencia diaria es BEAR
- TAO re-habilitado con ambas protecciones
- Simulación: habrían bloqueado 25/25 trades malos de April

### Telegram menu refresh (`b327e18`)
- Macro → ⛽ Commod (commodities 5 instrumentos, uso diario)
- Intel TAO → 📊 WinRate (winrate accionable)
- Signal keyboard: quitar 💰 Budget IA (ruido en momento de decisión)

### Slash command cleanup (`aaee63c`)
- Eliminados: /portfolio, /health, /positions (duplicados /pos), /flow (texto estático), /leverage (valores hardcoded)
- Fix: /risk usaba ATR de TAO → ahora BTC
- setMyCommands reorganizado por categoría con 23 comandos registrados

---

## ✅ Completado sesiones anteriores (hasta 2026-05-06)

Ver historial en git log — v4.3.x completo (Activate/Skip, manual positions, TON, /check, GOLD fix)

---

## 🔒 Bloqueado / Pendiente decisión

1. **Volume mount Railway** — sin volumen DB resetea en cada redeploy con slug change
2. **GitHub branch protection main** — pendiente desde v1.x
3. **@ZenithDevBot** — bot separado para dev (evitar conflicto getUpdates local vs prod)

---

## 📊 Estado del bot (cierre sesión 2026-05-07)

| Métrica | Valor |
|---------|-------|
| Branch main | `aaee63c` |
| WR real (último audit) | 17.8% (90 trades) |
| Commodities activos | GOLD, OIL, NG, SLV, HG (5 instrumentos) |
| TAO | ✅ re-habilitado con cooldown 4H + filtro 1D EMA200 |
| Posiciones manuales en DB | 0 (pendiente registrar vía /manual_add) |
| OPEC próximo | 2026-06-01 (ya en código) |
| Railway | UP — auto-deploy activo |
