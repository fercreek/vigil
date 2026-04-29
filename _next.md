# _NEXT.md — Pickup point próxima sesión

Última sesión: **2026-04-29** · bot v1.3.0
Tag prod actual: **v1.3.0** (main = dev, ambos pushed)
Bot: corriendo 24/7 en Railway · `https://web-production-75508.up.railway.app`

---

## ⚡ En proceso — retomar aquí

### 1. Validar despliegue v1.3.0 en Railway (5 min)

```bash
railway logs --deployment 2>&1 | tail -40
# Buscar:
#   "MANUAL POSITIONS MONITOR ACTIVADO"
#   "manual_monitor: store inicializado desde config (3 posiciones)"
#   "Commodities: analizando GOLD" → NO debe ver GOLD SHORT (bull lock activo)
```

En Telegram tras redeploy:
- `/manual` — debe mostrar TAO / ZEC / DOGE con P&L y recomendación
- `/manual_be DOGE` — anotar que DOGE ya está en ganancia cerca de BE

---

### 2. Posiciones manuales activas (estado al cierre 2026-04-29)

| Símbolo | Lado | Entry | Precio aprox | P&L | Acción recomendada |
|---------|------|-------|-------------|-----|--------------------|
| TAO | LONG (leverage) | $295.00 | ~$261 | -$345 unrealized / -$163 leverage | Hold si $250 aguanta; cierre si rompe |
| ZEC | LONG spot | $358.00 | ~$334 | -$107 | Hold; ZEC WR bot 29.5% — mejor activo |
| DOGE | LONG spot | $0.10299 | ~$0.10948 | +$136 | Mover SL a BE ($0.10299) ya |

Portfolio total: **-$399.99** (screenshot 2026-04-29)
Ganadores: DOGE +141, HBAR +43, LTC +37, ETH +4 | Perdedores: TAO -507, ZEC -107, SIL -12

---

## 💡 Backlog — próximas mejoras bot (en orden de impacto)

### A. Conectar MANUAL_POSITIONS a Cuadrilla Zenith (~30 min)
Cuadrilla no sabe de posiciones manuales abiertas. Agregar contexto en `gemini_analyzer.py`:
- Leer `manual_positions.json` en `get_ai_consensus()`
- Incluir en prompt: "Fernando tiene TAO LONG en -$345, ZEC LONG en -$107"
- Cuadrilla considera correlación al dar bias

### B. Investigar conf_score invertido (~1h)
Win rate por confluencia (base 89 trades):
- `conf_score 4` → **17.7% WR** (79 trades)
- `conf_score 5` → **0.0% WR** (7 trades)
Score más alto = peor resultado. El cálculo de confluencia tiene algo roto.
Hipótesis: score 5 se activa solo en condiciones over-extended (RSI + BB extremos simultáneos).
Fix: revisar `strategies.calculate_confluence_score()`, agregar logging de componentes activos.

### C. Pack 4 — PTS Crypto Triggers (~1h, zero risk)
BTC@79,917 + ETH@2,520 como triggers LONG one-way:
- Nuevo módulo `pts_crypto_triggers.py`
- Loop check: si `BTC >= 79917` y `USDT.D` rompiendo bajista → emit LONG
- `/cryptoadd BTC LONG 79917 69919 93000,101000 85000`

### D. Pack 3 — Eco Mercado (opcional, ~1h)
`/eco SYM CANAL DIR NOTA` → guarda señales externas en `logs/external_signals.jsonl`
Aparece en PANORAMA bajo "📡 ECO 24h"

---

## ✅ Completado esta sesión (2026-04-29)

### Win Rate Audit
- Global: **16.9%** (15W / 74L / 89 cerrados)
- TAO: 3.1% (1/32) — ya deshabilitado (`TAO_TRADING_ENABLED = False`)
- GOLD: 0% (0/6) — causa raíz: GOLD SHORT en bull market ATH
- SHORT general: **4.3%** (1/23) — `V1_SHORT_ENABLED = False` ya activo
- conf_score 5 = 0% WR (peor que conf 4) — investigación pendiente (backlog B)

### Fixes deployados → main `ba29f12`

**`commodities_bot.py`** (commit `5cab747`)
- `MIN_CONFLUENCE` 3→4
- Gold bull lock: `price > $2,500` → GOLD SHORT suprimido
- OIL SHORT bloqueado cuando SP500 > 7,000

**`config.py`** (commit `5cab747`)
- `MANUAL_POSITIONS` agregado (TAO/ZEC/DOGE)
- `FOMC_NEXT_MEETING` → Jun 17 (Apr 28-29 ya pasó)
- `STRATEGY_ITERATION = "v4.4"`

**`manual_positions_monitor.py`** nuevo (commit `0fa9133`)
- Store persistente `manual_positions.json` (init desde config)
- Análisis cada 30 min: precio Binance → P&L → recomendación LONG-oriented
- +5% → mover BE | +8% → tomar parciales | -8% → alerta drawdown | cooldown 1h/sym

**`telegram_commands.py`** (commit `0fa9133`)
- `/manual` — P&L + recomendación todas las posiciones
- `/manual_tp SYM [pct]` — TP completo o parcial
- `/manual_sl SYM` — SL hit
- `/manual_be SYM` — anotar BE movido
- `/manual_off SYM` — pausar monitoreo
- `/manual_add SYM ENTRY [LONG]` — agregar nueva posición

**`main.py`** (commit `0fa9133`) — thread `manual_monitor` + watchdog heartbeat

---

## 🔒 Bloqueado / Decisiones pendientes

1. **Volume mount Railway** — `manual_positions.json` NO persiste entre redeploys sin mount
   → Workaround: actualizar `config.MANUAL_POSITIONS` antes de cada deploy
2. **Railway upgrade Hobby $5/mo** — trial puede agotarse, revisar
3. **GitHub branch protection** para `main` (3 min UI)
4. **@ZenithDevBot** registro en @BotFather (dev bot separado)

---

## Verificaciones al arrancar próxima sesión

```bash
cd /Users/fernandocastaneda/Documents/ideas/scalp_bot
git pull origin dev
railway logs --deployment 2>&1 | tail -30
# Telegram: /manual → TAO / ZEC / DOGE con P&L vivos
```

---

## Memo arquitectura v1.3.0

**Threads en producción:**

| Thread | Módulo | Función |
|--------|--------|---------|
| scalp_bot | scalp_alert_bot.main | loop cripto (ZEC, BTC, ETH, SOL, HBAR, DOGE) |
| swing | swing_bot | estrategias swing 4H |
| telegram | scalp_alert_bot.run_telegram_worker | dispatcher comandos |
| stock | stock_analyzer.stock_watchdog | watchlist PTS acciones |
| commodities | commodities_bot | GOLD + OIL (15 min, 1H) |
| **manual_monitor** | **manual_positions_monitor** | **posiciones manuales (30 min)** |

**Filtros activos v1.3.0:**
- `V1_SHORT_ENABLED = False` — V1 shorts off (4.3% WR)
- `TAO_TRADING_ENABLED = False` — TAO off (3.1% WR)
- `GOLD_BULL_THRESHOLD = 2500` — no GOLD SHORT mientras price > $2,500
- `MIN_CONFLUENCE (commodities) = 4` — era 3

**Persistencia runtime:**
- `runtime_state.json` — paused, execution_mode, verbose
- `data/stock_watchlist.json` — watchlist PTS
- `manual_positions.json` — posiciones manuales (⚠️ no persiste en Railway sin volume mount)
- `risk_state.json` — risk_manager (NO tocar)

Tag prod: **v1.3.0** · main + dev sync · Railway auto-deploy en push a main
