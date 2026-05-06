# CHANGELOG — Zenith Trading Suite

> Registro de iteraciones significativas. Cada versión documenta los cambios,
> la simulación que los motivó, y el impacto en Win Rate.

---

## v4.3 — Snappy UX + Alert Lifecycle + OIL Post-Mortem (2026-05-06)

**Branch:** `dev`  
**Archivos modificados:** `tracker.py`, `alert_manager.py`, `scalp_alert_bot.py`, `strategies.py`, `telegram_commands.py`, `manual_positions_monitor.py`, `config.py`, `commodities_bot.py`  
**Archivos nuevos:** `docs/SIGNAL_FLOW.md`, `scripts/migrate_manual_to_db.py`

### Motivación

1. **Manual ops duplicadas** — dos paths paralelos (JSON + DB) causaban estado fragmentado. `/positions`, `/portfolio`, `/manual`, `/health` mostraban datos distintos del mismo estado.
2. **No había control sobre señales** — cuando el bot detectaba setup, log_trade se ejecutaba inmediatamente sin que Fernando pudiera activar o skipear. Win rate contaminado con trades no deseados.
3. **OIL SL inmediato** — post-mortem identificó 3 bugs críticos en `commodities_bot.py` + falta de supresión OPEC.

---

### A. Unificación de storage manual

#### `tracker.py`
- **+columnas** `is_manual INTEGER DEFAULT 0`, `is_sim INTEGER DEFAULT 0`, `be_moved`, `partial_pct`, `events_json`, `note` — migration in-place via `ALTER TABLE`
- **+`get_trade_by_id(trade_id)`** — lookup preciso por ID, elimina race condition de `get_last_open_trade(sym)` cuando hay 2 trades del mismo símbolo
- **+`log_simulated()`** — loguea señal skiada como SIM (is_sim=1) para trackear win rate paper
- **+`append_event(trade_id, event)`** — log de acciones sobre el trade (OPENED, ACTIVATED, CLOSED, BE moved, etc.)
- **+`get_open_manual_trades()`** — retorna trades con is_manual=1
- **+`mark_be(trade_id)`**, **+`mark_partial(trade_id, pct)`** — helpers atómicos
- **+`update_trade_levels()`** — ajusta SL/TP/entry post-apertura

#### `manual_positions_monitor.py`
- **Refactor completo**: eliminado `_load_store()` / `_save_store()` / JSON. Lee y escribe sobre `trades.db` filtrando `is_manual=1`.
- Misma lógica de recomendaciones PTS, mismos comandos `/manual_*` — cero ruptura de API.

#### `config.py`
- Eliminado `MANUAL_POSITIONS = [...]` (seed hardcoded TAO/ZEC/DOGE en drawdown).
- Agregado `MANUAL_SYMBOLS = ["TAO","ZEC","DOGE","SOL","BTC","ETH"]` — picker de /open.

#### `scripts/migrate_manual_to_db.py` (nuevo)
- One-shot migration de `manual_positions.json` → `trades.db` con `is_manual=1`.
- Idempotente: skip si ya existe trade abierto para el mismo símbolo.
- Archiva JSON como `.archived` al terminar.

---

### B. Alert Activate/Skip lifecycle

#### `alert_manager.py`
- **+`get_signal_keyboard(sid, sym, side)`** — keyboard de decisión pre-activación:
  `[✅ Activar SYM SIDE] [⏭️ Skip] [📊 Ver niveles] [💰 Budget]`
- **+`get_management_keyboard(trade_id, sym, side)`** — keyboard post-apertura:
  `[✅ TP1 50%] [✅ TP2 80%] [🏆 TP3] [🛑 SL] [🔴 Cerrar@live] [📊 P&L]`
- Callback data usa `trade_id` en posición 1: `tp1:TRADE_ID:SYM:SIDE` — lookup preciso por ID.
- Backward compat: callbacks legacy `tp1:SYM:SIDE` (3 parts) siguen funcionando.

#### `scalp_alert_bot.py`
- **+`_PENDING_SIGNALS` dict** — almacena params de señal hasta que Fernando decide. TTL 4h, GC automático en cada callback.
- **+`_store_pending()`** — guarda params, retorna `signal_id` para usar en callback_data.
- **+`_gc_pending_signals()`** — limpia señales expiradas, llamado en cada callback.
- **+Callbacks nuevos en `_handle_callback`:**
  - `activate:SID:SYM:SIDE` → `log_trade(is_sim=0)` real + edita mensaje con management keyboard + transfiere `episode_id` de `pending_ep_ids` → `episode_ids`
  - `skip:SID:SYM:SIDE` → `log_simulated(is_sim=1)` + edita mensaje "⏭️ skiada"
  - `close_now:TRADE_ID:SYM:SIDE` → cierra al precio live, determina WON/LOST por PnL
  - `pnl:TRADE_ID:SYM` → muestra P&L flotante con lookup preciso por trade_id
- **Fix TP/SL lookup**: si callback tiene 4 partes y `parts[1].isdigit()` → usa `get_trade_by_id()` (preciso). Si 3 partes → legacy `get_last_open_trade(sym)`.
- **Management keyboard en `open_confirm`**: después de confirmar `/open`, el mensaje se edita con TP/SL/Cerrar buttons (antes solo mostraba texto sin botones de gestión).

#### `strategies.py`
- **7 puntos desacoplados** (V1-SHORT, V3-Reversal, V1-LONG, V2-AI-LONG, V4-EMA-BOUNCE, V2-SHORT/Consensus, V5-Momentum):
  - Antes: `alert()` → `log_trade()` inmediato
  - Ahora: `_store_pending()` → `alert(inline_keyboard=get_signal_keyboard(sid,...))` → NO log_trade
  - `episode_ids` guardados en `pending_ep_ids[sid]` hasta activación — se transfieren a `episode_ids[trade_id]` en callback activate

---

### C. Snappy manual ops — Telegram UX

#### `telegram_commands.py`
- **+`compute_levels(side, price, atr)`** — helper reusable para SL/TP via ATR. Llamado desde `/open` confirm y `LONG SYM` free-text.
- **+`cmd_open(prices)`** — handler de `/open`, retorna mensaje + picker keyboard.
- **+`cmd_pos(args, prices)`** — vista unificada de posiciones:
  - `/pos` compact: `SYM SIDE @ entry → current (PnL%) 🟡/🤖`
  - `/pos full`: + SL/TP/BE/tiempo + recomendaciones del monitor + health del bot
- **Aliases**: `/positions`, `/portfolio`, `/health` → `cmd_pos`. `/manual` → lista manual (DB).
- **`LONG SYM` free-text**: ahora loguea con `is_manual=1` y envía management keyboard adjunto (antes: menú estático sin botones de gestión).

#### `alert_manager.py` — keyboard principal
- Row 1 actualizado: `[📊 Mercado] [📈 Acciones] [🎯 Setup]` → `[📂 /pos] [➕ /open] [🎯 Setup]`

---

### D. Commodities bot — OIL post-mortem fixes

**Root cause:** OIL LONG ~$101 (May 6) → SL hit en una vela 1H (OPEC+ anunció aumento producción, drop $3.60 en 60 min).

#### `commodities_bot.py`
- **+OPEC suppression**: `OPEC_MEETING_DATES = ["2026-05-05","2026-06-01","2026-09-01"]` — suprime señales OIL ±24h. Mismo patrón que FOMC en crypto.
- **Fix RSI SHORT**: `45 < rsi < 65` (zona bullish) → `rsi > 62` (overbought real).
- **SL por instrumento**: `ATR_SL_BY_KEY = {"GOLD": 1.5, "OIL": 2.5}` — OIL necesita más margen para spikes de noticias.
- **MIN_SL_PCT_OIL = 0.020**: SL mínimo 2% del precio en OIL — el 1H ATR puede ser menor a un spike de noticia.
- **Post-rally filter**: Si OIL sube >15% en 10 días → RSI máximo para LONG = 45 (normal: 55). Bloquea entradas overbought después de rallies.
- **Signal keyboard**: usa `_store_pending` + `get_signal_keyboard` (Activar/Skip) en lugar de `log_trade` inmediato.
- Fallback: si falla import/send → loguea directamente (no rompe el bot).

#### `docs/STRATEGY_AUDIT.md`
- Sección "Post-Mortem: OIL LONG May 6" con root cause, tabla de errores, código de fix, lección del sistema.

---

### E. Documentación

#### `docs/SIGNAL_FLOW.md` (nuevo)
Documentación completa del ciclo de vida de señales:
- Flujo auto-señal (detección → pending → Activar/Skip → gestión → cierre)
- Flujo manual `/open` 3-tap
- Flujo `LONG SYM` free-text
- Tabla de management keyboard con todos los callbacks
- Taxonomy de estrategias (strategy_version × alert_type × macro_regime)
- Win rate real (is_sim=0) vs simulado (is_sim=1) — SQL queries
- Campos clave de `trades` table
- Commands reference

---

### Win Rate impacto esperado

| Área | Antes | Después | Mecanismo |
|------|-------|---------|-----------|
| Win rate real | contaminado (trades no deseados) | solo trades activados | Activate/Skip filter |
| Win rate sim | N/A | trackeable | `log_simulated` en Skip |
| OIL WR (8.3%) | 1/12 | reducir falsas entradas ~30% | OPEC + RSI + post-rally |
| Fragmentación estado | 2 stores (JSON+DB) | 1 store (DB) | storage unificado |

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
