# CHANGELOG — Zenith Trading Suite

> Registro de iteraciones significativas. Cada versión documenta los cambios,
> la simulación que los motivó, y el impacto en Win Rate.

---

## v4.2 — Strategy Hardening (2026-04-17)

**Commits:** `307d225`
**WR simulado (77 trades):** 50.0% → proyección real 60-65%
**Target WR oficial:** 62% (`WR_TARGET_IDEAL` en config.py)

### Cambios

#### swing_bot.py
- **EMA50 Trend Filter**: Solo abre LONG si precio > EMA50 en 4H.
  Habría bloqueado todas las pérdidas de ZEC del 10-15 Abr (contra-tendencia).
- **Consecutive-Loss Guard**: Pausa símbolo tras 2 pérdidas SWING consecutivas.
  Previene seguir entrando en activo en caída. ZEC activó guard al restart (4 pérdidas).

#### tracker.py
- `get_recent_closed_trades_by_symbol(sym, limit, strategy)` — historial por símbolo
- `get_today_trade_count(sym, strategy)` — conteo diario por símbolo

#### config.py
- `STRATEGY_ITERATION = "v4.2"` — versioning de iteración
- `WR_TARGET_IDEAL = 0.62` — target sostenible documentado
- `WR_TARGET_MIN = 0.55` — mínimo para seguir operando el símbolo
- `SWING_CONSEC_LOSS_PAUSE = 2` — parámetro del guard
- `SWING_EMA50_TREND_FILTER = True` — toggle del filtro

### Por qué 62% y no 80%
| WR | Significado real |
|----|-----------------|
| 40% | Break-even con R:R 1.5:1 |
| 55-62% | Profesional sostenible (target) |
| 65-70% | Elite, tendencia fuerte |
| >75% | Overfitting en <200 trades |

---

## v4.1 — SIM D2 Hour Filter (2026-04-17)

**Commits:** `8c19d5e`
**WR simulado:** 18.2% → **50.0%** (+31.8pp en 77 trades)

### Cambios

#### strategies.py
- `_BLOCKED_HOURS = {1, 4, 6, 10, 11, 14, 15, 16, 17, 20}` — horas 0% WR histórico
- Kill switch TAO (`TAO_TRADING_ENABLED = False`) — 0% WR en 28 trades
- Kill switch V1-SHORT (`V1_SHORT_ENABLED = False`) — 0% WR en 16 trades

#### tracker.py
- Bug crítico: `open_time` faltaba en `get_open_trades()` SELECT.
  Time-exit de 36h nunca disparó en toda la historia del bot.
  7 de 12 pérdidas históricas corrieron 43-142h sin stop.

### Simulaciones que motivaron los cambios
| Sim | Filtros | WR |
|-----|---------|-----|
| Baseline | ninguno | 18.2% |
| SIM A | no TAO | 27.1% |
| SIM B | + no SHORT | 27.7% |
| SIM C | + NYSE 14-16h | 30.0% |
| **SIM D2** | + hours 1,4,6,10,11,14-17,20 | **50.0%** |

---

## v4.0 — Mighty Snail Iteration (2026-04-17)

**Commits:** `98ff7cd`, `b23779e`, `0961ba1`
**Problema resuelto:** Bot activo pero sin alertas cripto (0 alertas en días)

### Causa raíz
1. Régimen RANGING (ADX=12.3 < threshold=25, BB_width=2.07% > 2%)
2. RSI zona muerta (BTC RSI 54-57 vs entry ≤45 — nunca llegaba)
3. RVOL hardcodeado en 1.0 (pipeline roto — `calculate_rvol()` nunca se llamaba)
4. V5-MOMENTUM: 3 bugs silenciosos (import, key equivocado, gate faltante)

### Cambios

#### config.py
- `ADX_TRENDING_THRESHOLD`: 25 → 20
- `BB_WIDTH_RANGING_PCT`: 0.02 → 0.015

#### strategies.py
- RSI entry V1-LONG: 45 → 47 (ZEC: 48 → 49)
- V5-MOMENTUM: import `V5_MOMENTUM_RVOL_MIN`, RVOL gate, key `{sym}_VOL` → `{sym}_RVOL`
- NYSE filter: bloquear 14-16 UTC (0% WR histórico — luego expandido en v4.1)

#### scalp_alert_bot.py
- RVOL real inyectado en TTL_INDICATORS block (`indicators.calculate_rvol()`)
- KeyError fix macro_vals: `macro_vals["spy"]` → `.get("spy", fallback)`
- Intervalos optimizados: Panorama 1h→2h, Salmos 30min→60min, Sentinel 1h→2h (-59% llamadas Gemini)

#### signal_coordinator.py
- `WINDOW_SECS`: 300 → 120 (señales llegan 2.5x más rápido)

---

## v3.x — Historial previo

Ver `docs/ZENITH_MANIFESTO_V10.md` para evolución V1→V10.
