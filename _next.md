# _next.md — Pickup point próxima sesión

Última sesión: **2026-04-26** · cierre 22:55 hora MX
Tag prod actual: **v1.2.1**
Branch dev = main (sync OK)
Bot: corriendo 24/7 en Railway · `https://web-production-75508.up.railway.app`

---

## Verificaciones a correr al arrancar

```bash
cd /Users/fernandocastaneda/Documents/ideas/scalp_bot
git pull origin dev
railway logs --deployment 2>&1 | tail -30   # health prod
curl -s https://web-production-75508.up.railway.app/api/stats   # 200 + JSON
```

En Telegram:
- `/status` debería responder <2s
- `/scan` debería listar crypto pending + watchlist PTS
- `/params` muestra thresholds
- `/stocks` lista 10 tickers PTS

---

## Pendiente alto valor — orden recomendado

### 1. Validar SENTINEL compact (15 min)

Bug v1.2.0 → fixed en v1.2.1 (`max_output_tokens` 600→1500).
**Verificar:** próxima ejecución SENTINEL (cada 4h) NO loguea `JSON unparseable`.

Si sigue fallando:
```bash
railway logs --deployment 2>&1 | grep "Sentinel Compact"
# Ahora muestra `raw` completo (sin truncate) — diagnose con regex/JSON shape
```

Si parse falla recurrente: subir a `gemini-2.5-pro` o usar `response_schema` con google-genai SDK.

---

### 2. Pack 4 — Más entradas crypto (DECISIÓN, ~1h)

Bot demasiado restrictivo. 4 dials para subir señales/día:

| Dial | Hoy | Propuesta | Riesgo |
|---|---|---|---|
| Min confluence | 3 | 2 (solo BTC/ETH/SOL) | +30% señales, -10% precision |
| Regime filter | RANGING bloquea todo | RANGING permite 50% size | +50% señales en lateral |
| RSI long entry | 45 | 50 (más permisivo) | +20% señales tempranas |
| **PTS triggers crypto** | — | BTC@79.9k, ETH@2.5k watchers long-only | +2 alertas pre-cargadas, **zero risk** |

**Recomendación:** activar **solo PTS triggers** (zero risk, validados externamente). Otros dials esperar.

Implementación PTS triggers:
- Nuevo módulo `pts_crypto_triggers.py` — lee `data/crypto_triggers.json` (similar a stock_watchlist)
- Loop en main check: si `BTC ≥ 79917` y `USDT.D rompiendo bajista` → emit LONG signal
- Mismo patrón para ETH @ 2520

**Comando para usar también:** `/cryptoadd BTC LONG 79917 69919 93000,101000 85000`

---

### 3. Pack 3 — Eco Mercado (~1h, opcional)

Comando `/eco SYM CANAL DIR NOTA`:
```
/eco BTC bitlobo bull "rompió zona resistencia 75k"
→ guarda en logs/external_signals.jsonl
→ aparece en próximo PANORAMA bajo "📡 ECO 24h"
```

Implementación:
- Módulo `eco_signals.py` (load/save JSONL + dedupe por canal+sym 24h)
- Modificar PANORAMA en `scalp_alert_bot.py:749` para incluir `eco_lines` (ya soportado por `voice_compactor.render_panorama_compact`)
- Comando `/eco` en `telegram_commands.py`

Canales a tracker: PTS, BitLobo, Rose, Whales, Denmark, Trade It Simple, Inversión y Trading.

---

### 4. Tareas del workflow base pendientes (low priority pero importantes)

Del cierre sesión 2026-04-22 (siguen abiertas):

1. **Registrar `@ZenithDevBot` en @BotFather** (10 min) — pasos en `docs/DEV_WORKFLOW.md`
2. **GitHub branch protection** rule para `main` (3 min UI)
3. **GitHub default branch** → `dev` (UI)
4. **Railway upgrade Hobby $5/mo** — trial casi agotado, urgente
5. **Volume mount `/app/data`** (opcional, $0.25/mo) — SQLite persist entre redeploys

---

### 5. Post Contreras Code Jue 23 — pendiente (alta prioridad)

P-012 carrusel "Workflow dev→prod" (7 slides). Ver `_cortex.html` task ID P-012.

Subtasks:
- [ ] Aprobar copy: `~/Documents/context/content/linkedin/posts/2026-04-23-workflow-dev-prod-carrusel.md`
- [ ] Generar `~/Documents/context/scripts/gen-cc-carrusel-workflow.py` (Pillow puro, patrón v3)
- [ ] Correr → 7 PNGs 1080x1350 en `assets/contreras-code/ig-feed/`
- [ ] Upload LinkedIn (drag 7 PNGs en orden 01-07)
- [ ] Caption + hashtags `#softwareengineering #buildingpublic #devops #systems`
- [ ] Programar Metricool
- [ ] `_registry.md`: P-012/LI `⚪ draft` → `📤 scheduled`

---

## Memo arquitectura v1.2.0+

**Comando map:**

| Comando | Implementación | Función |
|---|---|---|
| `/scan` | `scan_status.py` | estado pending alerts crypto + watchlist PTS |
| `/params` | `telegram_commands.py:/params` | thresholds activos (RSI, conf, regime, sentinel) |
| `/stocks [add\|rm\|status]` | `stock_watchlist.py` | PTS watchlist con yfinance live price |
| `/verbose on\|off` | `runtime_state.is_verbose()` | revierte SENTINEL a Cuadrilla full |
| `/pause /resume` | runtime_state.paused | bloquea/reanuda execution |
| `/mode paper\|live` | runtime_state.execution_mode | switch ejecución |
| `/balance` | trading_executor | USDT futures real |
| `/logs [N]` | logs/bot.log tail | últimas N líneas |
| `/setsl /settp SYM PCT` | tracker.update_trade | ajusta SL/TP trade abierto |

**Filtros SENTINEL v1.2.0+:**
- Score Gemini < 4/5 → skip
- Mismo (sym, bias) en últimos 90min con score igual o menor → skip
- Frecuencia 4h (era 2h)
- SALMOS PROPHECY hourly removida (duplicaba PANORAMA)

**Persistencia runtime:**
- `runtime_state.json` — paused, execution_mode, verbose
- `data/stock_watchlist.json` — watchlist PTS (10 tickers seed v1.2.0)
- `risk_state.json` — owned por risk_manager (NO tocar)

---

## Health checks rápidos

```bash
# 1. Bot vivo
curl -s https://web-production-75508.up.railway.app/api/stats

# 2. Threads sanos
railway logs --deployment 2>&1 | grep -E "heartbeat|Ciclo Swing|Macro Update" | tail -5

# 3. Errores recientes
railway logs --deployment 2>&1 | grep -iE "error|warning" | tail -10

# 4. Predeploy gate local
./scripts/predeploy-check.sh

# 5. Git sync state
git log --oneline origin/main..main 2>&1 | wc -l   # = 0 si sync
git log --oneline origin/dev..dev 2>&1 | wc -l    # = 0 si sync
```

---

## Decisiones pendientes

1. **Pack 4 dials** — ¿activar solo PTS triggers crypto, o también relajar regime filter?
2. **Hetzner CAX11 fallback** — Railway funciona OK, ¿necesario migrar? Probable NO.
3. **MCPs Claude** — SSH-MCP + tradingview-mcp todavía no instalados (Fase 5 plan original)
4. **Pine V18 alertas live** — Webhook ya endurecido (HMAC + token), pero Pine V18 nunca deployado a TradingView (Fase 4 plan original)

---

Tag prod actual: **v1.2.1** · Build SUCCESS · Healthcheck OK · ZEC monitor activo
