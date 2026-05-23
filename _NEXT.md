# _NEXT.md — Scalp Bot / Zenith
> Update: 2026-05-23 · Prev: `db3681d`
> **Sesión cerrada — análisis exhaustivo activo. Ver spec-002.**

---

## ⚡ En proceso (retomar aquí)

- [ ] Verificación día siguiente mercado vivo — ver `docs/specs/002-alert-noise-failure-audit/tasks.md` sección "Verificación pendiente"
- [ ] Confirmar PULSO + PANORAMA suprimidos (quiet on)
- [ ] Confirmar `ai_calls` se llena en `trades.db` raíz (no `data/`)
- [ ] Confirmar `data/stock_alert_cache.json` se crea + persiste

## ✅ Sesión 2026-05-23 — Alert noise audit + 4 failure modes

| Commit | Fix |
|--------|-----|
| `c299b09` | PULSO/PANORAMA gate + Sentinel RSI filter |
| `94bec99` | ENABLE_TELEGRAM_BUTTONS kill switch |
| `94e3cb6` | P0: quiet mode + AI DB fix + TAO kill + stock outcomes |
| `db3681d` | 4 failure modes: signal_coordinator + retry + heartbeat + cache persist |

Spec completo: [`docs/specs/002-alert-noise-failure-audit/`](docs/specs/002-alert-noise-failure-audit/)

## 🔒 Bloqueado

- Logs Railway necesarios para validar stock thread health post-deploy (Fernando debe pegar `railway logs --service zenith-bot` si hay incidencia)

---

## 🎯 Spec maestro

**LEER PRIMERO:** [`_SPEC.md`](_SPEC.md) — único punto de verdad de qué se hizo + criterios de aceptación validación 2 semanas.

---

## ✅ Sesión 2026-05-13 — Fixes aplicados

| Commit | Fix |
|--------|-----|
| `688deb4` | Singleton ccxt compartido + `enableRateLimit` — elimina weight 3-4x |
| `688deb4` | HourFilter: removidas horas 01 y 14 (tenían WR positivo) |
| `e1e3c2b` | Ninja pre-alerta en bot — Telegram cuando RSI entra zona trigger |
| `e1e3c2b` | Confirmación trade: mensaje nuevo al activar (no solo editar) |
| `42ee6ef` | AutoSIM: cada señal crea SIM automático al disparar |
| `8927548` | Fallback OHLCV: Binance → Bybit → KuCoin (ante 403s) |

**Todos deployados en Railway. AutoSIM confirmado funcionando en logs.**

---

## 💰 Tracking de costos Railway (post optimización 2026-05-13)

Baseline + targets en `docs/COST_BASELINE.md`.

**Reminders manuales:**
- [ ] **2026-05-20** — Checkpoint semana 1: abrir https://railway.com/workspace/usage, comparar Memory minutely GB vs baseline (target -35%). Si < -20% → Round 3.
- [ ] **2026-05-22** — Checkpoint fin de ciclo (May 21 cerró): actualizar `docs/COST_BASELINE.md` con resultados reales del ciclo completo.

Commits relevantes: `8f485b5` (Round 1), `eb6b2a1` (Round 2), `21c4d9a` (baseline doc).

---

## ⏰ Próxima acción: 2026-05-23 (NO ANTES)

**Auditoría automática** correrá sola via routine `trig_01QjZVU9531oqK9pvNUoWSzF` el 2026-05-23T15:00:00Z (09:00 Mty) y appendea a `_AUDIT_LOG.md`.

**Hasta entonces:** dejar al sistema correr en Railway. NO tocar config. NO iterar. Solo recolectar data.

**Daily reports automáticos** llegarán cada día 13:00 UTC (≈8 AM EST) con PnL/PF/Expectancy del trailing 7d/24h/30d.

---

## 📊 Estado al cierre (2026-05-09)

**Backtest agregado (5 rondas tuning):**
```
PnL agregado:  +59.11% → +492.09%   (+433pp absolute, ~8.3x)
Profit Factor: 1.15 → 2.21          (institutional grade ≥ 2.0)
Trades:        253 → 238             (mejor calidad por trade)
```

**Walk-forward OOS (validación):**
- ETH V3: +15.9% test ✅ (campeón)
- ZEC V3: +21% test ✅ (alto edge)
- ZEC V4: +1.4% test ✅ (robust)
- TAO V3: -3% test (marginal, mejora vs -14.7% pre-r4)
- BTC V3: +2.7% test (overfit pero +OOS)

**Estrategias activas:**
- ✅ V3-REVERSAL (BTC ETH TAO ZEC) — core
- 🟡 V4-EMA (BTC TAO solo, ETH+ZEC blocklisted)
- 🟡 SWING (con keyboard fix)
- 🟡 COMMODITIES (con cooldown 8h post-LOST + 1D filter)
- 🆕 SCALPER_SHORTS (sin data aún)
- ❌ V1-LONG / V1-SHORT / V5-MOMENTUM (killed)

---

## 🚨 Si el bot falla durante validación

**Triggers para rollback (ver `_SPEC.md §11`):**
- PF live < 0.5 con n>10
- Bot crashes >3 veces/semana
- Trades stuck (OPEN >7d)

**Comando rollback rápido (vuelve pre-sesión):**
```bash
git checkout f99ea27^  # antes de los kill switches y tuning
```

---

## 🎯 Criterios decisión 2026-05-23 (auditor automático aplicará)

| Resultado live | Acción siguiente |
|----------------|------------------|
| **WR ≥ 35% AND PF ≥ 1.5** | ✅ pagar TradingView Essential, ronda 6 (Hyperopt) |
| **WR 25-35%** | 🟡 atacar items `_BACKLOG.md` (D1 trigger_conditions, D5 near_miss) |
| **WR < 25%** | 🔴 paper trading, audit slippage/comisiones reales vs backtest |
| **Volumen <10 trades 14d** | Relajar `MIN_CONFLUENCE_SCORE` 5→4 o `RVOL_MIN_ENTRY` 0.8→0.7 |

---

## 📋 Items backlog para post-validación

Si data live confirma edge → ronda 6 (en orden de impacto):

1. **Hyperopt-light** vía Freqtrade — V3 RSI por símbolo, 500 épocas
2. **Per-strategy + per-symbol weights** (no solo símbolo)
3. **VWAP RANGING strategy** — cubrir gap lateral (Q1 2026 todas perdieron)
4. **TradingView Pine webhook** — solo si edge confirmado
5. **Régimen detection refinement**

Otros items diferidos en `_BACKLOG.md`:
- 🔴 S1: rotar secrets `.env` (security)
- 🔴 S2: Railway Volume mount (data persist)
- 🟡 D1: poblar `trigger_conditions` JSON
- 🟡 D5: near_miss logging
- 🟢 C1-C7: refactor + tests

---

## 🧠 Filosofía vigente

> "No somos rentables todavía. Step by step. PF > 1.3 = ganando. WR alone es vanity."

3 strikes y muere. Iterar con data, no intuición. Cada decisión documentada.

---

## 📚 Docs leer en orden

1. **`_SPEC.md`** ← maestro, leer SIEMPRE primero
2. `_GUIDE.md` — manual operacional (sin código)
3. `_BACKTEST_HISTORICO.md` — historia + rondas tuning
4. `_STRATEGY_LIFECYCLE.md` — política de iteración
5. `_ITERATION_LOG.md` — log auditable de patches
6. `_BACKLOG.md` — items diferidos
7. `_AUDIT_LOG.md` — auditoría automática (se llena 2026-05-23)
