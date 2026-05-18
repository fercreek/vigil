# Railway Volume Setup — Persistencia de trades.db

> Contexto: sin Volume mount, `trades.db` se borra en cada redeploy.
> Código ya listo (`tracker.py` lee env var `TRACKER_DB`). Solo falta Railway dashboard.

---

## Estado del código (ya aplicado — commit `fix: tracker.py lee TRACKER_DB env var`)

```python
# tracker.py:5
DB_FILE = os.getenv("TRACKER_DB", "trades.db")
# Fallback: "trades.db" en raíz (comportamiento anterior sin Volume)
```

`ai_budget.py` ya leía `TRACKER_DB` → ambos módulos ahora apuntan al mismo archivo.

---

## Pasos en Railway dashboard (Fernando — 5 min)

### 1. Crear Volume

- Ir a: https://railway.com → proyecto `gentle-endurance` → servicio `web`
- **Settings → Volumes → Add Volume**
- Mount path: `/app/data`
- Size: 1 GB
- Costo: ~$0.25/GB/mes

### 2. Agregar env var

- **Variables → Raw Editor** → agregar al final:
  ```
  TRACKER_DB=/app/data/trades.db
  ```
- Click **Update Variables** → Railway redeploya automático

### 3. Verificar post-deploy

En Railway logs buscar la línea de arranque del bot. La DB debe crearse en `/app/data/trades.db`.

También desde Telegram: `/winrate` debe responder (antes fallaba silenciosamente si la DB era nueva).

---

## Qué pasa si se redeploya con Volume activo

- El archivo `/app/data/trades.db` **persiste** entre deploys (Volume mount sobrevive al contenedor).
- El código crea la tabla si no existe (`init_db()` en startup) — idempotente, no borra data existente.

---

## Rollback si algo falla

Sin `TRACKER_DB` seteada, el bot vuelve a usar `"trades.db"` en raíz (comportamiento anterior).
Simplemente eliminar la env var en Railway y redeploya.
