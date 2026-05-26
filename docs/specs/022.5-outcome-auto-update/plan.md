# Plan 022.5 — Outcome Auto-Update

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Decisiones técnicas

### 1. Hook en `update_trade_status` (chokepoint único)

Toda mutación de `trades.status` pasa por esta función. grep confirma — es el SQL UPDATE único para status field. Hook aquí captura 100% de las transitions sin tener que reachear `mark_partial`, `episode_memory.resolve_outcome`, etc.

### 2. Mapping status → outcome

```python
FULL_WON / WON          → "WIN"
PARTIAL_CLOSED / PARTIAL_WON → "PARTIAL"
LOST                    → "LOSS"
```

PARTIAL_WON existe en codebase (mark_partial) pero PARTIAL_CLOSED es el más común (Spec 002 close flow). Ambos mapean a "PARTIAL" en intel_outcomes para no duplicar segmentos en stats.

### 3. WHERE outcome IS NULL

```sql
UPDATE intel_outcomes
SET outcome = ?, outcome_filled_at = CURRENT_TIMESTAMP
WHERE alert_id = ? AND outcome IS NULL
```

Razón: si un human/script ya updated outcome manual (rare), no sobreescribir. Auto-update es solo para defaults NULL.

### 4. try/except wrap

```python
try:
    ...
except Exception as _e:
    print(f"[intel_outcomes auto-update ERROR] trade_id={trade_id}: {_e}")
```

Trade close flow NO debe fallar si intel_outcomes UPDATE fails. Trade.status update ya commiteado antes del bloque intel — atomicity per concern.

### 5. PnL queda None

Computar PnL real requiere close_price (no disponible en update_trade_status signature). Spec 022.6 candidato: extender signature con `close_price` param + calcular `pnl_pct = (close - entry) / entry * 100` con signo según direction.

Por ahora outcome categorial es suficiente para A/B WR analysis.

### 6. Connection separada para intel_outcomes

```python
_conn = sqlite3.connect(DB_FILE)
_c = _conn.cursor()
...
_conn.close()
```

Razón: el `conn` original ya `.close()` antes del hook. Nueva conexión transient — SQLite single-writer es OK, no race con bot main.

## Verificación

- ✅ py_compile tracker.py
- ✅ Insert intel + create trade row id=99999 + update_trade_status → outcome='WIN' verified
- ✅ 5 status mappings test correctos
- ✅ Log visible `📊 [intel_outcomes] auto-updated alert_id=X → OUTCOME`

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(metrics): spec-022.5 outcome auto-update hook — intel_outcomes via update_trade_status` |

## Backlog Spec 022.6

- Computar PnL real (extend update_trade_status signature con close_price)
- Hook en `episode_memory.resolve_outcome` también (para signal_episodes que NO crean trade row pero sí intel — e.g. alerts skipped/SIM)
- Dashboard endpoint `/api/metrics/intel_ab` exponer WR distribution chart (Spec 020.7 candidato)
- Retroactive update: script one-shot para llenar intel_outcomes históricos via JOIN trades close_time
- Notificación Telegram cuando A/B segment achieves stat significance (e.g. boost_3+ WR > boost_0 WR + 5pp con N≥30)
