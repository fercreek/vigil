# _SPEC.md — Zenith Trading Suite (Spec-Driven Development)

> **Sesión 2026-05-09** — Cierre antes de validación 2 semanas.
> Documento maestro: requirements → diseño → criterios de aceptación → validación.
> Único punto de verdad para lo que el sistema **debe hacer** y **cómo se valida**.

---

## 0. Vision / Mission

**Vision:** Sistema de monitoreo y alertas de trading con edge probado data-driven.

**Mission:** Generar señales de calidad (PF ≥ 1.5) sobre crypto + commodities con tracking transparente, sin pretender ser rentable hasta que la data en vivo lo demuestre.

**No-goals:** ejecutar trades autónomos, replicar Freqtrade/Jesse desde cero, depender de APIs pagas.

---

## 1. Componentes del sistema

### 1.1 Threads activos (8)

| Thread | Archivo | Loop | Propósito |
|--------|---------|------|-----------|
| `scalp_bot` | `scalp_alert_bot.py` | 35s | Crypto V3-REVERSAL + V4-EMA |
| `swing` | `swing_bot.py` | 4H | Ichimoku Kumo breakout |
| `telegram` | `scalp_alert_bot.py` | 5s | Comandos + callbacks |
| `stock` | `stock_analyzer.py` | 15min | Watchlist PTS (alertas, no auto-trade) |
| `commodities` | `commodities_bot.py` | 15min | GOLD/OIL/NG/SLV/HG |
| `manual_monitor` | `manual_positions_monitor.py` | 30min | P&L de posiciones manuales |
| `scalper_shorts` | `scalper_shorts_bot.py` | 15min | DOGE/FIL/TAO SHORT scalper |
| `daily_report` | `daily_report.py` | 24h @ 13:00 UTC | Reporte automático Telegram |

Watchdog (`thread_health.py`) auto-restart con MAX_RESTARTS=5.

### 1.2 Estrategias activas (con WR backtest 365d)

| Estrategia | Símbolos | Status | Backtest 365d | Walk-forward OOS |
|-----------|----------|--------|---------------|------------------|
| **V3-REVERSAL** | BTC, ETH, TAO, ZEC | ✅ CORE | 18 trades, 27.8% WR, **+63.8% PnL, PF ∞** | ETH +15.9% / ZEC +21% (campeones) |
| **V4-EMA** | BTC, TAO (sin ETH/ZEC) | 🟡 KEEP | 51 trades, 23.5% WR, -0.8% PnL | ZEC V4 +1.4% robust |
| **SWING Ichimoku** | BTC ETH TAO ZEC SOL | 🟡 keyboard fix | 76 trades hist, 17% WR (auto-log contaminó) | sin walk-forward (4H) |
| **COMMODITIES** | GOLD OIL NG SLV HG | 🟡 con fixes | 12 trades hist, 25% WR | sin walk-forward (yfinance) |
| **SCALPER_SHORTS** | DOGE FIL TAO | 🆕 sin data | — | requiere 4 semanas |
| ~~V1-LONG~~ | — | ❌ KILLED | -34% PnL en 53 trades | — |
| ~~V1-SHORT~~ | — | ❌ KILLED | 0% WR en 16 trades | — |
| ~~V5-MOMENTUM~~ | — | ❌ DISABLED | 0 trades en 365d (bug filtros) | — |

### 1.3 Config crítica (post 5 rondas tuning)

```python
# === Estrategias toggles ===
V1_LONG_ENABLED      = False   # killed: 15.4% WR / -34% PnL
V1_SHORT_ENABLED     = False   # killed: 0% WR / 16 trades
V5_ENABLED           = False   # killed: 0 trades en 365d
TAO_TRADING_ENABLED  = False   # Spec 001 (May-22-2026): 0/31 WR — killed
V4_BLOCKLIST         = ["ETH", "ZEC"]  # walk-forward overfit confirmado

# === V3-REVERSAL per-symbol RSI ===
RSI_REVERSAL_BY_SYMBOL = {
    "TAO": 28.0,   # estricto (V3 OOS mejoró de -14.7% a -3.0%)
    "ZEC": 30.0,   # alto edge OOS (+21%)
    "ETH": 32.0,   # campeón OOS (+15.9%)
    "BTC": 32.0,   # marginal +OOS
}

# === Tuning data-driven (ronda 5) ===
RSI_LONG_ENTRY         = 40.0   # era 45 (laxo +)
MIN_CONFLUENCE_SCORE   = 5      # era 4 (filtro estricto)
ATR_TP1_MULT           = 3.0    # era 2.0 (R:R ambicioso)
ATR_MIN_SL_PCT         = 0.012  # era 0.007
RVOL_MIN_ENTRY         = 0.8    # era 1.0 (más volumen permitido)
ADX_TRENDING_THRESHOLD = 25     # era 20 (filtro trending estricto)
BB_WIDTH_RANGING_PCT   = 0.010  # era 0.015
V3_MAX_HOLDING_BARS    = 96     # era 48 (V3 necesita tiempo para reversal)
V4_EMA_PROXIMITY_MAX   = 1.020  # era 1.025
V4_EMA_PROXIMITY_MIN   = 1.005  # era 1.001
MTF_RSI_4H_MAX         = 50.0   # NEW: multi-TF V3 filter (sin impacto medible aún)
```

### 1.4 Sizing weights (test_suite.py)

```python
SYMBOL_WEIGHTS = {"BTC": 0.8, "ETH": 1.5, "TAO": 0.7, "ZEC": 1.2}
# Basado en walk-forward edge: ETH campeón → boost, TAO marginal → trim
```

---

## 2. Data flow / arquitectura

```
┌──────────────────────────────────────────────────────────────────┐
│ FUENTES DE DATOS                                                  │
│  Binance Futures (ccxt)  ·  CoinGecko (fallback)                 │
│  Yahoo Finance (commodities + stocks)                             │
│  CryptoPanic / LunarCrush (opcional)                              │
└────────────┬─────────────────────────────────────────────────────┘
             ↓ fetch + cache (TTL 20-600s)
┌──────────────────────────────────────────────────────────────────┐
│ GLOBAL_CACHE (scalp_alert_bot.py)                                 │
│  prices, indicators, macro_metrics, social_intel, fear_greed     │
└────────────┬─────────────────────────────────────────────────────┘
             ↓
┌──────────────────────────────────────────────────────────────────┐
│ STRATEGY EVALUATION (12 filtros secuenciales)                     │
│  1. Hour blacklist  2. Circuit breaker  3. FOMC                  │
│  4. Phase alignment 5. 1D EMA200 bias   6. Loss streak           │
│  7. Volatility cap  8. Régimen RANGING  9. Position guard        │
│ 10. RVOL min       11. Confluence ≥5   12. PHY bias              │
└────────────┬─────────────────────────────────────────────────────┘
             ↓ (si pasa todo)
┌──────────────────────────────────────────────────────────────────┐
│ _store_pending() → _PENDING_SIGNALS dict (TTL 4h)                 │
│ Telegram: alert con keyboard [✅ Activar] [⏭️ Skip]                │
└────────────┬─────────────────────────────────────────────────────┘
             ↓ (user click)
┌──────────────────────────────────────────────────────────────────┐
│ tracker.log_trade() → trades.db (SQLite)                          │
│   strategy_version: V1-TECH | SWING | COMMODITY | SCALPER_SHORTS │
│   is_sim: 0=ACTIVATED, 1=SKIPPED                                  │
└────────────┬─────────────────────────────────────────────────────┘
             ↓
┌──────────────────────────────────────────────────────────────────┐
│ trade_monitor (cada 35s) → SL/TP/BE auto-detect                  │
│ daily_report (24h) → PnL/PF/Expectancy a Telegram                │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. Spec por componente

### 3.1 V3-REVERSAL — Estrategia core

**Trigger:**
```
SI phase == "LONG"
AND price < EMA200 (1H)
AND regime ∈ {VOLATILE, TRENDING_DOWN}
AND RSI ≤ RSI_REVERSAL_BY_SYMBOL[sym]   # 28-32 según símbolo
AND NO en FOMC proximity (24h)
AND NO en bias 1D BEAR (excepto si RSI ≤ 30 — bypass V3)
AND NO en hora bloqueada
AND NO en loss streak 4h
AND NO ya posición abierta del símbolo
AND RVOL ≥ 0.8
AND confluence_score ≥ 5
AND (opcional: rsi_4h ≤ 50)
ENTONCES → emitir alerta SHORT keyboard
```

**Targets:**
- SL = entry - max(ATR × 2.0, price × 0.012)
- TP1 = entry + ATR × 3.0  (R:R 1.5:1 con SL=2x)
- TP2 = entry + ATR × 3.5
- TP3 = entry + ATR × 7.0

**Gestión:**
- TP1 hit → mover SL a BE (entry × 1.001)
- TP2 hit → close FULL_WON
- SL hit → close LOST + circuit breaker hit
- Max holding: 96 bars (96h ≈ 4 días)

### 3.2 V4-EMA Bounce

**Trigger:**
```
SI phase == "LONG"
AND sym NOT IN V4_BLOCKLIST  # excluye ETH, ZEC
AND EMA200 × 1.005 ≤ price ≤ EMA200 × 1.020   # 0.5%-2% sobre EMA
AND 35 ≤ RSI ≤ 50 (V4_RSI_HIGH=44 BTC, 50 ZEC)
AND RSI > prev_RSI (rising)
AND regime == TRENDING_UP
ENTONCES → emitir alerta LONG keyboard
```

**SL ajustado: ATR × 1.5 (V4_ATR_SL_MULT)**

### 3.3 SWING Ichimoku 4H

**Trigger:** kumo breakout 4H + bias IA semanal alineado.
**Targets:** ATR multiplicadores 2.5/5/8 con distribución sugerida 50/30/20%.
**Cooldown:** 4H entre alertas, 24H direction flip.

**Fix sesión actual:** ahora usa `_store_pending()` + keyboard (antes auto-loggeaba sin pedir confirmación → contaminó el WR histórico).

### 3.4 COMMODITIES (GOLD/OIL/NG/SLV/HG)

**Trigger:** EMA9/21 cross + RSI + DXY filter + ATR confirmación. Min confluence 4/5.

**Guards específicos:**
- OPEC suppression OIL ±24h reuniones
- Post-rally OIL +15% en 10d → RSI max 45 LONG
- Gold bull lock: GOLD > $2,500 → no SHORT
- SP500 > 7,000 → no SHORT en OIL
- **Post-LOST cooldown 8h** (fix sesión actual)
- **1D EMA200 filter GOLD/SLV LONG** (evita re-entries en pullback bajista)

### 3.5 SCALPER_SHORTS

**Trigger SHORT (5 condiciones, mín 4/5):**
1. RSI ≥ 65
2. price ≥ BB_upper × 0.99
3. price > EMA200
4. EMA9 < EMA21
5. funding_rate > 0.03%

**Macro guard:** si 1D EMA200 = BEAR → skip (ya bajando, no scalp).

### 3.6 daily_report (NUEVO)

**Trigger:** cada día 13:00 UTC (configurable via env `DAILY_REPORT_HOUR_UTC`).

**Contenido:**
- WR 24h / 7d / 30d con delta vs baseline 18.7%
- **PnL acumulado · Profit Factor · Expectancy** (métricas reales)
- Top símbolo ganador/perdedor 7d
- Costo IA del mes
- Estado circuit breaker

---

## 4. Test suite canónica (`test_suite.py`)

**Suite oficial:** 7 períodos × 4 símbolos × 4 estrategias = 112 combos.

```python
PERIODS = [
    ("2025_FULL",  "2025-04-01", "2025-12-31"),
    ("2025_Q2",    "2025-04-01", "2025-06-30"),
    ("2025_Q3",    "2025-07-01", "2025-09-30"),
    ("2025_Q4",    "2025-10-01", "2025-12-31"),
    ("2026_M01",   "2026-01-01", "2026-01-31"),
    ("2026_M02",   "2026-02-01", "2026-02-28"),
    ("2026_M03",   "2026-03-01", "2026-03-29"),
]
SYMBOLS    = ["BTC", "ETH", "TAO", "ZEC"]
STRATEGIES = ["V1", "V3", "V4", "V5"]
```

**Métricas reportadas:**
- PnL agregado total
- Profit Factor global
- Trades total / wins / WR
- Pesos por símbolo aplicados

**Uso:**
```bash
python3 test_suite.py --label "baseline" --json /tmp/baseline.json
python3 backtester.py --symbols BTC ETH TAO ZEC --strategies V3 V4 --mode walk_forward
python3 iterate.py    # itera patches con keep/revert automático
```

**Estado actual del suite:**
```
PnL agregado:   +492.09%  ← post 5 rondas tuning
Profit Factor:    2.21
Trades total:      238
WR global:        16.8%
Pesos:            BTC 0.8 / ETH 1.5 / TAO 0.7 / ZEC 1.2
```

---

## 5. Política de iteración (3-strikes-and-kill)

**Definida en `_STRATEGY_LIFECYCLE.md`:**

Una iteración = cambio de parámetro o lógica + 14 días de data nueva o backtest 365d.

**Edge probado** requiere (con muestra ≥ 20 trades):
- PF ≥ 1.3
- Expectancy > 0% por trade
- Walk-forward degradation < 30%

**Kill switch automático:**
- 3 iteraciones sin mejora → retirar estrategia
- Aplicado: V1-LONG, V1-SHORT, V5-MOMENTUM

---

## 6. Telegram hygiene policy

**Reglas vigentes (post audit + cleanup ronda 5):**

✅ **Permitido:**
- Entrada con keyboard Activate/Skip (1 msg/señal)
- TP/SL/BE outcome (1 msg consolidado por evento)
- Trailing stop update (cooldown 15min)
- Daily report (1 msg/día @ 13:00 UTC)
- Comandos usuario (respuesta inmediata)

❌ **Prohibido:**
- ALTCOIN SENTINEL (eliminado)
- SALMOS PROPHECY (KILL_SALMOS_PROPHECY=True)
- NEURAL LEARNING reply spam (eliminado)
- Logs de sistema ("ciclo completado")
- Mensajes >10 líneas (templates simplificados ronda 5)

**Comandos visibles en menú (16):**
- Diario: /pos /check /open /winrate /pnl
- Mercado: /macro /funding /commodities /scalper_shorts
- Manual: /manual_add /manual_tp /manual_sl /manual_be /manual_off
- Admin: /budget

---

## 7. Criterios de aceptación — validación 2 semanas (2026-05-09 → 2026-05-23)

### 7.1 Métricas mínimas a observar

**Trigger checkpoint automático:** routine `trig_01QjZVU9531oqK9pvNUoWSzF` correrá 2026-05-23T15:00:00Z (09:00 Mty) y appendea a `_AUDIT_LOG.md`.

| Métrica | Threshold OK | Threshold KILL |
|---------|--------------|----------------|
| PF global 14d | ≥ 1.3 | < 0.8 con n>20 |
| WR mejorado vs baseline 18.7% | ≥ 25% | < 18% |
| ETH V3 (campeón teórico) | PF ≥ 2.0 | PF < 1.0 |
| ZEC V3 | PF ≥ 1.5 | PF < 0.8 |
| TAO V3 | PF ≥ 1.0 | PF < 0.5 |
| Volumen señales | 5-20 trades activados | <2 (filtro muy estricto) o >50 (spam) |
| Telegram volumen mensajes | -50% vs sesión anterior | sin cambio (cleanup falló) |

### 7.2 Validaciones específicas

- [ ] `trigger_conditions` columna se puebla en cada `log_trade()` call (audit D1 backlog)
- [ ] `events_json` columna se puebla con TP/SL events
- [ ] `ai_calls` table funciona (ya init en main.py startup)
- [ ] swing_bot ya NO auto-loggea trades (keyboard Activate/Skip vigente)
- [ ] Daily report llega cada día a Telegram a las 13:00 UTC
- [ ] Ningún ALTCOIN SENTINEL en Telegram
- [ ] TP/SL templates consolidados visibles
- [ ] SWING + COMMODITIES alerts < 10 líneas

### 7.3 Decisiones disparadas por checkpoint

**Si WR ≥ 35% AND PF ≥ 1.5:**
- ✅ Sistema validado. Considerar pago TradingView Essential ($14.95/mo).
- ✅ Continuar acumulando data para ronda 6 (Hyperopt-light)

**Si WR 25-35%:**
- 🟡 Edge marginal. Atacar items `_BACKLOG.md` (D1 trigger_conditions, D5 near_miss)
- Mantener config actual

**Si WR < 25%:**
- 🔴 Edge no confirmado live. Investigar gap backtest vs prod.
- Posibles causas: slippage real, comisiones reales, latencia Telegram→activación
- Considerar pause temporal para análisis profundo

**Si volumen < 10 trades en 14d:**
- Filtros muy restrictivos. Relajar `MIN_CONFLUENCE_SCORE` 5→4 o `RVOL_MIN_ENTRY` 0.8→0.7

---

## 8. Inventario de docs (artefactos sesión)

| Doc | Propósito |
|-----|-----------|
| **_SPEC.md** (este) | Spec maestro — único punto de verdad |
| **_GUIDE.md** | Manual operacional sin código (Fernando) |
| **_BACKTEST_HISTORICO.md** | Análisis multi-período + 5 rondas iteración |
| **_STRATEGY_LIFECYCLE.md** | Política 3-strikes + matriz régimen × estrategia |
| **_ITERATION_LOG.md** | Log de cada patch keep/revert (auditable) |
| **_BACKLOG.md** | Items diferidos (security, ops, limpieza) |
| **_AUDIT_LOG.md** | Auditoría automática recurrente (futuro 2026-05-23) |
| **_NEXT.md** | Pickup point sesión |
| **docs/ARCHITECTURE.md** | Arquitectura técnica completa |
| **docs/STRATEGY_RULES.md** | Reglas operativas legacy |
| **CLAUDE.md** | Reglas + contexto PTS |

---

## 9. Inventario de scripts (artefactos sesión)

| Script | Función |
|--------|---------|
| `test_suite.py` | Runner canónico 7 períodos × 4 símbolos × 4 estrategias |
| `iterate.py` | Loop iteración con keep/revert automático + log |
| `daily_report.py` | Reporte automático Telegram (PnL/PF/Expectancy) |
| `scalper_shorts_bot.py` | Agente SHORT scalper DOGE/FIL/TAO (NUEVO) |
| `backtester.py` | Backtester con CLI walk-forward (`--mode walk_forward`) |

---

## 10. Plan post-2-semanas (ronda 6)

**Solo si live trading confirma edge:**

1. **Hyperopt-light** vía Freqtrade — exportar V3 como strategy, correr 500 épocas
2. **Per-strategy + per-symbol weights** (no solo símbolo)
3. **Estrategia VWAP RANGING** — cubrir gap lateral
4. **TradingView webhook** Pine Script ($14.95 Essential)
5. **Hyperopt MIN_CONFLUENCE** + ATR mults vía grid search

**Si no confirma edge:**
- Volver a paper trading
- Auditar slippage/comisiones reales vs backtest
- Reconsiderar approach desde fundamentals

---

## 11. Rollback plan (si algo se rompe en producción)

**Cada cambio es revertible:**

```bash
# Revertir todas las iteraciones (ronda 1-5):
git revert 597fead 9d1c485 d915e5b 22d1565 f99ea27

# Revertir solo ronda 5 (sizing + telegram cleanup):
git revert 597fead

# Revertir solo Telegram cleanup (mantener tuning):
git revert <commit del cleanup>

# Volver a baseline pre-sesión:
git checkout f99ea27^  # commit anterior a kill switches
```

**Triggers para rollback:**
- PF live < 0.5 después de 10+ trades
- Telegram errors >5%/día
- Bot crashes >3 veces/semana
- Trades stuck (status=OPEN > 7d)

---

## 12. Filosofía operativa vigente

> **"No somos rentables todavía. Step by step."**

- Calidad > cantidad
- 3 strikes y muere
- PF > 1.3 = ganando (WR alone es vanity)
- In-sample backtest necesita walk-forward + live validation
- Iterar con data, no con intuición
- Documentar cada decisión

---

## Aprobación de spec

| Quién | Cuándo | Comentario |
|-------|--------|------------|
| Fernando | 2026-05-09 | Cierre sesión pre-validación 2 semanas |
| Auditor automático | 2026-05-23 09:00 Mty | Routine `trig_01QjZVU9531oqK9pvNUoWSzF` |
| Re-evaluación | 2026-05-23 | Decidir ronda 6 según data live |
