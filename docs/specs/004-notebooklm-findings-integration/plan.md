# Plan 004 — NotebookLM Findings Integration

> **Spec:** [spec.md](spec.md)
> **Status:** IN PROGRESS

## Estrategia

Cambio quirúrgico en dos archivos. Una sola fase:

1. **config.py** — 4 constantes nuevas + auto-expire helper.
2. **stock_analyzer.py** — auto-expire wire en stock_watchdog (justo donde se evalúa QUANTUM_SUPPRESSED).

No se toca `tracker.py`, `scalp_alert_bot.py`, ni se agregan dependencias.

## Decisiones técnicas

### 1. `MAX_PER_CLUSTER_BY_CLUSTER` como dict, no global

Mantener `MAX_PER_CLUSTER = 2` como fallback default. Agregar dict per-cluster:

```python
MAX_PER_CLUSTER_BY_CLUSTER = {
    "nuclear": 2,
    "ai_infra": 2,        # default; PRIORITY_BOOST_CLUSTER ya overrides a 3 esta semana
    "quantum": 0,
    "crypto_proxy": 1,    # restringido hasta BTC > CRYPTO_PROXY_BTC_GATE
    "petroleras": 3,      # cobertura defensiva, riesgo bajo
    "defensivos": 3,
}
```

**Lookup:** `MAX_PER_CLUSTER_BY_CLUSTER.get(cluster_name, MAX_PER_CLUSTER)`. Backward-compat.

Razón: NotebookLM justificó cada número con cita al corpus. Es la primera vez que la configuración del bot refleja conocimiento sectorial extraído del análisis, no solo defaults arbitrarios.

### 2. `QUANTUM_SUPPRESSED_UNTIL` con auto-expire en runtime

Constante fecha string:

```python
QUANTUM_SUPPRESSED_UNTIL = "2026-06-01"
```

En `stock_watchdog`:

```python
from datetime import datetime as _dt
_today = _dt.now()
_quantum_expire = _dt.strptime(QUANTUM_SUPPRESSED_UNTIL, "%Y-%m-%d")
if _today >= _quantum_expire:
    QUANTUM_SUPPRESSED = []   # reset local
    logger.info("👁️ Centinela: QUANTUM_SUPPRESSED auto-expired (UNTIL=%s passed). Re-habilitando.", QUANTUM_SUPPRESSED_UNTIL)
```

Razón: skip permanente requería que Fernando recordara editar la lista. Auto-expire libera la responsabilidad y deja log visible en el ciclo siguiente.

Trade-off: si PTS no reactiva para 1-Jun, Fernando debe extender UNTIL manualmente. Aceptable — fecha es señal de "review check".

### 3. `CRYPTO_PROXY_BTC_GATE` como constante

```python
CRYPTO_PROXY_BTC_GATE = 74000.0   # PTS: pipeline crypto solo activa si BTC > $74k
```

Por ahora solo constante. Enforcement real requiere fetch BTC en `stock_watchdog` (Spec 005). Documentado como gap.

### 4. `MACRO_BONDS_WATCH` lista

```python
MACRO_BONDS_WATCH = ["TLT", "TBT"]   # bonos 20Y: vigilar rendimientos (PTS 8k - Jueves 29)
```

Constante referencial. Si bot detecta `TLT` o `TBT` en señales externas (futuro), tag como "MACRO_BONDS_WATCH". No alertas activas, solo etiqueta cuando aparezcan.

### 5. Sin enforcement de MAX_PER_CLUSTER (todavía)

`MAX_PER_CLUSTER_BY_CLUSTER` queda como **lookup table** consumible por código futuro. El enforcement requiere:
- `tracker.py` API para contar posiciones open por cluster.
- Hook en `_store_pending` para bloquear nueva alerta si cluster full.

Es trabajo de Spec 005. Por ahora, la dict deja la decisión documentada en código, no en CLAUDE.md prose.

## Implementación

### config.py

Justo después de `MAX_PER_CLUSTER = 2` (line ~192), agregar bloque:

```python
# Spec 004 (NotebookLM 2026-05-26): MAX por cluster específico
# Justificación detallada en docs/research/notebook-lm/RESULTS.md (Prompt 3).
# Lookup: MAX_PER_CLUSTER_BY_CLUSTER.get(cluster_name, MAX_PER_CLUSTER)
MAX_PER_CLUSTER_BY_CLUSTER = {
    "nuclear": 2,
    "ai_infra": 2,
    "quantum": 0,
    "crypto_proxy": 1,
    "petroleras": 3,
    "defensivos": 3,
}

# Spec 004: auto-expire de quantum suppression
QUANTUM_SUPPRESSED_UNTIL = "2026-06-01"

# Spec 004: gate de crypto proxies — solo abrir pipeline si BTC > este nivel
CRYPTO_PROXY_BTC_GATE = 74000.0

# Spec 004: bonos macro a vigilar para contexto (sin alertas directas)
MACRO_BONDS_WATCH = ["TLT", "TBT"]
```

### stock_analyzer.py

En `stock_watchdog()`, modificar el import de `QUANTUM_SUPPRESSED` y agregar auto-expire:

```python
from config import (
    QUANTUM_SUPPRESSED, WEEK_PRIORITY_HIGH, WEEK_PRIORITY_LOW,
    WEEK_REVIEW_DATE, QUANTUM_SUPPRESSED_UNTIL,
)
_quantum_expire = _dt.strptime(QUANTUM_SUPPRESSED_UNTIL, "%Y-%m-%d")
if _today >= _quantum_expire:
    QUANTUM_SUPPRESSED = []
    logger.info("👁️ Centinela: QUANTUM auto-expired (UNTIL=%s) — re-habilitando IONQ/RGTI.", QUANTUM_SUPPRESSED_UNTIL)
```

## Verificación

1. `python3 -m py_compile config.py stock_analyzer.py` → OK.
2. Imports check: todas las constantes nuevas accesibles.
3. Dry-run: forzar `QUANTUM_SUPPRESSED_UNTIL = "2026-05-25"` (ayer) → confirmar log "auto-expired" + lista vacía.
4. Restaurar `QUANTUM_SUPPRESSED_UNTIL = "2026-06-01"` → confirmar skip IONQ/RGTI activo hoy 26-May.

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(stock): spec-004 NotebookLM findings — cluster MAX, quantum auto-expire, BTC gate, bonds watch` |
| 2 | `docs: research/notebook-lm/* — corpus + 6 prompts + RESULTS consolidado` |
