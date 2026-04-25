# Deploy Checklist — Scalp Bot → Railway

Runbook formal para llevar cambios de `dev` a prod (Railway auto-deploy desde `main`).

Tiempo esperado: **5min** si todo bien, **<1min rollback** si rompe.

---

## Pre-merge (en rama `dev`)

- [ ] Working dir limpio (`git status` sin modificaciones sin committear)
- [ ] `./scripts/predeploy-check.sh` exit 0 (6/6 checks verdes)
- [ ] Probado ≥1h con `BOT_MODE=DEV` local sin crashes ni errores en Telegram
- [ ] Si nueva dep Python: agregada a `requirements.txt` con versión pinneada (`pkg==X.Y.Z`)
- [ ] Si nueva env var: agregada a `.env.example` Y a `docs/ENV_REFERENCE.md`
- [ ] Si cambio toca ejecución real: `EXECUTION_MODE=PAPER` validado ≥24h antes

---

## Merge dev → main

```bash
git checkout main
git pull origin main              # sincroniza por si hubo hotfix directo
git merge --no-ff dev             # preserva historia (no fast-forward)
git tag -a vX.Y.Z -m "<changelog resumen 1 línea>"
git push origin main --tags
```

**Versionado semver:**
- `MAJOR` (v2.0.0): breaking change (config incompatible, schema DB, estrategia nueva)
- `MINOR` (v1.1.0): feature nueva sin romper nada (nuevo símbolo, nuevo comando)
- `PATCH` (v1.0.1): fix / tweak (requirements, threshold adjust, docs)

---

## Post-push — monitor Railway (2-3 min)

```bash
railway logs --build 2>&1 | tail -20       # debe decir: "Successfully Built!"
railway logs --deployment 2>&1 | tail -30  # debe decir: "Healthcheck succeeded!"
```

Verificaciones externas:

- [ ] Telegram: `/status` al bot prod responde `<2s`
- [ ] `curl https://<domain>/api/stats` → HTTP 200 + JSON válido
- [ ] Logs muestran los 5 threads arrancando (scalp_bot, swing, telegram_worker, stock_analyzer, commodities_bot)
- [ ] Sin error lines (`grep -i error` en últimos 100 logs)

---

## Si rompe

**Opción A — Rollback Railway (30s, 1 click):**
1. Railway UI → Service `web` → Deployments
2. Click en el deploy anterior verde → "Redeploy"
3. Monitor 30s hasta healthcheck pass

**Opción B — Revert git (2min):**
```bash
git revert <merge-sha>            # genera commit de reversa (sin reescribir historia)
git push origin main
# Railway auto-deploy del revert
```

**Opción C — Emergencia total:**
```bash
railway down                      # pausa service, mantiene data
# investigar con calma, fix en dev, redeploy cuando listo
```

Después del rollback:
- [ ] Crear issue en GitHub con logs + root cause
- [ ] Fix en rama `dev`
- [ ] Re-correr `./scripts/predeploy-check.sh`
- [ ] Repetir merge cuando verde

---

## Nueva env var en Railway

1. Railway UI → Service `web` → Variables → **Raw Editor**
2. Agregar línea `NEW_VAR=<valor>` al final
3. Click **Update Variables** (triggers redeploy automático)
4. Confirmar en `.env.example` + `docs/ENV_REFERENCE.md` ya documentadas
5. **NUNCA commitear el valor real** en git

---

## Changelog tagging

Por cada tag, agregar entry a `CHANGELOG.md`:

```markdown
## v1.0.1 — 2026-04-22

### Added
- scripts/predeploy-check.sh — gate local con 6 checks

### Fixed
- requirements.txt: yfinance + bs4 missing (crash al boot)
```

---

## Historial de deploys

| Tag | Fecha | Commit | Cambio |
|-----|-------|--------|--------|
| v1.0.0 | 2026-04-22 | `07245f4` | First Railway deploy — yfinance fix |
