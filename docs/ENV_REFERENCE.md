# Env Reference — Scalp Bot

Todas las variables de entorno. Source of truth para `.env` local + Railway prod.

**Convención:**
- ✅ = requerida
- ⚠️ = opcional (con fallback)
- 🔒 = secret (nunca commitear)

---

## Telegram

| Var | Requerida | Default | Dónde | Descripción |
|-----|-----------|---------|-------|-------------|
| `TELEGRAM_TOKEN` 🔒 | ✅ PROD | — | Railway + .env local (PROD) | Token del bot prod (@BotFather) |
| `TELEGRAM_CHAT_ID` | ✅ PROD | — | Railway + .env local (PROD) | Chat ID donde el bot envía alertas prod |
| `TELEGRAM_TOKEN_DEV` 🔒 | ✅ DEV | — | .env local únicamente | Token del `@ZenithDevBot` (separado del prod) |
| `TELEGRAM_CHAT_ID_DEV` | ✅ DEV | — | .env local únicamente | Chat ID dev (chat privado con ZenithDevBot) |

**Regla de oro:** nunca agregues `*_DEV` a Railway. Dev bot vive solo en laptop.

---

## Bot mode

| Var | Requerida | Default | Dónde | Descripción |
|-----|-----------|---------|-------|-------------|
| `BOT_MODE` | ⚠️ | `PROD` | ambos | `PROD` usa tokens reales. `DEV` usa `*_DEV` + fuerza `EXECUTION_MODE=PAPER` |

Resolver en `main.py:11-23`. En DEV swap es automático — no se leen tokens prod.

---

## Exchange (Binance)

| Var | Requerida | Default | Dónde | Descripción |
|-----|-----------|---------|-------|-------------|
| `BINANCE_API_KEY` 🔒 | ✅ LIVE | — | Railway (solo LIVE) | API key HMAC — permisos Futures Trade |
| `BINANCE_SECRET_KEY` 🔒 | ✅ LIVE | — | Railway (solo LIVE) | Secret HMAC (Ed25519/RSA NO soportado por ccxt) |
| `EXECUTION_MODE` | ⚠️ | `PAPER` | ambos | `PAPER` simula órdenes. `LIVE` toca Binance real |

**NUNCA** pasar `LIVE` sin ≥1 semana en `PAPER` con WR verificado >50%.

---

## AI providers

| Var | Requerida | Default | Dónde | Descripción |
|-----|-----------|---------|-------|-------------|
| `GEMINI_API_KEY` 🔒 | ✅ | — | Railway + .env local | Google AI Studio key para Cuadrilla Zenith + Vision |
| `ANTHROPIC_API_KEY` 🔒 | ⚠️ | — | opcional | Claude Haiku. Si vacío, fallback a Gemini (ver `gemini_analyzer.py:30-46`) |

AI Router detecta ausencia de ANTHROPIC y loguea `[AI Router] ANTHROPIC_API_KEY no configurada — usando Gemini para todo`.

---

## Loop + rate limits

| Var | Requerida | Default | Dónde | Descripción |
|-----|-----------|---------|-------|-------------|
| `CHECK_INTERVAL` | ⚠️ | `35` | ambos | Segundos entre ciclos de análisis (scalp loop) |
| `TV_RATE_LIMIT_PER_MIN` | ⚠️ | `10` | Railway | Max webhook requests/min/IP (429 si se excede) |

---

## Webhook TradingView (Fase 1)

| Var | Requerida | Default | Dónde | Descripción |
|-----|-----------|---------|-------|-------------|
| `TV_WEBHOOK_SECRET` 🔒 | ✅ | — | Railway + .env local | HMAC SHA256 shared secret. Generar: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `TV_WEBHOOK_TOKEN` 🔒 | ✅ | — | Railway + .env local | Token en path `/webhook/tradingview/<token>` (segundo factor para Pine que no puede HMAC). Generar: `python -c "import secrets; print(secrets.token_urlsafe(24))"` |
| `ENFORCE_HMAC` | ⚠️ | `false` | Railway | `true` rechaza requests sin HMAC válido (canary). Activar solo tras validar Pine V18 |

---

## Checklist al agregar nueva var

1. Definir nombre (`SCREAMING_SNAKE_CASE`)
2. Agregar default en `config.py` si aplica
3. Agregar al `.env.example` con comentario
4. Agregar fila en esta tabla (`docs/ENV_REFERENCE.md`)
5. Si es secret 🔒: Railway UI Raw Editor + `.env` local, nunca commit
6. Si es no-secret: puede ir directo en `railway.toml` bajo `[env]`

---

## Inspección rápida

```bash
# Ver qué tiene Railway
railway variables

# Ver qué tiene .env local (sin valores secretos)
grep -v '^#' .env | cut -d= -f1

# Diff entre .env.example y .env local
comm -23 <(grep -v '^#' .env.example | cut -d= -f1 | sort -u) \
         <(grep -v '^#' .env | cut -d= -f1 | sort -u)
# Muestra vars del template que faltan en tu .env
```
