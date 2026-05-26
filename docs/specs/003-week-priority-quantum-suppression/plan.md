# Plan 003 — Week Priority + Quantum Suppression

> **Spec:** [spec.md](spec.md)
> **Status:** IN PROGRESS

## Estrategia

Cambio quirúrgico en `stock_analyzer.py` `stock_watchdog()`. Una sola fase:

1. Lee constantes nuevas de `config.py` (ya agregadas).
2. En el loop por símbolo, gate 1 (suppression) + gate 2 (priority tag).
3. Stale check antes del loop (warning si >7d).

No se toca `alert_manager.py`, `signal_coordinator.py`, ni `scalp_alert_bot.py` — el tag es solo cosmético del mensaje.

## Decisiones técnicas

### 1. Skip vs alert-with-warning para QUANTUM_SUPPRESSED

**Decisión:** skip total. Cero alerta Telegram para IONQ/RGTI.

Alternativa rechazada: alertar con tag "⚠️ SOBREEXTENDIDO — esperar reentry PTS". Razón rechazo: Daniel fue explícito "hasta que tengan corrección enviaremos reentrada". Ruido innecesario.

Fernando puede preguntar via `/bitlobo IONQ` si necesita opinión manual — esa vía no se afecta.

### 2. Pullback detector real vs manual override

**Decisión:** manual override por ahora. Fernando edita `QUANTUM_SUPPRESSED = []` cuando PTS publique reentry.

Alternativa rechazada: bot calcula max 7d y compara `current < max * (1 - PULLBACK_PCT/100)`. Razón: PTS define "corrección" cualitativamente, no por % fijo. Auto-reactivar riesgo de false positive si retroceso técnico no es el que Daniel esperaba.

Trade-off aceptado: requiere disciplina de Fernando para limpiar lista. `WEEK_REVIEW_DATE` stale check fuerza revisar semanal.

### 3. Tag en msg vs columna en signal_episodes

**Decisión:** tag prepended al string del mensaje Telegram.

Razón: cero impacto downstream. `signal_episodes` se llena de `entry/sl/tp` del dict, no del msg. Backtester ya tiene su propio campo `source`.

Si futuro queremos analytics por prioridad → agregar columna `priority` a `signal_episodes`. Out of scope.

### 4. Orden checks priority

```python
if t in WEEK_PRIORITY_HIGH:
    priority_tag = "🔥 PRIORIDAD ALTA (PTS semana)\n"
elif t in WEEK_PRIORITY_LOW:
    priority_tag = "🟢 DEFENSIVA — estable\n"
else:
    priority_tag = ""
```

WEEK_PRIORITY_MEDIUM no tagea (default behavior). Razón: medium ≈ default attention level, no necesita visual distintivo.

### 5. Stale check WEEK_REVIEW_DATE

Si `(today - WEEK_REVIEW_DATE).days > 7`:
- Log WARNING `"Priorities stale (>7d). Ignoring WEEK_PRIORITY_*."`
- `priority_tag = ""` para todos.
- `QUANTUM_SUPPRESSED` sigue activo (es decisión humana, no caduca tan rápido).

Trade-off: si Fernando se va de viaje 8 días el bot empieza a comportarse default. Aceptable — prioridad stale es worse que default.

## Implementación

**Archivo único:** `stock_analyzer.py`

1. Import constantes nuevas (top de `stock_watchdog`).
2. Stale check pre-loop.
3. Gate 1 (`continue` si `t in QUANTUM_SUPPRESSED`).
4. Compute `priority_tag` post-gate.
5. Prepend `priority_tag` a msg en `ZONE_ALERT` (line ~324) y `ENTRY_ALERT` (line ~340).

Cero cambios fuera de ese archivo.

## Verificación

1. `python3 -m py_compile stock_analyzer.py` → OK.
2. Imports: confirmar `QUANTUM_SUPPRESSED`, `WEEK_PRIORITY_HIGH`, `WEEK_PRIORITY_LOW`, `WEEK_REVIEW_DATE` accessible.
3. Dry-run mental: símbolo IONQ → skip. CRWV → tag HIGH. XOM → tag LOW. NVDA → no tag (no en ninguna lista).
4. Confirmar lunes 26-May post-apertura: logs muestran skip IONQ/RGTI + tags en alerts reales.

## Commits planeados

| # | Hash | Scope |
|---|------|-------|
| 1 | (pending) | `feat(stock): spec-003 week priority + quantum suppression — PTS 25-May` |
