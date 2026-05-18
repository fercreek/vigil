# _AUDIT_LOG — Zenith Trading Suite
> Entradas más recientes arriba. Baseline pre-fixes: WR global = **18.7%** (91 trades).


---

## Audit 2026-05-18 — Checkpoint 14d

**DB:** ⛔ DB no encontrada en `/home/user/vigil/trades.db` — sin Railway Volume o TRACKER_DB no seteada
**Trades stuck:** ✅ Sin trades stuck

> ⚠️ Volumen <10 trades — considerar relajar `MIN_CONFLUENCE_SCORE` 5→4 o `RVOL_MIN_ENTRY` 0.8→0.7

### WR Global 14d

| Métrica | Valor | vs Baseline 18.7% |
|---------|-------|-------------------|
| WR global | N/D | — |
| Trades cerrados | 0 | — |
| Wins | 0 | — |
| Losses | 0 | — |
| PF estimado (2:1 R:R) | N/D | ⬜ Sin datos |

**Régimen:** ⬜ Sin datos

### WR por Estrategia

_Sin trades cerrados en la ventana._

### REAL vs SIM

| Tipo | WR | Trades |
|------|----|--------|
| REAL (activados) | N/D | 0 |
| SIM (skiados) | N/D | 0 |

### Acciones

- 🔴 **1** — Configurar Railway Volume + env var `TRACKER_DB=/app/data/trades.db` (ver `docs/VOLUME_SETUP.md`)

---

## Audit 2026-05-18 — Checkpoint 14d post-fixes (May 9)

**Auditor:** Claude Code (remote) · **Branch:** main · **HEAD:** `843aa58`

---

### 1. Verificación de fixes en código

| Fix (May 9) | Estado | Evidencia |
|-------------|--------|-----------|
| `V1_LONG_ENABLED = False` | ✅ Confirmado | `config.py:162` — comentario: "15.4% WR / -34.1% PnL → disabled May 2026" |
| V3-REVERSAL dispara en BEAR 1D si RSI ≤ 30 | ✅ Confirmado | `strategies.py:287-290` — excepción explícita: `rsi > RSI_LONG_EXTREME → bloqueado`, si ≤ 30 pasa |
| `V4_BLOCKLIST = ["ETH"]` | ✅ Confirmado (ampliado) | `config.py:163` — lista actual: `["ETH", "ZEC"]` (ZEC agregado por walk-forward overfit) |
| `V5_ENABLED = False` | ✅ Confirmado | `config.py:164` — "0 trades en backtest 365d → bug o filtro muy restrictivo" |
| swing_bot keyboard Activar/Skip | ✅ Confirmado | `swing_bot.py:259` — "Enviar con keyboard Activar/Skip (mismo flujo que commodities/scalper_shorts)" |
| commodities_bot cooldown 8h post-LOST | ✅ Confirmado | `commodities_bot.py:106` — `POST_LOST_COOLDOWN = 3600 * 8` + `_in_post_lost_cooldown()` |
| commodities_bot filtro 1D EMA200 GOLD/SLV | ✅ Confirmado | `commodities_bot.py:254` — función `_bias_1d_for_key()`, bloquea LONG si BEAR |
| `ai_budget.init_db()` en startup | ✅ Confirmado | `main.py:87-88` — llamado antes de arranque de threads |

**Fix extra no mencionado en tarea:** `V4_BLOCKLIST` incluye también `"ZEC"` (degradación -100% walk-forward). Correcto.

---

### 2. WR últimos 14d — DATO NO DISPONIBLE

**Razón: arquitectura sin persistencia.**

La base de datos `trades.db` vive en el contenedor Railway sin Volume mount persistente (`_BACKLOG.md S2`). Cada redeploy borra el historial completo. Desde el 9-May hubo **6 deploys** (commits `688deb4`, `e1e3c2b`, `42ee6ef`, `8927548`, `8f485b5`, `eb6b2a1`), con la última ventana limpia iniciando el **13-May** → 5 días efectivos, no 14d.

El archivo `docs/reporte_ayer.md` confirma estado reset: `"Trades Totales: 0"`.

**No es posible calcular WR, PF ni Expectancy real sin Volume mount.** Esta es la causa principal de que el audit carezca de métricas live.

---

### 3. Análisis WR — Estimado por contexto de código

Sin DB, el análisis se basa en lo que el código permite ahora vs antes:

| Estrategia | Status actual | WR backtest | Señales esperadas 14d |
|------------|--------------|-------------|----------------------|
| V3-REVERSAL BTC | ✅ Activa | ~27.8% | 2-4 (mercado lateral BTC) |
| V3-REVERSAL ETH | ✅ Activa pero V4_BLOCKLIST bloquea V4 | ~27.8% | 1-3 |
| V3-REVERSAL TAO | ✅ Activa | ~27.8% | 1-3 |
| V3-REVERSAL ZEC | ✅ Activa | ~27.8% | 1-2 |
| V4-EMA BTC | ✅ Activa | ~23.5% | 0-2 (requiere EMA proximity) |
| V4-EMA TAO | ✅ Activa | ~23.5% | 0-1 |
| V4-EMA ETH/ZEC | ❌ Blocklisted | — | 0 |
| V1-LONG | ❌ Disabled | 15.4% | 0 |
| V5-MOMENTUM | ❌ Disabled | 0% | 0 |
| SWING Ichimoku | ✅ Activa (keyboard fix) | ~17% | 1-3 |
| COMMODITIES (GOLD/OIL/etc) | ⚠️ Thread COMENTADO | ~25% | 0 |
| SCALPER_SHORTS | ⚠️ Thread COMENTADO | sin data | 0 |

**Total estimado 14d:** 5-18 señales → volumen en umbral mínimo (_SPEC §7.1: mín 5 trades activados).

---

### 4. Validación de comportamientos esperados

| Comportamiento | Estado | Detalle |
|----------------|--------|---------|
| `trigger_conditions` poblado en `log_trade()` | ✅ Sí | Todas las estrategias llaman `build_trigger_conditions()` antes de `_store_pending()` — `strategies.py:512,589,653,711,773` |
| GOLD sin re-entries inmediatos (cooldown 8h) | ⚠️ Código OK, bot OFF | `_in_post_lost_cooldown()` funciona, pero `commodities_bot` está comentado desde May-13 (`8f485b5`) por RAM opt |
| V3-REVERSAL dispara en BEAR 1D si RSI ≤ 30 | ✅ Funciona | Lógica correcta en `strategies.py:289`. RSI > 30 → bloqueado. RSI ≤ 30 → pasa |
| SCALPER_SHORTS activo | ❌ No activo | Comentado en `main.py:104` por RAM — "score=1/5 nunca dispara + ccxt futures propio" (`8f485b5`) |
| AutoSIM en cada señal | ✅ Activo (desde May-12) | `42ee6ef` — `auto-SIM on signal fire` |
| Daily report 13:00 UTC | ✅ Thread activo | `main.py:103` — `_start_thread("daily_report", ...)` |

---

### 5. Delta vs Baseline 18.7%

| Métrica | Baseline (pre-fix) | Live 14d | Delta |
|---------|-------------------|----------|-------|
| WR global | 18.7% (91 trades) | **N/D** — DB sin persistencia | — |
| PF global | ~0.9 (estimado) | N/D | — |
| Volumen trades | — | **~0-5** (5d útiles post-último deploy) | ↓ |
| Contaminación swing auto-log | ❌ existía | ✅ eliminada (keyboard fix) | mejora estructural |
| Señales V1-LONG generando ruido | ❌ existían | ✅ 0 señales (disabled) | mejora estructural |

**Conclusión:** No es posible medir delta WR. Los fixes estructurales están en código y son correctos. El problema es de **infraestructura de datos**, no de estrategia.

---

### 6. Top 3 acciones

| Prioridad | Acción | Impacto |
|-----------|--------|---------|
| 🔴 **1 — URGENTE** | Configurar Railway Volume mount `/app/data` ($0.25/GB/mo). Sin esto ningún audit futuro tendrá datos reales. El historial de 9 días post-fixes ya se perdió. Ver `_BACKLOG.md S2`. | Desbloquea TODOS los audits futuros |
| 🟡 **2** | Decidir si reactivar `commodities_bot` y `scalper_shorts_bot`. Ambos comentados por RAM (`8f485b5`). SCALPER_SHORTS: score=1/5 nunca dispara — validar threshold o dejarlo muerto. COMMODITIES: útil pero requiere RAM adicional (~65 MB). | Amplía fuentes de señal |
| 🟢 **3** | Con Volume activo: re-run este audit en 7 días con DB real. Si volumen <10 trades → relajar `MIN_CONFLUENCE_SCORE` 5→4 según criterio _SPEC §7.1. | Cierra el loop de validación |

---

### 7. Clasificación según criterios _SPEC §7.3

> No aplica — volumen <5 trades reales medibles (ventana efectiva 5d, DB reseteada 6 veces).

**Aplicar regla:** *"Si volumen < 10 trades → relajar filtros"* — pero primero resolver S2 (Volume mount) para tener datos limpios antes de cambiar parámetros.

---

**Próximo checkpoint:** 2026-05-23T15:00:00Z (según _NEXT.md) — **solo útil si Railway Volume está activo antes del 2026-05-19.**
