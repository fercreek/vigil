# Dev Workflow — Scalp Bot

Cómo trabajar día a día sin romper prod.

---

## Branch model

```
dev (default)  ────────┬──────┬────────▶  trabajo diario
                       │      │
                       ▼      ▼
main                  merge  merge   ────▶  Railway auto-deploy
                       │      │
                       tag    tag
                       v1.0.1 v1.1.0
```

- `main` = prod (Railway auto-deploy). **Intocable** excepto merges verificados con tag.
- `dev` = default para clones + trabajo diario.
- Sin `staging` — bot dev local cubre ese rol.

---

## Setup inicial (primera vez)

```bash
git clone git@github.com:fercreek/vigil.git scalp_bot
cd scalp_bot

# Venv + deps
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Secrets locales
cp .env.example .env
# Editar .env y rellenar:
#   TELEGRAM_TOKEN, TELEGRAM_CHAT_ID (bot prod — solo para debugging, NO correr prod local)
#   GEMINI_API_KEY
#   BINANCE_API_KEY, BINANCE_SECRET_KEY (opcional en DEV — PAPER no los usa)
```

---

## Registrar bot dev (`@ZenithDevBot`) — primera vez

1. Abrir Telegram → chat con `@BotFather` → `/newbot`
2. Nombre: `Zenith Dev Bot`
3. Username: `ZenithDevBot` (si tomado, probar `ZenithDevXBot`, `FernandoZenithDev`, etc.)
4. Copiar token devuelto → agregar a `.env`:
   ```
   TELEGRAM_TOKEN_DEV=<pegar token aquí>
   ```
5. Abrir chat privado con `@ZenithDevBot` en Telegram → enviar `/start`
6. Obtener chat ID:
   ```bash
   source .env && curl -s "https://api.telegram.org/bot${TELEGRAM_TOKEN_DEV}/getUpdates" \
     | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['result'][-1]['message']['chat']['id'])"
   ```
7. Agregar a `.env`:
   ```
   TELEGRAM_CHAT_ID_DEV=<pegar id>
   ```

**Verificación:**
```bash
BOT_MODE=DEV python main.py
# Banner debe mostrar:
# [BOOT] BOT_MODE=DEV — using dev token + EXECUTION_MODE=PAPER forced
```

En Telegram: `/status` a `@ZenithDevBot` → responde solo al chat dev (prod no se entera).

---

## Ciclo diario

```bash
# 1. Asegurar estar en dev + sincronizado
git checkout dev
git pull origin dev

# 2. Trabajar (edit, test, iterar)
BOT_MODE=DEV python main.py   # correr dev local en paralelo al prod Railway

# 3. Commit con mensaje convencional (ver sección abajo)
git add <files>
git commit -m "feat: agrega filtro funding rate para SOL"
git push origin dev

# 4. Cuando listo para prod: gate local
./scripts/predeploy-check.sh
# Si pasa → continuar. Si falla → fix y re-correr.

# 5. Merge a main
git checkout main
git pull origin main
git merge --no-ff dev
git tag -a v1.X.Y -m "resumen del cambio"
git push origin main --tags
# Railway auto-deploy dispara

# 6. Monitorear
railway logs --deployment 2>&1 | tail -30
# Verificar "Healthcheck succeeded!" + threads arrancan

# 7. Volver a dev
git checkout dev
git merge main      # sincroniza dev con el tag recién creado
```

---

## Commit message convention

Formato: `<tipo>: <descripción>`

| Tipo | Uso |
|------|-----|
| `feat` | Feature nueva (nuevo símbolo, comando, estrategia) |
| `fix` | Bug fix |
| `docs` | Solo documentación |
| `refactor` | Cambio de código sin cambiar comportamiento |
| `test` | Agregar/modificar tests |
| `perf` | Optimización |
| `chore` | Mantenimiento (deps, config, logs) |

Ejemplos:
```
feat: agrega comando /pause a Telegram
fix(deploy): yfinance missing en requirements.txt
docs: actualiza DEPLOY_CHECKLIST con paso Raw Editor
refactor: extrae telegram_commands.py de scalp_alert_bot
test(strategies): cubre caso V4 EMA proximity edge
```

---

## Tag versioning (semver)

`vMAJOR.MINOR.PATCH`

- `MAJOR` (v2.0.0): breaking change — schema DB nuevo, config incompatible, estrategia rehecha
- `MINOR` (v1.1.0): feature nueva sin romper — nuevo símbolo, nuevo comando, nueva IA
- `PATCH` (v1.0.1): fix o tweak — requirements, threshold adjust, docs fix

---

## Agregar símbolo nuevo

1. Editar `config.py` → agregar al `SYMBOLS_TO_CHECK` o al swing list
2. Verificar que el símbolo existe en Binance y tiene suficiente histórico
3. Correr `BOT_MODE=DEV python main.py` → monitorear 1-2h si emite señales razonables
4. Agregar test en `tests/test_strategies.py` si hay lógica nueva
5. Commit: `feat(symbols): agrega ADA al watchlist`
6. Seguir flujo merge a main normal

---

## Agregar dependencia Python

1. En venv: `pip install <pkg>` + `pip show <pkg>` (copiar versión exacta)
2. Editar `requirements.txt` → agregar línea `pkg==X.Y.Z` (pin estricto)
3. Correr `pip install --dry-run -r requirements.txt` → verificar no rompe otras
4. `./scripts/predeploy-check.sh` pasa
5. Commit: `chore(deps): agrega <pkg> para <razón>`
6. Seguir flujo merge a main normal

---

## Agregar env var nueva

1. Leer en código: `os.getenv("NEW_VAR", "<default>")`
2. Agregar línea en `.env.example` con comentario
3. Agregar fila en `docs/ENV_REFERENCE.md` con descripción, default, requerida, dónde
4. Actualizar tu `.env` local
5. Si es requerida en prod: Railway UI → Raw Editor → agregar antes del merge
6. Commit: `feat: nueva config NEW_VAR para <razón>`
7. Seguir flujo merge a main normal

---

## Rollback rápido

Ver [DEPLOY_CHECKLIST.md](DEPLOY_CHECKLIST.md#si-rompe). Resumen:

- **Mejor opción (30s):** Railway UI → Deployments → Redeploy previo
- **Backup (2min):** `git revert <merge-sha> && git push`
- **Emergencia:** `railway down` (pausa service)

---

## Referencia rápida — archivos críticos

| Archivo | Qué hace |
|---------|----------|
| `main.py` | Entry point + threads + BOT_MODE resolver |
| `config.py` | Thresholds, símbolos, kill switches, FOMC context |
| `scalp_alert_bot.py` | Loop principal alertas scalp |
| `swing_bot.py` | Loop swing (4H timeframe) |
| `stock_analyzer.py` | Monitoreo acciones pre-market |
| `commodities_bot.py` | GOLD, OIL |
| `telegram_commands.py` | Dispatcher `/pause`, `/mode`, `/status`, etc. |
| `gemini_analyzer.py` | Cuadrilla Zenith (AI consensus) + AI Router |
| `trading_executor.py` | Binance orders (PAPER/LIVE) |
| `app.py` | Flask + webhook TradingView |
| `tests/conftest.py` | Fixtures OHLCV sintéticos |
| `scripts/predeploy-check.sh` | Gate pre-merge a main |
| `railway.toml` | Config Railway (builder, healthcheck) |
