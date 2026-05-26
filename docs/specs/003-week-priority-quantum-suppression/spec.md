# Spec 003 — Week Priority + Quantum Suppression (PTS 25-May-2026)

> **Status:** IN PROGRESS 2026-05-25
> **Created:** 2026-05-25
> **Owner:** Fernando
> **Severity:** P1 — alinear alertas a plan semanal Daniel Marin antes de apertura lunes 26-May

## Contexto

PTS publicó "análisis rápido" 25-May 23:00 con plan semana 26-30 May:

- **SP500 VERDE_BULL confirmado** (gap alcista futuros, >7000).
- **Vigilancia activa** (Daniel monitoreando esta semana): COIN, CRWV, CORZ, CIFR (AI-infra → movimientos alcistas próximos).
- **En zona entrada todavía:** UUUU, OKLO, SMR (nucleares).
- **Defensivas estables** (suben despacio): XOM, CVX, XLE, VAL, JNJ, KO, CL, MO.
- **Sobreextendidas — esperar corrección:** IONQ, RGTI (cuánticas). NO reentry.
- **Ya hicieron move:** ASTS, RKLB. Hold ganadores.

Cita Daniel: *"hasta que tengan una corrección enviaremos una reentrada"* — explícito para cuánticas.

## Problema raíz

Bot trata todos los símbolos del `STOCK_WATCHLIST` por igual:

1. **IONQ + RGTI** ya en `STOCK_WATCHLIST` con entry levels de hace 2 semanas (PTS 19-22 May). Si precio retrocede al entry viejo, bot dispara `ENTRY_ALERT` aunque PTS explícitamente dijo NO reentry hasta corrección significativa.
2. **CRWV/CORZ/CIFR/COIN** = prioridad alta esta semana, pero sus alertas se mezclan con XOM/JNJ/KO en feed Telegram. Fernando no distingue cuál mira primero.
3. **DEFENSIVE_SECTORS + SECTOR_CLUSTERS + WEEK_PRIORITY_*** constantes existen en `config.py` pero **ningún módulo las consume**. Context-only, no operativas.

## Goals

1. **IONQ + RGTI:** bot NO dispara `ENTRY_ALERT` ni `ZONE_ALERT` mientras estén en `QUANTUM_SUPPRESSED`. Log debug visible.
2. **WEEK_PRIORITY_HIGH** símbolos: alerta Telegram lleva etiqueta `🔥 PRIORIDAD ALTA (PTS semana)` para que Fernando los vea distintos.
3. **WEEK_PRIORITY_LOW** símbolos: alerta lleva etiqueta `🟢 DEFENSIVA — estable, sube despacio` para distinguir del urgente.
4. Override manual fácil: variable `WEEK_REVIEW_DATE` en config. Si han pasado >7 días sin actualizar → bot ignora prioridades (vuelve a comportamiento default) y loguea WARNING. Evita prioridades stale.
5. Sin tocar dedup logic ni cambiar thresholds de distancia (0.5%) — solo tagging + skip.

## Non-goals

- Cablear `MAX_PER_CLUSTER` / `PRIORITY_BOOST_CLUSTER` (no hay enforcement de posiciones simultáneas en código aún — feature pendiente).
- Reordenar `STOCK_WATCHLIST` por prioridad (irrelevante para alert flow actual).
- Implementar pullback detector real para reactivar IONQ/RGTI (manual override por ahora — Fernando edita `QUANTUM_SUPPRESSED` cuando PTS envíe reentry).
- Cambiar confluence threshold por símbolo.
- Auto-fetch nuevo reporte PTS (skill `cortex-macro-intel` ya lo hace manual).

## Dependencias

- `config.py` — constantes ya agregadas (commit pendiente).
- `stock_analyzer.py:265-510` — `stock_watchdog()` loop principal de alertas stocks.
- `CLAUDE.md` sección 8k — contexto humano.

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Olvidar quitar IONQ/RGTI de `QUANTUM_SUPPRESSED` cuando PTS reactive | `WEEK_REVIEW_DATE` stale check loguea WARNING en cada ciclo si >7d |
| Tag visual rompe parsers downstream (signal_episodes parse msg) | Tag va prepended al cuerpo; parser usa entry/sl/tp del dict, no del msg |
| PRIORIDAD ALTA causa fatiga si todos los símbolos están en HIGH | HIGH actual = 4 símbolos (COIN/CRWV/CORZ/CIFR). Threshold dist 0.5% sigue limitando frecuencia |
| WEEK_PRIORITY shadowing — un símbolo en HIGH también en LOW | Lista checks: HIGH primero, return. LOW solo si no HIGH. |

## Criterio de aceptación

1. Lunes 26-May NYSE apertura: bot loguea `"👁️ Centinela: IONQ SUPRIMIDA"` + `"RGTI SUPRIMIDA"` cuando llegan en loop. No envía Telegram.
2. Si COIN/CRWV/CORZ/CIFR alcanzan zona entrada → mensaje Telegram empieza con `🔥 PRIORIDAD ALTA`.
3. Si XOM/JNJ/etc. alcanzan zona entrada → mensaje Telegram empieza con `🟢 DEFENSIVA`.
4. Si Fernando deja `WEEK_REVIEW_DATE` sin actualizar 1 semana → log WARNING + bot ignora `WEEK_PRIORITY_*`.
