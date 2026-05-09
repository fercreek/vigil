# Zenith Trading Suite — Arquitectura Completa

> Actualizado 2026-05-08. Estado real del código en producción (`main` branch).

---

## 1. Vista General

```
┌─────────────────────────────────────────────────────────────────────┐
│                        main.py (entry point)                        │
│   Flask :8080  +  7 threads daemon con auto-restart + watchdog      │
└────────────┬────────────────────────────────────────────────────────┘
             │
    ┌────────┴──────────┐
    │  thread_health.py │  heartbeat watchdog, MAX_RESTARTS=5, backoff 5-30s
    └────────┬──────────┘
             │
  ┌──────────┴──────────────────────────────────────────────────────────┐
  │  HILOS ACTIVOS (7)                                                  │
  ├─────────────────┬──────────────┬──────────────┬─────────────────── ┤
  │  scalp_bot 35s  │  swing 4H    │  telegram 5s │  stock 5min        │
  │  commodities 15m│  manual 30m  │  scalper_     │                    │
  │                 │              │  shorts 15m   │                    │
  └─────────────────┴──────────────┴──────────────┴────────────────────┘
```

---

## 2. Threads Activos

| Nombre | Archivo | Función | Intervalo |
|--------|---------|---------|-----------|
| `scalp_bot` | `scalp_alert_bot.py` | Loop principal crypto: V1/V2/V4/V5 strategies | 35s |
| `swing` | `swing_bot.py` | Ichimoku Kumo 4H: ZEC, TAO, BTC, ETH, SOL | 4H |
| `telegram` | `scalp_alert_bot.py` | Poll Telegram commands + inline callbacks | 5s |
| `stock` | `stock_analyzer.py` | STOCK_WATCHLIST: nivel alerts, yfinance | 5min |
| `commodities` | `commodities_bot.py` | GOLD, OIL, NG, SLV, HG — EMA/RSI/DXY 1H | 15min |
| `manual_monitor` | `manual_positions_monitor.py` | P&L + SL/TP alerts en posiciones manuales | 30min |
| `scalper_shorts` | `scalper_shorts_bot.py` | SHORT scalper: DOGE, FIL, TAO — RSI/BB/EMA/funding | 15min |
| Flask | `app.py` | Dashboard web `/api/stats`, `/api/trades` | keep-alive |

---

## 3. Estrategias de Trading

### 3a. Crypto Scalp (scalp_alert_bot.py + strategies.py)

**Símbolos:** ZEC, TAO, BTC, ETH, SOL, HBAR, DOGE, TON  
**Exchange:** Binance Futures (ccxt)  
**Timeframe:** 15m señal + 1H confirmación  

| Estrategia | Lado | Condiciones clave | Confluencia mín | Estado |
|-----------|------|------------------|-----------------|--------|
| **V1-TECH** | LONG | RSI≤45, price>EMA200, BB touch, regime≠RANGING | 4/7 | ✅ activa |
| **V1-SHORT** | SHORT | RSI≥55, price<EMA200, EMA declining | 3/7 | ❌ disabled (0% WR, 16 trades) |
| **V3-REVERSAL** | LONG | RSI≤28 (TAO), price<EMA200, extreme oversold | 4/7 | ✅ activa |
| **V4-EMA** | LONG | Price dentro 2% de EMA200, RSI 35-50 | 3/7 | ✅ activa |
| **V5-MOMENTUM** | LONG | RSI cruza 50 desde abajo | 3/5 | ✅ activa |
| **V2-AI** | LONG/SHORT | Gemini consensus: CONSERVADOR + SCALPER votan | 4-5 | ✅ activa |

**Filtros globales aplicados a todas:**
- Circuit breaker: 3+ pérdidas consecutivas → 4H cooldown (DB-persisted)
- FOMC proximity: -24h antes de reunión → confluencia mínima +1
- 1D EMA200 bias: bloquea LONGs si tendencia diaria es BEAR (TAO, configurable)
- Hour blacklist: horas con 0% WR histórico bloqueadas
- Funding rate contrarian: ±1 a confluencia según crowding

### 3b. Swing (swing_bot.py)

**Símbolos:** ZEC, TAO, BTC, ETH, SOL  
**Timeframe:** 4H  
**Método:** Ichimoku Kumo breakout + ATR targets  
**SL:** 2.0×ATR | TP1: 2.5×ATR (50%) | TP2: 5.0×ATR | TP3: 8.0×ATR  
**Cooldown:** 4H entre alertas | 24H para flipear dirección  

### 3c. Commodities (commodities_bot.py)

**Instrumentos:** GOLD (GC=F), OIL (CLM26.NYM), NG (NG=F), SLV, HG (HG=F)  
**Exchange:** Yahoo Finance (yfinance)  
**Timeframe:** 1H  
**Método:** EMA9/21 cross + RSI + DXY filter + ATR confirmation  
**Confluencia mín:** 4/5  
**DB version tag:** `"COMMODITY"`  
**Market hours guard:** CME Globex (cerrado Vie 17h–Dom 18h ET) + NYSE para SLV  

Protecciones especiales:
- OPEC suppression: suprime señales OIL ±24h de reuniones OPEC+
- Post-rally filter OIL: si +15% en 10d → RSI max 45 para LONG
- Gold bull lock: si GOLD > $2,500 → no SHORT (correlación DXY rota en 2026)
- SP500 verde guard: si SP500 > 7,000 → no SHORT en OIL

### 3d. Scalper Shorts (scalper_shorts_bot.py) — NUEVO May-2026

**Instrumentos:** DOGE, FIL, TAO  
**Exchange:** Binance Futures (ccxt perpetuos)  
**Timeframe:** 1H  
**Método:** RSI overbought + BB upper + EMA cross + funding contrarian  
**Confluencia mín:** 4/5  
**DB version tag:** `"SCALPER_SHORTS"`  

| # | Condición | Threshold |
|---|-----------|-----------|
| 1 | RSI sobrecomprado | ≥ 65 |
| 2 | Precio toca BB superior | ≥ 99% BB_upper |
| 3 | Precio sobre EMA200 | price > EMA200 (distribución desde arriba) |
| 4 | Cruce EMA bajista | EMA9 < EMA21 |
| 5 | Funding longs crowded | rate > 0.03% |

**Macro guard:** Si `price_1D < EMA200_1D` → bloquea (ya bajando, no scalp)  
**ATR targets SHORT:** SL +2.0x | TP1 -1.5x | TP2 -3.0x | TP3 -5.0x  
**Comando Telegram:** `/scalper_shorts`

### 3e. Stock Watchlist (stock_analyzer.py + stock_watchlist.py)

**Watchlist:** TSLA, NVDA, PLTR, SIL, GCM6, RKLB, XBI, HOOD, COIN, MP, SOFI, IREN, UUUU, IONQ, MSFT, XOM, MOO, CRCL, NKE, WEN, GDX, MSTR, UVXY  
**Exchange:** Yahoo Finance (yfinance)  
**Alertas:** Nivel reach alerts (precio cruza entry/SL/TP) — no entry autónoma  
**Comando Telegram:** `/stocks`

---

## 4. Agentes IA

### Cuadrilla Zenith (gemini_analyzer.py)

4 personajes con perspectivas distintas — votan en consenso por cada señal:

| Agente | Libro bíblico | Sesgo | Rol |
|--------|--------------|-------|-----|
| **Genesis** | Génesis | Fundacional | Contexto macro histórico |
| **Exodo** | Éxodo | Técnico | Análisis de indicadores |
| **Salmos** | Salmos | Espiritual/emocional | Psicología de mercado |
| **Apocalipsis** | Apocalipsis | Pesimista | Devil's advocate, riesgos |

**Output:** Veredicto unificado → LONG / SHORT / ESPERAR  
**Función:** `get_ai_consensus()` en `gemini_analyzer.py`

### BitLobo Agent (bitlobo_agent.py)

Análisis técnico por zonas de color (verde=soporte, rojo=resistencia).  
- Input: imagen de chart vía Gemini Vision o datos de precio  
- Output: opinión independiente que aparece como línea 🐺 en debates Zenith  
- Memoria: JSON diario por persona (`memory/bitlobo_YYYY-MM-DD.json`)

### Personas Gemini (gemini_analyzer.py)

| Persona | Sesgo | Uso |
|---------|-------|-----|
| CONSERVADOR | Defensivo, largo plazo | Panorama horario |
| SCALPER | Agresivo, intradía | Análisis de señales rápidas |

Ambas votan en cada señal V2-AI. Daily memory JSON persiste entre reinicios.

### Signal Coordinator (signal_coordinator.py)

Deconflicta señales de múltiples fuentes (V1, V2, Salmos, TradingView):
- Ventana 120s para detectar conflictos
- Si hay acuerdo → envía inmediato
- Si hay conflicto → favorece mayor confianza (≥0.8)
- Si es solo una fuente → espera 120s, luego envía

---

## 5. Flujo Señal → DB

```
1. strategies.py detecta condiciones
        ↓
2. _store_pending(sym, side, price, tp1, tp2, sl, ...)
   → _PENDING_SIGNALS[sid] (TTL 4h)
        ↓
3. Telegram alert con inline keyboard [✅ Activar] [⏭️ Skip]
        ↓
4a. ACTIVAR → tracker.log_trade(..., is_sim=0)
    → trades.db: status=OPEN, version=V1-TECH|SCALPER_SHORTS|COMMODITY|...
    → append_event(tid, "ACTIVATED via Telegram @ $price")
        ↓
4b. SKIP → tracker.log_simulated(..., is_sim=1)
    → Para comparación Real vs SIM en /winrate
        ↓
5. monitor_open_trades() detecta TP/SL hits → update_trade_status()
   → append_event("TP1 HIT @ $price")
```

---

## 6. Win Rate Tracking por Agente

Todos los trades van a `trades.db` tabla `trades`. Separación por `strategy_version`:

| Agente | strategy_version | Consulta |
|--------|-----------------|---------|
| Crypto scalp V1 | `V1-TECH` | `tracker.get_win_rate("V1-TECH")` |
| Commodities | `COMMODITY` | `tracker.get_win_rate("COMMODITY")` |
| Scalper Shorts | `SCALPER_SHORTS` | `tracker.get_win_rate("SCALPER_SHORTS")` |
| Swing | `SWING` | `tracker.get_win_rate("SWING")` |
| Global | — | `tracker.get_win_rate()` (sin filtro) |

**Funciones clave en tracker.py:**
- `get_win_rate(version=None)` → wins, losses, total, wr%
- `get_winrate_comparison()` → Real vs SIM (Activate vs Skip)
- `get_win_rate_by_alert_type()` → breakdown por alert_type + symbol
- `get_audit_metrics()` → Profit Factor, SQN, Sortino

**Comando Telegram:** `/winrate`

---

## 7. Módulos por Categoría

### Core loop
- `scalp_alert_bot.py` — loop principal, get_prices(), GLOBAL_CACHE, scheduled events
- `main.py` — lanzador de threads + Flask

### Estrategias
- `strategies.py` — V1-V5 logic, confluence score, regime guards, cooldowns
- `swing_bot.py` — Ichimoku 4H para ZEC/TAO/BTC/ETH/SOL
- `commodities_bot.py` — GOLD/OIL/NG/SLV/HG via yfinance
- `scalper_shorts_bot.py` — SHORT scalper DOGE/FIL/TAO via ccxt
- `stock_analyzer.py` + `stock_watchlist.py` — STOCK_WATCHLIST alerts

### IA
- `gemini_analyzer.py` — Cuadrilla Zenith, Gemini API, panorama horario, V2-AI
- `bitlobo_agent.py` — BitLobo zone analysis + Gemini Vision
- `analysis_science.py` — backtesting científico frame-by-frame
- `backtester.py` — replay histórico, comisiones, métricas

### Señales
- `signal_coordinator.py` — deconflicto multi-fuente, ventana 120s
- `episode_memory.py` — memoria episódica AI + auto-fill de outcomes

### Telegram
- `telegram_commands.py` — dispatcher de comandos, 40+ handlers
- `alert_manager.py` — send_telegram, set_bot_commands, main menu

### Datos
- `tracker.py` — SQLite CRUD: trades, backtest_sessions, append_event
- `indicators.py` — RSI, BB, EMA, ATR, ADX, RVOL, Elliott, Fibonacci, Ichimoku, POC
- `indicators_swing.py` — indicadores extendidos para swing
- `market_intel.py` — funding rates, liquidation levels, regime detection
- `social_analyzer.py` — social sentiment, Reddit, LunarCrush

### Riesgo
- `risk_manager.py` — circuit breaker, position sizing, loss streak cooldown
- `manual_positions_monitor.py` — P&L + recs para posiciones manuales (/check)
- `trade_monitor.py` — TP/SL auto-detection por precio

### Monitoreo
- `thread_health.py` — heartbeat watchdog, auto-restart, MAX_RESTARTS=5
- `metrics.py` — Sharpe, Sortino, MaxDD, SQN, Profit Factor
- `ai_budget.py` — Gemini/Claude spend tracking, cap $10/mes
- `voice_compactor.py` — compactar reportes Sentinel, deduplication
- `scan_status.py` — historial de /scan requests

### Config / Seguridad
- `config.py` — todos los thresholds: RSI, EMA, BB, FOMC, SYMBOLS, STOCK_WATCHLIST
- `runtime_state.py` — persist paused state entre reinicios
- `webhook_security.py` — HMAC-SHA256 auth para TradingView webhooks
- `logger_core.py` — centralized logging

### Dashboard
- `app.py` — Flask: `/api/stats`, `/api/trades`, `/api/metrics`, `/api/backtest`, `/api/winrate`

---

## 8. Config: Parámetros Clave

```python
# config.py — valores actuales en producción (May-2026)

SYMBOLS = ["ZEC", "TAO", "BTC", "ETH", "SOL", "HBAR", "DOGE", "TON"]

# RSI thresholds
RSI_LONG_ENTRY    = 45.0
RSI_SHORT_ENTRY   = 55.0  # V1-SHORT (disabled)
RSI_LONG_EXTREME  = 30.0  # V3 reversal
RSI_LONG_TAO_EXTREME = 28.0

# Estrategia flags
V1_SHORT_ENABLED  = False   # 0% WR en 16 trades — disabled Apr-2026
TAO_TRADING_ENABLED = True  # Re-enabled May-2026 con cooldown 4H + 1D EMA200

# FOMC suppression
FOMC_NEXT_MEETING = "2026-06-17"

# Circuit breaker
TAO_LOSS_STREAK_COOLDOWN = True  # 3 lost → 4H pause (DB-persisted)

# Macro context (hawkish hold)
RATE_BIAS = "HAWKISH_HOLD"
OIL_INFLATION_THRESHOLD = 85.0

# AI budget
AI_BUDGET_MAX_MONTHLY = 10.0  # USD

# Commodities
OPEC_MEETING_DATES = ["2026-05-05", "2026-06-01", "2026-09-01"]
GOLD_BULL_THRESHOLD = 2500.0
SP500_VERDE_MIN = 7000

# Scalper Shorts (scalper_shorts_bot.py)
# RSI_SHORT_ENTRY = 65.0 (más estricto que V1-SHORT)
# MIN_CONFLUENCE  = 4/5
# FUNDING_THRESHOLD = 0.0003
```

---

## 9. Comparación con Sistemas de Agentes Reales

### ✅ Implementado bien

| Capacidad | Implementación |
|-----------|---------------|
| Multi-estrategia | V1/V3/V4/V5 crypto + Swing + Commodities + Scalper Shorts |
| Memoria de sesión | `GLOBAL_CACHE` persiste entre ciclos |
| Memoria persistente | Daily JSON por persona IA |
| Múltiples fuentes | Binance → CoinGecko → cache (3 niveles fallback) |
| Circuit breaker | 3+ pérdidas → 4H cooldown, DB-persisted (sobrevive restart) |
| Signal Coordinator | Deconflicto 4 fuentes en ventana 120s |
| Win rate por agente | `strategy_version` tag en trades.db |
| Real vs SIM tracking | `is_sim` flag — Activate vs Skip comparison |
| Control de presupuesto AI | `ai_budget.py` cap $10/mes |
| Market hours guards | Commodities: CME Globex + NYSE schedule |
| Backtester | `backtester.py` + `analysis_science.py` |

### ❌ Gaps vs sistemas profesionales

| Gap | Impacto | Fix sugerido |
|-----|---------|-------------|
| Memoria episódica estructurada | Bot no aprende semánticamente de setups pasados | SQLite con condiciones + outcome JSON |
| Backtesting automático continuo | Cambios de threshold van directo a prod | Shadow mode: duplicar señales en paper tracker |
| Tool use dinámico (Claude API) | Gemini no puede pedir orderbook cuando lo necesita | Migrar V2-AI a Claude con tool_use |
| Correlación de portafolio | 2 posiciones correlacionadas = riesgo doble | Matriz correlación 30d pre-entry |
| Near-miss logging | No sabes qué señales casi se dispararon | Log cuando confluence = MIN-1 |
| TradingView webhook activo | Pine Script y bot Python son islas | Endpoint `/webhook/tradingview` Flask |
