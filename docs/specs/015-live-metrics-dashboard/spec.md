# Spec 015 — Live Metrics Dashboard

> **Status:** CODE COMPLETE 2026-05-26
> **Owner:** Fernando
> **Severity:** P1 — Roadmap NotebookLM 4 Prompt 6 Spec 016
> **Origen:** `docs/research/notebook-lm-4/RESULTS.md` Prompt 6 — panel web ligero para health del bot sin SQL manual

## Contexto

Hoy revisar WR / distribución por símbolo / performance por estrategia requiere queries SQL a mano (`sqlite3 trades.db ...`). Esa fricción retrasa decisiones operativas (kill TAO si WR=0%, expandir COMMODITY si WR>55%, validar SWING contra benchmark).

Métrica de éxito (NotebookLM Prompt 6, roadmap): **"Fernando puede ver health del bot sin querys SQL manuales"**.

Stack actual ya tiene `app.py` (Flask) corriendo en Railway + local — solo falta nueva ruta + endpoints JSON + template HTML.

## Goals

1. `GET /dashboard/live` — HTML page server-side rendered con secciones: header (uptime, total trades), Win Rate global con badge color-coded, tabla por símbolo, tabla por estrategia, recent activity (20 últimos), signal episodes summary.

2. `GET /api/metrics/wr` — JSON con `{global, by_symbol, by_strategy}`.

3. `GET /api/metrics/recent_trades` — JSON con últimos N trades + status.

4. `GET /api/metrics/signal_episodes_summary` — JSON con `{total, outcome_breakdown, by_source, orphans}` (referencia Spec 002 huérfanas).

5. Helper module `dashboard_metrics.py` — SQL aislado, testeable, reutilizable. Funciones: `compute_global_wr`, `compute_wr_by_symbol`, `compute_wr_by_strategy`, `get_recent_trades`, `get_signal_episodes_summary`, `get_dashboard_snapshot`.

6. Mobile-friendly + dark theme + auto-refresh 60s (vanilla JS).

## Non-goals

- Autenticación (dashboard local + Railway no público) → Spec 015.5 candidato
- Charts/gráficas interactivas (Chart.js, Plotly) → Spec 015.6 candidato
- Frameworks frontend pesados (React, Vue, Bootstrap, jQuery) — pure CSS + vanilla JS por filosofía bot
- WebSockets push real-time → cada 60s reload es suficiente para uso humano
- Filtros UI (date range, symbol multi-select) → Spec 015.7 candidato
- Endpoint `/metrics/regime` con HMM Spec 009 → Spec 015.8 cuando HMM esté hooked en config

## Dependencias

- `trades.db` con tabla `trades` (91 rows) ✅
- `trades.db` con tabla `signal_episodes` (39 rows, Spec 002) ✅
- Flask + Jinja2 ya cargados en `app.py` ✅
- `templates/` directorio existe (tiene `index.html`) ✅

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Query lenta degrada UX cuando trades > 10k | LIMIT en todas las queries + indexed columns (id DESC, symbol, status) |
| SQLite locked durante write del bot main | Conexión read-only `mode=ro` + timeout=2.0s + try/except → dict vacío |
| Dashboard expuesto públicamente en Railway | NO autenticación este spec (riesgo aceptado — Railway URL no indexada). Spec 015.5 si público |
| Race condition entre helper y bot escribiendo trades.db | sqlite3 maneja WAL — lecturas no bloquean writes |
| Auto-refresh 60s consume bandwidth Railway free tier | `document.visibilityState` check — pausa si tab oculta |
| Template Jinja2 falla por símbolo None / status NULL | `or '—'` defaults + `_error` keys filtrados en template |

## Criterio de aceptación

1. `python3 -m py_compile dashboard_metrics.py app.py` → OK
2. `python3 -c "from dashboard_metrics import compute_global_wr; print(compute_global_wr())"` retorna dict con `global_wr` key
3. `python3 dashboard_metrics.py` produce snapshot JSON válido (smoke test)
4. Curl `GET /dashboard/live` → 200 HTML con secciones esperadas
5. Curl `GET /api/metrics/wr` → 200 JSON `{global: {...}, by_symbol: {...}, by_strategy: {...}}`
6. Render mobile (DevTools 375px) sin overflow horizontal
7. WR badge color cambia: <30%=red, 30-50%=yellow, >50%=green
8. Auto-refresh JS pausa cuando tab oculta (verificable en Network tab DevTools)
