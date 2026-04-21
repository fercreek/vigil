# DEPLOY RAILWAY — Runbook

Despliegue Scalp Bot en Railway.app. Zero sysadmin, git push deploy.

## Arquitectura

```
git push main
  │
  ▼
Railway detecta push (GitHub integration) o railway up (CLI)
  │
  ▼ Nixpacks builder lee:
  ├── Procfile         → `web: python main.py`
  ├── runtime.txt      → python-3.12.7
  ├── requirements.txt → pip install
  └── railway.toml     → deploy config (restart, healthcheck)
  │
  ▼
Container boot
  ├── main.py arranca 5 threads background (scalp, swing, telegram, stock, commodities)
  └── Flask escucha $PORT asignado por Railway
  │
  ▼
Public URL: https://<proyecto>.up.railway.app
  ├── GET /api/stats       → healthcheck
  └── POST /webhook/tradingview[/<token>]  → Pine alerts
```

## Archivos deploy (ya creados en repo)

| Archivo | Propósito |
|---|---|
| `Procfile` | `web: python main.py` |
| `runtime.txt` | `python-3.12.7` (pin) |
| `railway.toml` | Builder, restart policy, healthcheck |
| `.railwayignore` | Excluir venv, logs, .env del build |
| `requirements.txt` | Deps pip |
| `.env.example` | Template vars (NO real) |

## Setup inicial (una sola vez)

### 1. Crear cuenta Railway

- railway.app → Login con GitHub
- Plan: **Hobby $5/mo** (incluye $5 usage credit, en práctica = gratis para este bot)

### 2. Instalar Railway CLI (opcional pero útil)

```bash
# macOS
brew install railway

# Login
railway login
```

### 3. Crear proyecto

**Opción A — UI (recomendado):**
1. Railway dashboard → New Project → Deploy from GitHub repo
2. Seleccionar repo `scalp_bot`
3. Railway detecta Python auto + usa Procfile

**Opción B — CLI:**
```bash
cd ~/Documents/ideas/scalp_bot
railway init
railway link
railway up
```

### 4. Configurar variables de entorno

Railway dashboard → proyecto → Variables → bulk import desde `.env.example`:

```
# Telegram
TELEGRAM_TOKEN=<tu_token>
TELEGRAM_CHAT_ID=<tu_chat_id>
BOT_MODE=PROD

# Binance
BINANCE_API_KEY=<api_key>
BINANCE_SECRET_KEY=<secret>
EXECUTION_MODE=PAPER

# AI
GEMINI_API_KEY=<key>
ANTHROPIC_API_KEY=<key>

# Loop
CHECK_INTERVAL=35

# Webhook TV (F1)
TV_WEBHOOK_SECRET=<token_hex_32>
TV_WEBHOOK_TOKEN=<token_urlsafe_24>
ENFORCE_HMAC=false
TV_RATE_LIMIT_PER_MIN=10
```

Generar secrets:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

**IMPORTANTE:** mantener `EXECUTION_MODE=PAPER` durante primeros 48h soak test. Cambiar a `LIVE` solo si WR > 50%.

### 5. Whitelist Binance API (solo para LIVE)

Railway asigna IP dinámica — **NO** sirve IP whitelist Binance directo.

Opciones:
- **Tailscale/exit-node** → bot sale por IP fija Tailscale → whitelist esa IP
- **Binance sin IP whitelist** (permisos limitados: solo trade, no withdraw)
- **IP Static Railway** ($20/mo addon, overkill)

Recomendado: Binance API key con permisos `Enable Reading + Enable Futures`, **NO** `Enable Withdrawals`, sin IP whitelist. Riesgo cero robo fondos si se filtra.

### 6. Deploy

```bash
# Desde laptop
git add Procfile runtime.txt railway.toml .railwayignore
git commit -m "feat: Railway deploy config"
git push origin main

# Railway auto-build + deploy en 2-4 min
# Ver logs:
railway logs
```

### 7. Obtener URL pública

Railway asigna `https://<proyecto>.up.railway.app`.

Verificar:
```bash
curl https://<proyecto>.up.railway.app/api/stats
# → JSON con métricas bot
```

### 8. Configurar custom domain (opcional)

Para webhook TV con URL memorable:

1. Railway → Settings → Networking → Custom Domain
2. Añadir `bot.tudominio.tld`
3. DNS del dominio: CNAME → `<proyecto>.up.railway.app`
4. Railway genera TLS automático (5-10 min propagación)

## Ops diarios

```bash
# Logs en vivo
railway logs --follow

# Restart
railway redeploy

# Status
railway status

# Ver vars de entorno
railway variables

# Deploy cambio código
git push origin main    # auto-deploy
# O manual:
railway up
```

## Monitoreo

Railway dashboard muestra:
- CPU / RAM usage
- Logs streaming
- Deployments history
- Uptime graph

**Alerta downtime:** configurar UptimeRobot → `GET https://<proyecto>.up.railway.app/api/stats` cada 5 min → Telegram si falla.

## Costo real

| Componente | Costo |
|---|---|
| Railway Hobby plan | $5/mo base + $5 credit |
| Uso típico bot 24/7 | ~$3-4/mo compute |
| **Total efectivo** | **$5/mo** (credit cubre uso) |

Si uso excede $5 credit → paga diferencia. Este bot con 5 threads + Flask + Gemini calls = **siempre < $5 usage**.

## Rollback

```bash
# Ver deploys recientes
railway deployments

# Rollback a deploy anterior (dashboard UI)
# Settings → Deployments → Redeploy on previous version
```

O git:
```bash
git revert <sha_malo>
git push origin main
```

## Limites Railway Hobby

| Recurso | Límite |
|---|---|
| RAM | 8GB max |
| CPU | 8 vCPU max |
| Disk | 100GB ephemeral (se borra on redeploy) |
| Network egress | 100GB/mo |
| Concurrent services | unlimited |

**Disk ephemeral = CRITICAL:** SQLite `trades.db` **se borra en cada redeploy**. Soluciones:

1. **Railway Volume** ($0.25/GB/mo): mount persistent volume
   ```bash
   railway volume add --name zenith-data --mount-path /app/data
   ```
   Luego en código: DB path = `/app/data/trades.db`

2. **Postgres Railway** ($5/mo addon): migrar SQLite → Postgres
3. **Backup cron** (menos robusto): `rsync` DB a S3/R2 cada hora

**Recomendado F3 v1:** Railway Volume. Upgrade Postgres después.

## Troubleshooting

| Síntoma | Fix |
|---|---|
| Build falla "no module named X" | Verificar `requirements.txt` pinea versión |
| `$PORT` error | Railway asigna PORT, `main.py:80` ya lee `os.environ["PORT"]` ✅ |
| Bot arranca pero no responde TG | Verificar `TELEGRAM_TOKEN` + `TELEGRAM_CHAT_ID` en vars |
| Webhook 401 | `ENFORCE_HMAC=true` sin secret correcto |
| DB se borra en redeploy | Agregar Railway Volume |
| OOM crash | Upgrade RAM limit (paid addon) o optimizar Gemini batch size |
| Binance API error IP | Quitar IP whitelist en API key o usar Tailscale |

## Checklist primer deploy

- [ ] Crear cuenta Railway + plan Hobby
- [ ] Conectar GitHub repo
- [ ] Variables de entorno cargadas (`.env.example` como referencia)
- [ ] `EXECUTION_MODE=PAPER`
- [ ] Generar `TV_WEBHOOK_SECRET` + `TV_WEBHOOK_TOKEN`
- [ ] `git push origin main`
- [ ] Verificar `railway logs` sin errores
- [ ] `curl .../api/stats` responde 200
- [ ] Custom domain (opcional)
- [ ] Railway Volume para persist DB
- [ ] UptimeRobot alert downtime
- [ ] 48h soak PAPER
- [ ] Switch `EXECUTION_MODE=LIVE` si WR OK
