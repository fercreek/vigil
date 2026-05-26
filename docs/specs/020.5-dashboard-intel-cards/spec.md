# Spec 020.5 — Dashboard Intel Cards (Frontend HMM + CVD + Whale + Social)

> **Status:** CODE COMPLETE 2026-05-26
> **Owner:** Fernando
> **Severity:** P1 — visibilidad UI data ya disponible vía endpoints
> **Origen:** Spec 020 backlog

## Contexto

Spec 020 expuso 4 endpoints REST con data intel (`/api/metrics/regime`, `/cvd/<sym>`, `/onchain_eth`, `/social/<sym>`). Dashboard live (Spec 015) los IGNORA — Fernando tendría que hacer curl manual.

Spec 020.5 agrega 4 secciones nuevas en `templates/dashboard_live.html` con fetch JS async + render cards mobile-friendly.

## Goals

1. Nueva sección "📡 Intel en Vivo (Spec 020.5)" en dashboard_live.html, debajo de Recent Activity
2. 4 sub-sections:
   - **HMM Régimen por Símbolo** (5 cripto: BTC/ETH/SOL/ZEC/TAO)
   - **CVD Spot** (BTC, ETH)
   - **Whale Netflow ETH 24h**
   - **Social Sentiment** (BTC, ETH, SOL)
3. Vanilla JS fetch async (no frameworks). Paralelo via Promise.all.
4. Auto-refresh 30s del intel (más frecuente que page reload 60s).
5. Color coding:
   - STRONG_TREND verde, RANGE amarillo, VOLATILE_SQUEEZE rojo
   - BULLISH/FEAR verde, BEARISH/EUPHORIA rojo
   - Datos faltantes — gris muted

## Non-goals

- Charts time-series (no Chart.js todavía — Spec 020.6)
- Mostrar histórica de transiciones régimen (Spec 002.6)
- HTTP Basic auth (Spec 015.5)
- WebSocket real-time push (Spec 020.7)
- Botones acción (manual override, refresh button) — Spec 020.8

## Dependencias

- Endpoints Spec 020 ✅
- `templates/dashboard_live.html` ✅ Spec 015
- Filosofía Spec 015: pure HTML+CSS+vanilla JS, no frameworks

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Endpoint fail → card vacío | Mensaje "—" gris muted, no crash |
| Promise.all fail si un endpoint timeout | Each fetch try/catch individual |
| Intervalo 30s spam Railway con queries | Cache TTL endpoints (60s CVD, 30min social, 5min whale, sin cache regime+HMM 15min Spec 009.6) absorbe |
| CSS responsive en mobile <320px | `grid-template-columns: repeat(auto-fill, minmax(160px,1fr))` se adapta |
| JS error rompe page entire | IIFE async + try/catch alrededor de fetchJson |
| Fernando no ve update en tab fondo | Reload page check visibilityState (heredado Spec 015) |

## Criterio de aceptación

1. Abrir `/dashboard/live` → 4 nuevas secciones visibles
2. Si endpoints retornan data → cards con valores + color
3. Si endpoint falla → "—" gris muted (no crash)
4. Auto-refresh cada 30s actualiza intel sin reload página
5. Mobile <600px: grid se ajusta a columnas adaptable
6. Producción Railway URL: `https://[url]/dashboard/live` muestra intel cards
