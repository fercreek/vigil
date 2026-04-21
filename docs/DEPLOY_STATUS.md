# DEPLOY STATUS — Scalp Bot 24/7

Estado vivo del deploy a servidor online. Actualizar al cerrar cada fase.

Plan completo: `~/.claude/plans/si-revids-quae-nerceistamos-precious-grove.md`

---

## Resumen de fases

| Fase | Estado | Tiempo est. | Notas |
|------|--------|-------------|-------|
| F1 — Webhook TV endurecido (HMAC + rate limit + idempotency) | ✅ DONE | 3h | Canary `ENFORCE_HMAC=false` |
| F3 — Railway deploy setup (Procfile, railway.toml) | ✅ DONE | 1h | Pivot desde Oracle; git push deploy |
| F2 — Comandos Telegram runtime (/pause /mode /balance ...) | ⏳ PENDING | 4h | — |
| F4 — Pine V18 + alertas TV live | ⏳ PENDING | 2h | Requiere F3 online |
| F5 — MCPs Claude (tradingview-mcp) | ⏳ PENDING | 1h | Railway CLI > SSH-MCP |
| F6 — Bot dev separado (@ZenithDevBot + BOT_MODE) | ⏳ PENDING | 3h | Requiere crear bot en @BotFather |

**Cambio de plan:** Oracle Free Tier descartado por lottery capacity + drama verificación. Pivot a **Railway $5/mo** para deploy en 10 min con git push.

---

## F1 — Webhook TV endurecido ✅

**Archivos:**
- `webhook_security.py` (nuevo) — HMAC SHA256 + rate limit + idempotency
- `app.py:1-7,417-430` — import + decorator `@require_tv_auth` + path opcional `/webhook/tradingview/<token>`
- `config.py:244-249` — doc vars (valores reales en `.env`)
- `.env.example` (nuevo)

**Vars nuevas en `.env`:**
```
TV_WEBHOOK_SECRET=<32 bytes hex>
TV_WEBHOOK_TOKEN=<24 bytes urlsafe>
ENFORCE_HMAC=false       # canary; cambiar a true tras validar Pine firma
TV_RATE_LIMIT_PER_MIN=10
```

Generar secrets:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"      # SECRET
python3 -c "import secrets; print(secrets.token_urlsafe(24))"  # TOKEN
```

**Tests locales (DONE):**
- HMAC válido/inválido
- Rate limit N/min
- Idempotency hash(payload+minuto)

**Test producción (post F3):**
```bash
# 1. Sin firma, ENFORCE_HMAC=false
curl -X POST https://bot.dominio/webhook/tradingview \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTC","direction":"LONG","rsi":28,"price":60000,"strategy":"test"}'
# Expect: 200

# 2. Con HMAC válido
SECRET="<TV_WEBHOOK_SECRET>"
PAYLOAD='{"symbol":"BTC","direction":"LONG","rsi":28,"price":60000,"strategy":"test"}'
SIG=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')
curl -X POST https://bot.dominio/webhook/tradingview \
  -H "X-TV-Signature: $SIG" -H "Content-Type: application/json" -d "$PAYLOAD"
# Expect: 200, alerta TG

# 3. Con token path (cuando Pine no puede HMAC)
TOKEN="<TV_WEBHOOK_TOKEN>"
curl -X POST "https://bot.dominio/webhook/tradingview/$TOKEN" \
  -H "Content-Type: application/json" -d "$PAYLOAD"
# Expect: 200

# 4. Rate limit
for i in {1..15}; do curl ... ; done
# Expect: 11ª → 429
```

---

## F2 — Comandos Telegram runtime 🔄

**Pending:** extender `telegram_commands.py` con 7 comandos:

| Cmd | Acción | Persiste |
|---|---|---|
| `/pause` | `GLOBAL_CACHE["paused"]=True` → bloquea nuevas ejecuciones | sí |
| `/resume` | `GLOBAL_CACHE["paused"]=False` | sí |
| `/balance` | `ZenithExecutor.get_balance()` (PAPER=$1000 o Binance real) | no |
| `/mode paper\|live` | switch `EXECUTION_MODE` runtime | sí |
| `/logs [N]` | tail últimas N líneas `logs/bot.log` (default 30) | no |
| `/setsl SYM PCT` | ajusta SL trade abierto | sí |
| `/settp SYM PCT` | ajusta TP trade abierto | sí |

**Archivos:**
- `telegram_commands.py:509` — extender dispatcher
- `trading_executor.py:85` — check `GLOBAL_CACHE["paused"]` antes de ejecutar
- `risk_state.json` — persistir `paused` + `execution_mode`
- `scalp_alert_bot.py` — agregar `GLOBAL_CACHE["paused"]` init

**Verificación:**
```
/pause    → "⏸️ Bot pausado"
/balance  → "💰 USDT Futures: $X.XX (PAPER|LIVE)"
/mode paper  → "✅ Modo: PAPER"
/logs 10  → últimas 10 líneas
```

---

## F3 — Railway deploy ✅

**Archivos creados:**
- `Procfile` — `web: python main.py`
- `runtime.txt` — `python-3.12.7`
- `railway.toml` — builder, restart always, healthcheck `/api/stats`
- `.railwayignore` — excluir venv, logs, .env
- `docs/DEPLOY_RAILWAY.md` — runbook completo

**Requisitos externos Fernando:**

| Ítem | Acción |
|---|---|
| Cuenta Railway | railway.app → GitHub login → Hobby $5/mo |
| Secrets TV webhook | `python3 -c "import secrets; print(secrets.token_hex(32))"` + `token_urlsafe(24)` |
| Binance API | sin IP whitelist (Railway IP dinámica) + permisos NO-withdraw |
| Custom domain (opcional) | CNAME → `<proyecto>.up.railway.app` |

**Orden ejecución Railway:**
1. Railway dashboard → New Project → Deploy from GitHub → seleccionar repo
2. Variables → bulk import desde `.env.example`
3. `EXECUTION_MODE=PAPER` en vars
4. `git push origin main` → auto-deploy
5. `railway logs --follow` → verificar boot limpio
6. `curl https://<proyecto>.up.railway.app/api/stats` → 200 OK
7. (Opcional) agregar Railway Volume para persist SQLite DB
8. 48h soak PAPER → switch `EXECUTION_MODE=LIVE` si WR OK

**Costo:** $5/mo Hobby plan (credit $5 usage cubre uso real del bot).

Ver `docs/DEPLOY_RAILWAY.md` para runbook completo.

---

## F4 — Pine V18 + alertas TV live ⏳

**Archivos:**
- `scripts/tradingview/Zenith_Suite_V18.pine` — copiar a TradingView UI
- `docs/TRADINGVIEW_SETUP.md` — runbook setup (NUEVO)

**Setup manual TradingView:**
1. Pine Editor → pegar V18 → Add to Chart
2. Crear alerta por símbolo: BTC, ZEC, TAO, HBAR, DOGE
3. Webhook URL: `https://bot.dominio/webhook/tradingview/<TV_WEBHOOK_TOKEN>` (token path porque Pine no puede HMAC)
4. Message body:
```json
{
  "symbol": "{{ticker}}",
  "direction": "{{strategy.order.action}}",
  "rsi": {{plot("RSI")}},
  "price": {{close}},
  "strategy": "Zenith V18",
  "confidence": 0.9
}
```

**Nota TV plan:** free limita 1 alerta. Pro $15/mo permite múltiples.

---

## F5 — MCPs Claude local ⏳

Railway no usa SSH → drop SSH-MCP. Railway CLI + dashboard bastan.

**MCPs:**

| MCP | URL | Uso |
|---|---|---|
| tradingview-mcp | `github.com/tradesdontlie/tradingview-mcp` | Crear/editar alertas TV desde Claude |

**Archivos:**
- `~/.claude/settings.json` — agregar `mcpServers`

**Alternativa ops Railway desde Claude:** usar `Bash` tool con `railway logs`, `railway redeploy`. No hace falta MCP específico.

---

## F6 — Bot dev separado ⏳

**Requisitos externos:**
- Crear `@ZenithDevBot` en `@BotFather` → token
- Chat privado dev (tu user ID Telegram)

**Archivos:**
- `config.py` — `BOT_MODE`, `TELEGRAM_BOT_TOKEN_DEV`, `TELEGRAM_CHAT_ID_DEV`
- `scalp_alert_bot.py` — selector token según `BOT_MODE`
- `deploy/scalpbot-dev.service` — systemd separado, `EXECUTION_MODE=PAPER` forzado
- `metrics.py` — extender con latency webhook→TG, señales/hora, WR paper

---

## Checklist externo Fernando

Antes de deploy Railway:
- [ ] Cuenta Railway (railway.app → GitHub login)
- [ ] Plan Hobby $5/mo activado
- [ ] Generar secrets:
  ```bash
  python3 -c "import secrets; print(secrets.token_hex(32))"      # TV_WEBHOOK_SECRET
  python3 -c "import secrets; print(secrets.token_urlsafe(24))"  # TV_WEBHOOK_TOKEN
  ```
- [ ] Guardar ambos en password manager
- [ ] Binance API key con permisos **solo Futures + Read, NO Withdraw**, sin IP whitelist
- [ ] Repo `scalp_bot` en GitHub (push pendiente)
- [ ] (Opcional) Custom domain con CNAME → Railway

Antes de F6 (dev bot):
- [ ] Crear `@ZenithDevBot` en `@BotFather` → guardar token
- [ ] Obtener chat_id dev

Antes de LIVE mode (después de 48h soak PAPER):
- [ ] WR > 50% en PAPER semana
- [ ] Set `EXECUTION_MODE=LIVE` en Railway vars
- [ ] Railway redeploy (auto on var change)

---

## Comandos ops post-deploy

```bash
# Logs en vivo
railway logs --follow

# Restart manual
railway redeploy

# Status + metrics
railway status

# Ver env vars
railway variables

# Update código (auto-deploy en push)
git push origin main

# Rollback: dashboard → Deployments → previous version → Redeploy
# O git revert + push
git revert <sha_malo>
git push origin main

# Backup DB (si usas Railway Volume)
railway run "cp /app/data/trades.db /tmp/ && cat /tmp/trades.db" > ~/backup_$(date +%F).db
```

---

## Riesgos identificados

| Riesgo | Mitigación |
|---|---|
| TV Pine no puede HMAC | Token path `/webhook/tradingview/<token>` como segundo factor |
| LIVE mode con WR bajo | Soak 48h PAPER + WR > 50% antes de switch |
| Secrets en repo | `.env` gitignored, `.env.example` sin valores reales |
| Crash bot sin supervisión | `railway.toml` restart=ALWAYS + UptimeRobot ping `/api/stats` |
| SQLite borrado en redeploy | Railway Volume $0.25/GB/mo mount `/app/data` |
| Binance API IP dinámica | Key con permisos NO-withdraw → bajo riesgo sin whitelist |
| Usage > $5 credit | Monitor dashboard; bot real usa ~$3-4/mo |

---

## Timeline estimado (Railway)

- Día 1: F1 ✅ + F3 ✅ + F2 (6h total código)
- Día 2: deploy Railway + F4 alertas TV + F5 MCPs + F6 dev bot (6h + deploy)
- Día 3-4: 48h soak PAPER
- Día 5: switch LIVE si WR > 50%

Total: ~12h código + 48h soak = **3-5 días calendar** (vs 1 semana Oracle).
