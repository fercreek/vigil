# Spec 004 — NotebookLM Findings Integration

> **Status:** IN PROGRESS 2026-05-26
> **Created:** 2026-05-26
> **Owner:** Fernando
> **Severity:** P1 — alinear bot con findings del análisis NotebookLM del corpus PTS Apr–May 2026
> **Origen:** `docs/research/notebook-lm/RESULTS.md`

## Contexto

NotebookLM deep dive produjo 6 outputs estructurados sobre el corpus PTS:

1. Tabla consolidada por símbolo (51 símbolos, 18 ACTIVE / 28 PENDING / 2 SUPPRESSED / 5 CLOSED).
2. 6 contradicciones identificadas entre reportes consecutivos.
3. Análisis sectorial con MAX_PER_CLUSTER recomendado por cluster.
4. Línea de tiempo del régimen SP500 (9 puntos · 3 inflexiones).
5. Análisis de ops cerradas + 2 filtros propuestos (EXPLOSIVE_CORRECTION + BARRIDA_OPPORTUNITY).
6. Plan accionable día-por-día semana 26-30 May.

## Findings críticos vs estado actual del bot

| # | Finding | Estado actual | Gap |
|---|---------|---------------|-----|
| 1 | `MAX_PER_CLUSTER` recomendado por cluster (nuclear=2, ai_infra=3 boost, quantum=0, crypto_proxy=1-2, petroleras=2-3, defensivos=3) | Global `MAX_PER_CLUSTER = 2` | No es por cluster; sin enforcement |
| 2 | `QUANTUM_SUPPRESSED_UNTIL = "2026-06-01"` con auto-expire | `QUANTUM_SUPPRESSED = ["IONQ", "RGTI"]` sin expire | Skip permanente, requiere manual edit |
| 3 | Crypto proxy gating: restringir hasta BTC > $74k | No existe | Sin gate, posible falsa señal |
| 4 | TLT/TBT bonos como vigilancia macro | No en watchlist | Trigger del Jueves 29 sin enforcement |
| 5 | Filtro `EXPLOSIVE_CORRECTION` (régimen AMARILLA→VERDE → boost explosivas) | No existe | Patrón RKLB +30% no replicado |
| 6 | Filtro `BARRIDA_OPPORTUNITY` (VIX<22 + SP500>7000 → no filtrar caídas intradía) | No existe | Patrón May-19 confirmado, no implementado |
| 7 | OKLO Earnings martes 27-May en EARNINGS_CALENDAR | ✅ Ya existe | OK |
| 8 | PRIORITY_BOOST_CLUSTER = "ai_infra" max 3 | ✅ Ya existe en config | Sin enforcement en código |

## Goals (qué se considera resuelto)

1. **`MAX_PER_CLUSTER_BY_CLUSTER`** dict por cluster en `config.py` (default 2, override por cluster).
2. **`QUANTUM_SUPPRESSED_UNTIL`** constante + auto-expire en `stock_analyzer.py`: si pasó la fecha, ignorar `QUANTUM_SUPPRESSED` y loguear info.
3. **`CRYPTO_PROXY_BTC_GATE = 74000.0`** constante simple. Stock analyzer skip alerts crypto proxies si BTC current < gate.
4. **`MACRO_BONDS_WATCH = ["TLT", "TBT"]`** lista para vigilancia macro (sin entry/SL, solo trigger contextual).

## Non-goals (P1 backlog para sesión siguiente)

- Filtro `EXPLOSIVE_CORRECTION` — requiere state machine de transiciones de régimen + persistencia.
- Filtro `BARRIDA_OPPORTUNITY` — requiere detector intradía de spikes bajistas en clusters específicos.
- Enforcement real de `MAX_PER_CLUSTER` — requiere conteo posiciones open via `tracker.py` (P1 ya documentado en Spec 003 backlog).
- Fetch BTC current price en stock_analyzer — agregar a `_fetch_prices` flow, requiere extender pipeline.

## Dependencias

- `config.py` — agregar constantes nuevas.
- `stock_analyzer.py:stock_watchdog()` — leer `QUANTUM_SUPPRESSED_UNTIL`, aplicar auto-expire.
- `docs/research/notebook-lm/RESULTS.md` — fuente de verdad.

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Auto-expire de QUANTUM antes que PTS reactive → bot dispara reentry prematura | Fecha conservadora 2026-06-01 (siguiente lunes). Si PTS aún no reactiva ese día, Fernando debe actualizar manual la fecha. Log INFO cuando expire para visibilidad. |
| `MAX_PER_CLUSTER_BY_CLUSTER` documentado pero sin enforcement | Documentar claramente en spec que la dict es solo lookup. Enforcement real es backlog P1 (requiere tracker). |
| BTC gate sin fetch real → constante muerta | Spec 004 deja constante. Spec 005 wires el fetch. Por ahora es referencia para Fernando. |

## Criterio de aceptación

1. `python3 -m py_compile config.py stock_analyzer.py` → OK.
2. Smoke test: si pongo `QUANTUM_SUPPRESSED_UNTIL = "2026-05-25"` (ayer), IONQ/RGTI dejan de ser skipped en el log.
3. Cluster lookup: `from config import MAX_PER_CLUSTER_BY_CLUSTER` → dict accesible.
4. Lunes 26 apertura (hoy): bot sigue suprimiendo IONQ/RGTI (UNTIL=2026-06-01 > 2026-05-26).
5. 1 Jun: auto-expire activa, IONQ/RGTI vuelven a watchlist con tags WEEK_PRIORITY normales.
