# DEPLOY STATUS — Scalp Bot / Zenith 24/7

Estado vivo del deploy. Último update: 2026-04-21.

Plan completo: `~/.claude/plans/si-revids-quae-nerceistamos-precious-grove.md`

---

## Resumen de fases

| Fase | Estado | Notas |
|------|--------|-------|
| F1 — Webhook TV endurecido (HMAC + token + rate limit + idempotency) | ✅ DONE | `ENFORCE_HMAC=false` canary |
| F2 — Comandos Telegram runtime (/pause /resume /balance /mode /logs /setsl /settp) | ✅ DONE | `runtime_state.py` persiste flags |
| F3 — Railway deploy setup (Procfile, railway.toml, runtime.txt) | ✅ DONE | Pivot desde Oracle |
| F6 — BOT_MODE resolver (dev bot isolation) | ✅ DONE | Resolver en `main.py` antes de imports |
| **Deploy Railway activo** | 🔄 IN PROGRESS | Env vars pendientes |
| F4 — Pine V18 + alertas TV live | ⏳ POST-DEPLOY | Requiere URL pública |
| F5 — MCPs Claude (tradingview-mcp) | ⏳ POST-DEPLOY | — |
| Dev bot (@ZenithDevBot systemd-like) | ⏳ OPCIONAL | Requiere crear bot en @BotFather + segundo servicio Railway |

---

## Estado actual del deploy (CHECKPOINT)

**GitHub repo:** `fercreek/vigil` (branch `main`, último commit `cde0b3d`)

**Railway:**
- Cuenta: Fernando Contreras (TRIAL — ~$1.00 usage credit restante)
- Workspace ID: `05fea91f-a3a8-4a91-8c70-1e0337625d06`
- Proyecto: `gentle-endurance` (d5ae9a55-6932-46d8-b281-87bc0fb9e170)
- Servicio: `web` (29b6f05a-af97-4f62-9a28-b720bb21828e)
- Environment: `production` (da71ebff-5ab4-4f70-b4f2-f1602994422e)
- Región: `europe-west4-drams3a`
- Dashboard: https://railway.com/project/d5ae9a55-6932-46d8-b281-87bc0fb9e170

**Otro proyecto en la misma cuenta:** `vivacious-success` (Dance Leveling) — NO tocar.

**Paso actual:** primer deploy en BUILDING — va a crashear sin env vars. Falta:

1. Pegar vars en Raw Editor (ver template abajo)
2. Railway redeploya auto al guardar vars
3. Verificar `/api/stats` responde 200
4. Si trial no alcanza → upgrade a Hobby $5/mo

---

## Env vars — template para Raw Editor

Valores reales **NUNCA** en repo. Pegar directo en Railway → Variables → Raw Editor (modo ENV):

```bash
# Telegram (copiar de .env local)
TELEGRAM_TOKEN=<pegar>
TELEGRAM_CHAT_ID=<pegar>
BOT_MODE=PROD

# Binance (API key con permisos Read + Futures, NO withdraw, sin IP whitelist)
BINANCE_API_KEY=<pegar>
BINANCE_SECRET_KEY=<pegar>
EXECUTION_MODE=PAPER

# AI (copiar de .env local)
GEMINI_API_KEY=<pegar>
ANTHROPIC_API_KEY=<pegar>

# Loop
CHECK_INTERVAL=35

# Webhook TradingView (generados 2026-04-21 — guardar en password manager)
TV_WEBHOOK_SECRET=7fc04b8d5a93aedb594ff0158636016d172330cf4c8159ec3c5ea96cf84e2400
TV_WEBHOOK_TOKEN=yYlPKWkhgVN0SzOIn_F3IWxwOs87W1LN
ENFORCE_HMAC=false
TV_RATE_LIMIT_PER_MIN=10
```

Re-generar secrets:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"      # TV_WEBHOOK_SECRET
python3 -c "import secrets; print(secrets.token_urlsafe(24))"  # TV_WEBHOOK_TOKEN
```

---

## Siguientes pasos (sin contexto previo)

**Si retomas mañana:**

1. Abrir https://railway.com/project/d5ae9a55-6932-46d8-b281-87bc0fb9e170
2. Servicio `web` → Variables → Raw Editor → pegar template de arriba con valores reales → Update Variables
3. Railway redeploya auto. Ver Deployments tab → última build debe estar `SUCCESS`
4. Click en el deployment → View Logs → confirmar `[BOOT] BOT_MODE=PROD` y `Flask escucha $PORT`
5. Settings → Networking → Generate Domain → Railway da URL `https://gentle-endurance-production.up.railway.app` (o similar)
6. Verificar healthcheck:
   ```bash
   curl https://<url>/api/stats
   # Expect: JSON 200
   ```
7. Test webhook TV (con token path, porque Pine no puede HMAC):
   ```bash
   curl -X POST https://<url>/webhook/tradingview/yYlPKWkhgVN0SzOIn_F3IWxwOs87W1LN \
     -H "Content-Type: application/json" \
     -d '{"symbol":"BTC","direction":"LONG","rsi":28,"price":60000,"strategy":"test","confidence":0.9}'
   # Expect: 200 + alerta llega a Telegram
   ```
8. En Telegram probar `/status`, `/pause`, `/resume`, `/balance`, `/mode paper`, `/logs 20` — confirmar responden.

**Si trial Railway expira antes:** Upgrade Hobby $5/mo desde dashboard → Billing → Choose Plan.

**Persistencia SQLite (trades.db):** Railway disk es ephemeral. Agregar Railway Volume ($0.25/GB/mo) mount `/app/data` antes de 48h. Sin volume cada redeploy pierde historial.

---

## F1 — Webhook TV endurecido ✅

**Archivos:**
- `webhook_security.py` — HMAC SHA256 + rate limit + idempotency
- `app.py` — decorator `@require_tv_auth` + path token `/webhook/tradingview/<token>`
- `config.py:244-249` — doc
- `.env.example` — template
- `docs/TRADINGVIEW_WEBHOOK.md` — runbook

**Auth layers (orden de validación):**
1. Path token (`/webhook/tradingview/<TV_WEBHOOK_TOKEN>`) — usado por Pine (sin HMAC)
2. HMAC firma (`X-TV-Signature` header) — usado por otros publishers
3. Si `ENFORCE_HMAC=true` y ninguno valida → 401
4. Rate limit por IP (10/min default) → 429
5. Idempotency hash(payload+min) → ignora duplicados misma ventana

**Test producción:**
```bash
# Sin firma, ENFORCE_HMAC=false → acepta
curl -X POST https://<url>/webhook/tradingview \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTC","direction":"LONG","rsi":28,"price":60000,"strategy":"test"}'

# Con HMAC válido
SECRET="7fc04b8d..."
PAYLOAD='{"symbol":"BTC","direction":"LONG","rsi":28,"price":60000,"strategy":"test"}'
SIG=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')
curl -X POST https://<url>/webhook/tradingview \
  -H "X-TV-Signature: $SIG" -H "Content-Type: application/json" -d "$PAYLOAD"

# Con token path (Pine)
curl -X POST "https://<url>/webhook/tradingview/yYlPKWkhg..." \
  -H "Content-Type: application/json" -d "$PAYLOAD"

# Rate limit
for i in {1..15}; do curl ... ; done  # 11ª → 429
```

---

## F2 — Comandos Telegram runtime ✅

**Archivos:**
- `runtime_state.py` — persiste `paused` + `execution_mode` en `runtime_state.json`
- `telegram_commands.py` — 7 nuevos handlers antes del catchall
- `trading_executor.py` — check `is_paused()` + re-read `EXECUTION_MODE` cada call
- `scalp_alert_bot.py` — hidrata `GLOBAL_CACHE["paused"]` al arranque

**Comandos nuevos:**

| Cmd | Efecto | Persiste |
|---|---|---|
| `/pause` | Bloquea ejecución de señales nuevas | sí (runtime_state.json) |
| `/resume` | Reanuda ejecución | sí |
| `/balance` | Muestra USDT Futures + modo actual | no |
| `/mode paper` | Switch runtime a PAPER | sí |
| `/mode live` | Switch runtime a LIVE (⚠️ dinero real) | sí |
| `/logs [N]` | Tail últimas N líneas `logs/bot.log` (default 30, max 200) | no |
| `/setsl SYM PCT` | Ajusta SL de trade abierto a N% del entry | sí (DB) |
| `/settp SYM PCT` | Ajusta TP1 de trade abierto a N% del entry | sí (DB) |

**Comportamiento paused:** NO cierra posiciones abiertas — solo bloquea nuevas ejecuciones. Señales siguen llegando a Telegram (no se suprimen alertas) pero `execute_bracket_order` retorna `SKIPPED`.

---

## F3 — Railway deploy ✅

**Archivos:**
- `Procfile` → `web: python main.py`
- `runtime.txt` → `python-3.12.7`
- `railway.toml` → NIXPACKS, restart ALWAYS, healthcheck `/api/stats`
- `.railwayignore` → excluye venv, logs, docs, tests
- `docs/DEPLOY_RAILWAY.md` → runbook completo

**Nota Railway Volume (crítico post-48h):**

SQLite `trades.db` se **borra** en cada redeploy sin volume. Agregar:

```
Railway dashboard → Service → Settings → Volume → Add
- Mount path: /app/data
- Size: 1GB ($0.25/mo)
```

Luego en código migrar DB a `/app/data/trades.db` (o symlink). Ver `docs/DEPLOY_RAILWAY.md` sección "Disk ephemeral".

---

## F6 — BOT_MODE resolver ✅

**Archivo:** `main.py:9-22`

**Comportamiento:**
- `BOT_MODE=PROD` (default) → usa `TELEGRAM_TOKEN` + `TELEGRAM_CHAT_ID` normales
- `BOT_MODE=DEV` → usa `TELEGRAM_TOKEN_DEV` + `TELEGRAM_CHAT_ID_DEV` y **fuerza** `EXECUTION_MODE=PAPER`

Resolver corre **antes** de cualquier `import` que lea `os.getenv("TELEGRAM_TOKEN")` a module-scope. Permite bot dev sin tocar los ~10 archivos que leen el env var.

**Para bot dev separado (opcional, post-deploy):**

1. `@BotFather` → `/newbot` → nombre `ZenithDevBot` → guardar token
2. Obtener `chat_id` dev (chat privado distinto, o mismo chat si prefieres)
3. Segundo servicio Railway en **mismo proyecto**:
   - Nombre: `web-dev`
   - Mismo GitHub repo `fercreek/vigil`
   - Vars: `BOT_MODE=DEV`, `TELEGRAM_TOKEN_DEV=<token>`, `TELEGRAM_CHAT_ID_DEV=<id>` + resto igual
4. Deploy → `@ZenithDevBot` responde sin tocar prod

---

## Riesgos activos

| Riesgo | Mitigación | Status |
|---|---|---|
| Trial credit $1 se agota | Upgrade Hobby $5/mo | ⚠️ watch |
| SQLite borrado en redeploy | Railway Volume $0.25/mo | pending |
| Binance LIVE sin IP whitelist | Key permisos Read+Futures NO withdraw | depende vars |
| WR bajo en LIVE | Soak 48h PAPER + WR>50% antes de switch | controlado por `/mode` |
| Secrets en repo | `.env` gitignored, valores solo en Railway | ✅ |
| Compromiso TV webhook | `ENFORCE_HMAC=true` tras validar Pine firma | canary false |

---

## Checklist externo Fernando

**Antes de primer deploy exitoso:**
- [ ] Abrir Raw Editor en Railway (ya abierto)
- [ ] Copiar valores de `.env` local (6 secrets)
- [ ] Pegar template completo con valores reales
- [ ] Update Variables
- [ ] Esperar build SUCCESS
- [ ] Settings → Networking → Generate Domain
- [ ] `curl https://<url>/api/stats` responde 200
- [ ] Telegram `/status` responde

**Post-deploy (24-48h):**
- [ ] Agregar Railway Volume mount `/app/data`
- [ ] Migrar `trades.db` path (código + env var)
- [ ] Configurar UptimeRobot ping `/api/stats`
- [ ] Observar usage dashboard; upgrade Hobby si hit ~$4 usage

**Post-soak (48h+ PAPER):**
- [ ] WR > 50% en semana
- [ ] `/mode live` vía Telegram (no requiere redeploy)
- [ ] Monitorear primeros trades LIVE con tamaño mínimo

**F4/F5 (post-deploy):**
- [ ] Pegar Pine V18 en TradingView (ver `docs/zenith_indicator.pine` v4.3)
- [ ] Crear alertas: webhook URL `https://<url>/webhook/tradingview/yYlPKWkhg...`
- [ ] Instalar tradingview-mcp en `~/.claude/settings.json`

---

## Comandos ops post-deploy

```bash
# Railway CLI (macOS: brew install railway)
railway login
railway link  # selecciona gentle-endurance

# Logs en vivo
railway logs --follow

# Restart manual
railway redeploy

# Ver vars
railway variables

# Rollback: dashboard Deployments → versión anterior → Redeploy

# Backup DB (si Volume activo)
railway run "cat /app/data/trades.db" > ~/backup_$(date +%F).db
```

---

## Referencias

- Plan completo: `~/.claude/plans/si-revids-quae-nerceistamos-precious-grove.md`
- Railway runbook: `docs/DEPLOY_RAILWAY.md`
- TradingView webhook: `docs/TRADINGVIEW_WEBHOOK.md`
- Commits deploy: `git log origin/main..HEAD --grep="feat(f"` (5 commits: chore + F1 + F2 + F3 + F6)
