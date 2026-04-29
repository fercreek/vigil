# _NEXT.md — Pickup point próxima sesión

Última sesión: **2026-04-29** · bot v1.3.1
Tag prod actual: **v1.3.1** (main = dev, ambos pushed)
Bot: corriendo 24/7 en Railway · `https://web-production-75508.up.railway.app`

---

## ⚡ En proceso — retomar aquí

### 1. Validar despliegue v1.3.1 en Railway (5 min)

```bash
railway logs --deployment 2>&1 | tail -40
# Verificar:
#   PHY ALERT solo aparece 1 vez cada 30 min (no spam)
#   Sentinel: NO debe aparecer "JSON unparseable" — debe procesar con voces "—"
#   "MANUAL POSITIONS MONITOR ACTIVADO" → /manual en Telegram responde
```

---

### 2. Posiciones manuales activas (estado al cierre 2026-04-29)

| Símbolo | Lado | Entry | Precio aprox | P&L | Acción |
|---------|------|-------|-------------|-----|--------|
| TAO | LONG (leverage) | $295.00 | ~$261 | -$345 unrealized / -$163 leverage | Hold si $250 aguanta |
| ZEC | LONG spot | $358.00 | ~$334 | -$107 | Hold; ZEC best WR 29.5% |
| DOGE | LONG spot | $0.10299 | ~$0.10948 | +$136 | **Mover SL a BE ya** → `/manual_be DOGE` |

---

## 💡 Backlog — próximas mejoras (en orden de impacto)

### A. Conectar MANUAL_POSITIONS a Cuadrilla Zenith (~30 min)
Leer `manual_positions.json` en `gemini_analyzer.get_ai_consensus()`.
Prompt context: "Fernando tiene TAO LONG -$345, ZEC LONG -$107".
Cuadrilla considera correlación al dar bias.

### B. Investigar conf_score invertido (~1h)
- `conf_score 4` → 17.7% WR (79 trades)
- `conf_score 5` → 0.0% WR (7 trades) ← peor
Revisar `strategies.calculate_confluence_score()`. Hipótesis: score 5 = over-extended.
Agregar logging de qué componentes se activan.

### C. Pack 4 — PTS Crypto Triggers (~1h, zero risk)
BTC@79,917 + ETH@2,520 como triggers LONG one-way.
Módulo `pts_crypto_triggers.py` + `/cryptoadd BTC LONG 79917 69919 93000,101000 85000`

### D. Pack 3 — Eco Mercado (opcional)
`/eco SYM CANAL DIR NOTA` → `logs/external_signals.jsonl` → aparece en PANORAMA

---

## ✅ Completado esta sesión (2026-04-29)

### Fixes v1.3.0 (commodities + manual monitor)
- `commodities_bot`: gold bull lock `>$2,500` + MIN_CONFLUENCE 3→4 + OIL SHORT kill en VERDE
- `config`: MANUAL_POSITIONS (TAO/ZEC/DOGE) + FOMC Jun 17 + v4.4
- `manual_positions_monitor.py`: nuevo thread, 30 min, recomendaciones LONG-oriented
- `/manual*` comandos Telegram: tp/sl/be/off/add

### Bugfixes v1.3.1
- **`strategies.py`**: PHY ALERT cooldown 30 min (`_phy_last_alert` dict) — SOL spam eliminado
- **`voice_compactor.py`**: `_repair_partial()` en `parse_sentinel_json` — extrae bias/score/verdict por regex cuando Gemini trunca el JSON en mid-string. Testeado contra payload real de prod.

---

## 🔒 Bloqueado / Decisiones pendientes

1. **Volume mount Railway** — `manual_positions.json` no persiste entre redeploys
   → Workaround: actualizar `config.MANUAL_POSITIONS` antes de cada deploy
2. **Railway upgrade Hobby $5/mo** — revisar estado trial
3. **GitHub branch protection** para `main` (3 min UI)
4. **@ZenithDevBot** en @BotFather (dev bot)

---

## Verificaciones al arrancar próxima sesión

```bash
cd /Users/fernandocastaneda/Documents/ideas/scalp_bot
git pull origin dev
railway logs --deployment 2>&1 | tail -30
# Telegram: /manual  →  TAO/ZEC/DOGE con P&L vivos
```

---

## Memo arquitectura v1.3.1

**Threads:**
| Thread | Módulo | Ciclo |
|--------|--------|-------|
| scalp_bot | scalp_alert_bot.main | ~60s |
| swing | swing_bot | 4H |
| telegram | run_telegram_worker | polling |
| stock | stock_analyzer.stock_watchdog | 15 min |
| commodities | commodities_bot | 15 min |
| manual_monitor | manual_positions_monitor | 30 min |

**Filtros activos:**
- `V1_SHORT_ENABLED = False`
- `TAO_TRADING_ENABLED = False`
- `GOLD_BULL_THRESHOLD = 2500` (no GOLD SHORT)
- `MIN_CONFLUENCE (commodities) = 4`
- `PHY_ALERT_COOLDOWN = 1800s` (30 min — nuevo v1.3.1)

**Persistencia:**
- `runtime_state.json` — paused/mode/verbose
- `data/stock_watchlist.json` — PTS watchlist
- `manual_positions.json` — posiciones manuales (⚠️ no persiste sin Railway volume mount)
- `risk_state.json` — NO tocar

Tag prod: **v1.3.1** · main + dev sync
