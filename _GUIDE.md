# _GUIDE — Cómo funciona el bot (manual operacional)

> Para Fernando. Sin código. Lenguaje plano.
> Última actualización: 2026-05-09 (validado contra código por 5 auditores)
> Cobertura validada: 100% threads, 100% filtros, 88% comandos, 100% schema, 100% flujo señal→trade

---

## 1. ¿Qué es este bot?

Es un sistema automático de **monitoreo de mercado** que:

1. **Lee precios** de Binance Futures (crypto) + Yahoo Finance (acciones, oro, petróleo)
2. **Calcula indicadores** técnicos (RSI, EMA, BB, ATR, funding rates, etc.)
3. **Decide** si hay setup válido según reglas predefinidas
4. **Te avisa por Telegram** con botones [Activar] / [Skip] cuando encuentra algo
5. **Trackea tus trades** activados en una base de datos local
6. **Te alerta cuando** el precio toca SL/TP/BE de tus posiciones abiertas

**No ejecuta órdenes reales.** Solo te avisa. Tú decides si entras manualmente.

---

## 2. Los 7 hilos que corren en paralelo

Pensalo como **7 trabajadores** distintos cada uno haciendo su tarea:

| Hilo | Qué hace | Cada cuánto | Símbolos |
|------|----------|-------------|----------|
| **scalp_bot** | Busca entradas crypto LONG (V1/V3/V4/V5) | 35 segundos | ZEC, TAO, BTC, ETH, SOL, HBAR, DOGE, TON |
| **swing** | Busca entradas Ichimoku 4H (long/short) | 4 horas | ZEC, TAO, BTC, ETH, SOL |
| **commodities** | Busca entradas en metales/energía | 15 min | GOLD, OIL, NG, SLV, HG |
| **scalper_shorts** | Busca SHORTs scalper (NUEVO) | 15 min | DOGE, FIL, TAO |
| **stock** | Watchdog acciones US — alerta cuando precio toca entry de la lista PTS | 15 min | TSLA, NVDA, COIN, HOOD, etc. |
| **manual_monitor** | Revisa P&L de tus posiciones manuales (`/manual_add`) | 30 min | Las que tengas abiertas |
| **telegram** | Escucha tus comandos `/comando` | 5 segundos | — |

Todos tienen **auto-restart**: si se cae uno, se reinicia solo. Watchdog vigila heartbeat de cada uno.

---

## 3. Las 7 estrategias y cuándo disparan

### A. Crypto (scalp_bot loop)

| Estrategia | Cuándo dispara | Win rate histórico |
|-----------|----------------|-------------------|
| **V1-LONG** | RSI ≤ 45 (ZEC: ≤48) + precio sobre EMA200 + BB touch (bonus, no requerido) | 27% (49 trades antiguos) |
| **V3-REVERSAL** | RSI extremo (≤ 26-28) + precio bajo EMA200 — modo rescate | sin data reciente |
| **V4-EMA** | Precio dentro 2% de EMA200 + RSI 35-50 | sin data reciente |
| **V5-MOMENTUM** | RSI cruza 50 desde abajo | sin data reciente |
| **V1-SHORT** | RSI ≥ 55 + EMA bajando | ❌ DESHABILITADO (0% en 16 trades) |

**Importante:** estas 4 estrategias activas (V1, V3, V4, V5) están emitiendo señales pero **0 fueron activadas vía Telegram**. Es el flujo Activate/Skip — si no le das al botón, no se trackea.

### B. Swing (swing_bot, 4 horas)

Estrategia: **Ichimoku Kumo breakout**.
- Cuando precio rompe el "kumo" 4H al alza → LONG
- Cuando rompe abajo → SHORT
- **Niveles ATR-based:** SL = 2×ATR, TP1 = 2.5×ATR, TP2 = 5×ATR, TP3 = 8×ATR
- **Distribución de cierre sugerida:** 50% en TP1, 30% TP2, 20% TP3

**Histórico real:** 76 trades, **17.1% WR**. La gran mayoría perdedores. La causa fue el bug de TAO Apr 12-14 (ya parchado).

### C. Commodities (commodities_bot, 15 min)

Estrategia: **EMA cross + RSI + DXY filter**.
- LONG cuando EMA9 > EMA21 + RSI bajo + DXY débil
- SHORT cuando EMA9 < EMA21 + RSI alto

**Histórico real:** 12 trades, **25% WR**. Problema: GOLD LONG 0/6 — re-entries en pullback bajista (ya parchado con el fix de hoy).

### D. Scalper Shorts (scalper_shorts_bot, 15 min, NUEVO)

Estrategia: **5 condiciones, mínimo 4/5**:
1. RSI ≥ 65 (sobrecomprado)
2. Precio toca banda superior BB
3. Precio sobre EMA200 (zona alta)
4. EMA9 < EMA21 (cruce bajista reciente)
5. Funding rate > 0.03% (longs crowded)

**Win rate:** 0 trades aún (recién deployado). Acumular 20+ para juzgar.

---

## 4. Los 12 filtros que pueden bloquear una alerta

Antes de que llegue al Telegram, una señal pasa por **12 chequeos**. Si uno falla, no hay alerta:

```
Señal detectada
    ↓
1. ¿Hora bloqueada? (UTC 1, 4, 6, 10, 11, 14, 15, 16, 17, 20)  → 0% WR histórico
    ↓
2. ¿Circuit breaker activo? (3+ pérdidas seguidas → 4h pausa)
    ↓
3. ¿FOMC en próximas 24h? → suprime señales débiles
    ↓
4. ¿Phase != macro_status? (institutional alignment)
    ↓
5. ¿1D EMA200 bias = BEAR? → bloquea LONG (excepto RSI ≤ 30 = V3 rescate)
    ↓
6. ¿Loss streak por símbolo? (3 pérdidas en 4h → cooldown 4h)
    ↓
7. ¿ZEC volatilidad > 3.5%? → skip
    ↓
8. ¿Régimen = RANGING? → suprime todas
    ↓
9. ¿Ya hay trade abierto del mismo símbolo+side? → skip (no doblar)
    ↓
10. ¿RVOL < mínimo? (volumen relativo bajo)
    ↓
11. ¿Confluence score < mínimo? (V1: 4, V3: 4, V4: 3, V5: 3)
    ↓
12. ¿PHY bias activo? → fuerza modo RAPIDA (posición chica)
    ↓
✅ ALERTA TELEGRAM con [Activar] [Skip]
```

**Por eso a veces no hay alertas durante horas/días:** el mercado no califica según las reglas.

---

## 5. Flujo: alerta → trade → tracking

```
Bot detecta señal V1-LONG en BTC
    ↓
[Telegram] 🚨 V1-LONG BTC @ $80,150
            SL $79,000  TP1 $82,500  TP2 $84,000
            Confluencia 5/7
            [✅ Activar]  [⏭️ Skip]
    ↓
Tú decides → ✅ Activar
    ↓
log_trade() escribe en trades.db:
  - symbol=BTC, type=LONG, status=OPEN
  - entry=80150, sl=79000, tp1=82500
  - strategy_version=V1-TECH
  - alert_type=v1_long
    ↓
trade_monitor (cada 35s) revisa: ¿precio cruzó SL o TP?
    ↓
Si TP1 hit:
  - update status = PARTIAL_WON
  - append_event "TP1 HIT @ $82,500 → mover SL a BE"
  - Telegram: 🎯 TP1 HIT BTC
    ↓
Si SL hit:
  - update status = LOST
  - append_event "SL HIT @ $79,000"
  - Telegram: 🛑 SL HIT BTC
  - Circuit breaker registra pérdida
```

**¿Qué hace Skip?** Loggea la señal con `is_sim=1` para comparar después: "si la hubieras activado, ¿habrías ganado?"

---

## 6. Comandos Telegram que importan

### Menú visible en `/` (16 comandos esenciales)

**Diario:**
- `/pos` — posiciones abiertas (`/pos full` = detalle)
- `/check` — P&L + recomendaciones SL/TP por ATR
- `/open` — abrir posición manual (picker inline)
- `/winrate` — win rate global + Real vs SIM
- `/pnl` — ganancia/pérdida del día

**Mercado:**
- `/macro` — USDT.D + Macro Shield
- `/funding` — funding rates por símbolo
- `/commodities` — estado GOLD/OIL/NG/SLV/HG
- `/scalper_shorts` — estado DOGE/FIL/TAO scalper

**Posición manual:**
- `/manual_add SYM ENTRY [LONG|SHORT]` — registrar trade ya abierto
- `/manual_tp SYM [pct]` — cerrar parcial / TP
- `/manual_sl SYM` — marcar SL tocado
- `/manual_be SYM` — mover SL a break even
- `/manual_off SYM` — desactivar monitoreo

**Admin:**
- `/budget` — gasto IA (Gemini + Claude)

### Comandos avanzados (NO en menú, pero handlers activos)

Si los necesitás, los podés tipear igual:
- `/status` — precios + RSI + sentimiento AI (redundante con `/macro`)
- `/regime` — régimen actual (trending/ranging/volatile)
- `/audit` — auditoría institucional (Profit Factor, SQN)
- `/agents` — historial Cuadrilla Zenith
- `/circuit` — estado circuit breaker
- `/risk` — resumen de riesgo (ATR, VIX, position size)
- `/intel` — Social Intel & News Feed
- `/pause` / `/resume` — pausar bot
- `/logs [N]` — últimas N líneas del log
- `/stocks` — estado watchlist acciones
- `/bitlobo` — análisis BitLobo

---

## 7. Cómo verificar tu win rate

**Opción A — Telegram:**
```
/winrate
```
Muestra: WR global + Real (activadas) vs SIM (skipeadas).

**Opción B — SQL directo (cuando quieras detalle):**

```bash
sqlite3 trades.db
```

Queries útiles:
```sql
-- WR por estrategia
SELECT strategy_version,
  SUM(CASE WHEN status IN ('FULL_WON','PARTIAL_WON','PARTIAL_CLOSED','WON') THEN 1 ELSE 0 END) as wins,
  COUNT(*) as total
FROM trades WHERE (is_sim=0 OR is_sim IS NULL) AND status != 'OPEN'
GROUP BY strategy_version;

-- Trades del último mes
SELECT symbol, type, entry_price, sl_price, tp1_price, status, open_time
FROM trades WHERE open_time > date('now', '-30 days')
ORDER BY open_time DESC;
```

**Opción C — Dashboard web:**
- Local: http://localhost:5001
- Railway: el URL que te dio Railway al deploy
- Endpoints: `/api/stats`, `/api/trades`, `/api/metrics`

---

## 8. Tu base de datos (trades.db) en lenguaje plano

Tabla `trades` — cada fila = un trade activado o señal skipeada:

| Campo | Qué significa |
|-------|---------------|
| `id` | Número único del trade |
| `symbol` | BTC, ZEC, GOLD, TSLA, etc. |
| `type` | LONG o SHORT |
| `entry_price` | Precio al que entraste |
| `sl_price` | Stop loss |
| `tp1_price`, `tp2_price` | Targets |
| `status` | OPEN, FULL_WON, PARTIAL_WON, PARTIAL_CLOSED, LOST |
| `strategy_version` | V1-TECH, SWING, COMMODITY, SCALPER_SHORTS, MANUAL |
| `alert_type` | v1_long, v3_reversal, swing_institutional, commodity_conservative, scalper_short_v1, manual_long |
| `conf_score` | 0-7 — qué tan fuerte fue la señal |
| `is_sim` | 0 = activado real, 1 = skip (simulado) |
| `is_manual` | 1 = abierto vía /open, 0 = automático |
| `open_time`, `close_time` | Timestamps |

**Campos técnicos adicionales (audit/IA):**
- `msg_id` — ID del mensaje Telegram (para reply/update)
- `rsi_entry`, `bb_status`, `atr`, `elliott_wave` — snapshot indicadores en entry
- `ai_analysis`, `macro_bias`, `inst_score` — contexto IA
- `trigger_conditions` — JSON de condiciones que dispararon (⚠️ 0/91 pobladas — bug)
- `events_json` — historial timestamps de eventos (TP/SL/BE) (⚠️ 0/91 pobladas)
- `be_moved`, `partial_pct` — flags de gestión

**Tablas relacionadas:**
- `signal_episodes` — memoria de aprendizaje IA. 31/39 sin outcome (bug, ver `_BACKLOG.md`)
- `backtest_sessions` — resultados de backtests históricos
- `ai_calls` — **NO existe en producción** (función `ai_budget.init_db()` definida pero nunca llamada al startup)

---

## 9. ¿Qué hace cada agente IA?

### Cuadrilla Zenith (4 voces)
- **Genesis** — contexto macro histórico
- **Éxodo** — análisis técnico
- **Salmos** — psicología de mercado
- **Apocalipsis** — devil's advocate, riesgos

Votan en consenso. Output: LONG / SHORT / ESPERAR. Se invoca cuando hay señal V2-AI o `/agents` en Telegram.

### Personas Gemini (2 voces)
- **CONSERVADOR** — sesgo defensivo, largo plazo
- **SCALPER** — sesgo agresivo, intradía

Las 2 votan en cada señal V2-AI. Memoria diaria persiste en `memory/*.json`.

### BitLobo
Análisis por zonas (verde=soporte, rojo=resistencia). Aparece como línea 🐺 en debates Zenith.

### Costo IA
- Gemini Flash: gratis
- Claude Haiku: pago, cap $10/mes (config `ai_budget.py:26` `MAX_MONTHLY_USD`)
- **Estado real:** `ai_budget.py` tiene `init_db()` con tabla `ai_calls` definida, **pero nunca se invoca al startup** del bot. La tabla no existe en `trades.db` actual → tracking de costo IA no funciona en prod (ver `_BACKLOG.md` D2)

---

## 10. Estado actual del sistema (2026-05-09)

| Métrica | Valor |
|---------|-------|
| WR global histórico | 18.7% (91 trades) |
| WR por estrategia | SWING 17.1% / COMMODITY 25% / MANUAL 33% |
| Trades abiertos | 0 |
| Posiciones manuales | 0 (pendiente registrar las 6 de QF si aplica) |
| Circuit breaker | NORMAL (no disparado) |
| Branch prod | `main` (commit más reciente) |
| Símbolos activos crypto | DOGE, FIL, TAO en scalper_shorts; ZEC/TAO/BTC/ETH/SOL en swing |
| Símbolos activos commodities | GOLD, OIL, NG, SLV, HG |

**Bugs activos identificados:** 0 (los 2 críticos parchados hoy)
**Items diferidos:** ver `_BACKLOG.md`

---

## 11. Próximos pasos prioritarios

1. **Acumular 20+ trades nuevos** post-fixes (commodities cooldown + 1D filter + V3 reversal habilitado)
2. **Recalcular WR** en 2 semanas — esa será la métrica real del sistema corregido
3. **Si WR sigue < 35%** → considerar paper trading hasta tener edge demostrado en backtest
4. **Atacar items del `_BACKLOG.md`** cuando haya bandwidth (security, ai_calls table, trigger_conditions)

---

## 12. ¿Cómo se ve un día normal del bot?

```
00:00 UTC — bot corre
00:00:35 — scalp_bot ciclo: lee precios, evalúa V1/V3/V4/V5 en 8 símbolos
00:00:36 — bot encuentra: BTC RSI=58 (no califica) → continue
00:00:37 — ZEC RSI=79 (sobrecomprado, no LONG) → continue
00:00:38 — todos los símbolos filtrados → sin alertas este ciclo
00:01:13 — siguiente ciclo (35s después)
...
00:15:00 — commodities_bot ciclo: GOLD RSI=42 + EMA cross BULL → calcula score
00:15:02 — score 4/5 + 1D BEAR → bloqueado por nuevo filtro
00:15:03 — sin alerta GOLD
...
04:00 UTC — swing_bot ciclo (cada 4h)
04:00:10 — TAO 4H Ichimoku no rompe kumo → no alerta
04:00:11 — ZEC rompe kumo al alza → 🚨 ALERTA SWING-LONG ZEC
[Telegram] notifica con keyboard [Activar] [Skip]
```

Si el mercado no califica según las reglas, **el silencio es correcto**. No es bug, es disciplina.
