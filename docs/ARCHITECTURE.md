# Zenith Trading Suite — Arquitectura del Sistema

> Generado 2026-04-07. Refleja el estado actual del código en producción.

---

## Flujo Completo

```
FUENTES DE DATOS (TTL variable)
────────────────────────────────────────────────────────────
Binance          CoinGecko      Yahoo Finance   CryptoPanic     Alternative.me
(primario, 20s)  (fallback, 20s) (SPY/VIX/DXY,  (noticias,      (Fear & Greed,
BTC ETH ZEC TAO               15min)          30min)          10min)
SOL GOLD HBAR
DOGE
        │
        ▼
get_prices() → GLOBAL_CACHE
────────────────────────────────────────────────────────────
Precios · RSI · BB(U/L) · EMA200 · ATR · VOL_SMA
USDT.D · BTC.D · Fear&Greed · VIX · DXY · SPY · MACRO_TREND
Social Score (-1.0→+1.0) · PHY Bias · Funding Rates
Elliott Wave label · POC (Point of Control)
        │
        │ cada 35s (CHECK_INTERVAL)
        ├──────────────────────────────────────────┐
        │                                          │
        ▼                                          ▼
check_strategies()                    monitor_open_trades()
strategies.py                         trade_monitor.py
────────────────                      ─────────────────────
Símbolos: ZEC TAO ETH HBAR DOGE       Por cada trade abierto:
                                        • PnL flotante
4 estrategias en paralelo:              • Evalúa TP1 / TP2 / SL
  V1-TECH  → RSI + BB + EMA200          • Trailing Stop ATR
  V2-AI    → Gemini analiza             • Neural Learning al perder
  V4-EMA   → Mean Reversion bounce       (trigger_shadow_post_mortem)
  V5-MNTM  → RSI midline cross

Filtros de entrada (todos deben pasar):
  ✓ Circuit Breaker (max DD diario)
  ✓ RSI threshold (45 std / 30 extreme)
  ✓ Confluence Score ≥ 4
  ✓ Market Regime (ADX, no CHOPPY)
  ✓ PHY Bias (Head & Shoulders macro)
  ✓ Social Score (sentimiento)
  ✓ RVOL ≥ 1.0 (volumen relativo)
  ✓ Funding Rate (no longs/shorts crowded)
        │
        ▼
open_position() → tracker.py (SQLite)
Entry · SL (ATR×2) · TP1 (2:1) · TP2 (3.5:1) · TP3 (7:1)
Clasificación: RAPIDA o SWING
        │
        ▼
alert() — alert_manager.py
  key + cooldown → fired{} → evita duplicados cross-cycle
  send_telegram() → límite 4096 chars
  send_telegram_long() → chunking para reportes largos

EVENTOS PROGRAMADOS
────────────────────────────────────────────────────────────
Cada 30min (07-01h):  Salmos Prophecy → VEREDICTO: LONG/SHORT/ESPERAR
                      con ENTRY · SL (1.5×ATR) · TP1 (1:1.5R) · TP2 (1:2.5R)
Cada 1h:              Panorama horario (Salmos + Scalper)
                      Sentinel ZEC/TAO (skip si posición abierta)
Cada 4h:              Altcoin Sentinel (BTC/ETH narrativa, solo si 🚨)
En apertura/cierre NYSE: Market Pulse análisis

HILOS EN PARALELO (main.py)
────────────────────────────────────────────────────────────
bot_thread      → scalp loop, 35s interval
swing_thread    → 4H timeframe, ZEC TAO ETH
telegram_worker → comandos Telegram, 5s interval
stock_thread    → watchdog acciones US
Flask           → dashboard web :8080 (hilo principal)

GEMINI AI — PERSONAS Y FRECUENCIA
────────────────────────────────────────────────────────────
SCALPER              → Salmos Prophecy cada 30min
CONSERVADOR/SALMOS   → Panorama horario
4 agentes (Sentinel) → ZEC/TAO cada 1h (skip con posición)
SOCIAL_SENTINEL      → Social Intel cada 30min por símbolo
SHADOW               → Post-mortem en cada pérdida
QA libre             → Preguntas Telegram bajo demanda
```

---

## Archivos Clave

| Archivo | Responsabilidad | Líneas aprox |
|---------|----------------|--------------|
| `scalp_alert_bot.py` | Loop principal, precios, scheduled events | ~750 |
| `strategies.py` | V1-V5, confluence score, filtros | ~500 |
| `trade_monitor.py` | TP/SL tracking, trailing stop | ~130 |
| `gemini_analyzer.py` | Todas las llamadas a Gemini AI | ~1050 |
| `alert_manager.py` | Cooldown, send_telegram, chunking | ~200 |
| `indicators.py` | RSI, BB, EMA200, ATR, RVOL, PHY | ~400 |
| `social_analyzer.py` | Social intel, CryptoPanic, sentimiento | ~200 |
| `risk_manager.py` | Circuit breaker, trailing stop manager | ~600 |
| `tracker.py` | SQLite CRUD de trades | ~200 |
| `telegram_commands.py` | Dispatcher de comandos Telegram | ~300 |
| `config.py` | Todos los thresholds centralizados | ~110 |
| `main.py` | Lanzador de hilos + Flask | ~70 |

---

## Comparación vs Sistemas Reales de Agentes

### Lo que tenemos vs lo que tienen sistemas como AutoGPT, CrewAI, LangGraph, o sistemas de trading profesional (Hummingbot, Jesse, QuantConnect)

---

### ✅ Lo que SÍ tenemos bien implementado

| Capacidad | Implementación actual |
|-----------|----------------------|
| Multi-estrategia | V1 (técnico) + V2 (AI) + V4 (EMA) + V5 (momentum) en paralelo |
| Memoria de sesión | `GLOBAL_CACHE` persiste entre ciclos, `fired{}` evita spam |
| Memoria persistente | `neural_memory` — lecciones de trades perdidos en disco |
| Múltiples fuentes | Binance → CoinGecko → caché (3 niveles de fallback) |
| Circuit breaker | Detiene trading si DD diario supera threshold |
| Trailing stop | `TrailingStopManager` con ATR, persiste entre ciclos |
| Post-mortem automático | `trigger_shadow_post_mortem` en cada pérdida |
| Clasificación de trades | RAPIDA vs SWING según contexto macro |
| Control de presupuesto AI | `ai_budget.py` cap $10/mes |
| Multi-hilo | 5 hilos independientes sin bloqueos críticos |
| Cooldown de alertas | Key único por trade/evento, evita duplicados |

---

### ❌ Lo que nos falta vs sistemas de agentes reales

#### 1. **Memoria Episódica Estructurada**
**Qué tienen:** LangGraph, MemGPT — almacenan cada decisión con contexto completo, recuperables semánticamente.
**Qué tenemos:** `neural_memory` es una lista plana de strings. No hay búsqueda semántica ni recuperación por contexto.
**Impacto:** El bot no puede responder "¿en qué condiciones ZEC falló antes?" con precisión.
**Fix sugerido:** SQLite con embeddings o JSON estructurado: `{symbol, setup, outcome, conditions, timestamp}`.

#### 2. **Razonamiento en Cadena (Chain-of-Thought persistente)**
**Qué tienen:** CrewAI, LangGraph — cada agente documenta su razonamiento paso a paso. El siguiente agente lo lee antes de actuar.
**Qué tenemos:** Cada llamada a Gemini es stateless. Salmos no sabe qué dijo el Sentinel hace 1 hora.
**Impacto:** Los 4 agentes del Sentinel no se coordinan realmente — cada uno responde desde cero.
**Fix sugerido:** Pasar el último reporte del Sentinel como contexto al siguiente. `last_sentinel_context[sym]` en caché.

#### 3. **Bucle de Evaluación / Self-Critique**
**Qué tienen:** AutoGPT, sistemas de trading profesional — después de cada señal, un agente evalúa si la señal anterior fue correcta y ajusta parámetros.
**Qué tenemos:** Post-mortem existe pero solo en pérdidas. No hay evaluación de señales ignoradas que habrían ganado.
**Impacto:** El sistema no aprende de oportunidades perdidas, solo de errores.
**Fix sugerido:** Loggear todas las señales (disparadas o filtradas) con precio de entrada hipotético, evaluar resultado 4h después.

#### 4. **Orquestador Explícito**
**Qué tienen:** CrewAI, LangGraph — un agente "manager" coordina qué agente actúa, en qué orden, y con qué contexto.
**Qué tenemos:** Hilos independientes sin coordinación explícita. La Profecía de Salmos puede dispararse mientras el Sentinel acaba de decir "ESPERAR".
**Impacto:** Señales contradictorias en el mismo minuto sin resolución.
**Fix sugerido:** Un `SignalCoordinator` que consolide outputs de todos los agentes antes de enviar a Telegram.

#### 5. **Herramientas Externas (Tool Use real)**
**Qué tienen:** GPT-4 function calling, Claude tool_use — el modelo decide cuándo llamar a qué herramienta.
**Qué tenemos:** El prompt le dice al modelo qué datos tiene. El modelo no puede pedir más datos dinámicamente.
**Impacto:** Si Gemini necesita el orderbook para validar una señal, no puede pedirlo.
**Fix sugerido:** Migrar las llamadas críticas a Claude con tool_use. El modelo pide `get_orderbook(ZEC)` si lo necesita.

#### 6. **Gestión de Riesgo de Portafolio Real**
**Qué tienen:** Jesse, QuantConnect — position sizing dinámico basado en correlaciones entre activos, Kelly Criterion, VaR.
**Qué tenemos:** `RISK_PER_TRADE_PCT = 0.01` fijo. No hay correlación entre ZEC y TAO al dimensionar.
**Impacto:** Si ZEC y TAO están altamente correlacionados, dos posiciones simultáneas duplican el riesgo real.
**Fix sugerido:** Matriz de correlación simple (30 días) antes de abrir segunda posición.

#### 7. **Backtesting en Vivo (Paper Trading Loop)**
**Qué tienen:** Hummingbot, QuantConnect — modo paper trading que valida estrategias con datos reales sin capital.
**Qué tenemos:** `docs/SIMULATION_GUIDE.md` existe pero no hay loop automático de validación continua.
**Impacto:** Cambios en thresholds (como RSI 45→48) se van directo a producción sin validación.
**Fix sugerido:** Shadow mode: cada señal real se duplica en un tracker paralelo "paper" y se evalúa automáticamente.

#### 8. **Webhooks TradingView como Trigger**
**Qué tienen:** Sistemas profesionales — TradingView envía webhook al bot cuando se cumple condición en chart.
**Qué tenemos:** El Pine Script de Zenith Suite V17 existe pero no está conectado al bot Python.
**Impacto:** El análisis visual de TradingView y el bot Python son islas separadas.
**Fix sugerido:** Endpoint Flask `/webhook/tradingview` que recibe alertas del Pine Script y las procesa como señal adicional.

#### 9. **Explicabilidad de Señales**
**Qué tienen:** Sistemas institucionales — cada señal incluye qué filtro fue decisivo, cuáles fallaron por poco.
**Qué tenemos:** La alerta dice el score final pero no "el RSI casi no pasó (46.2 vs umbral 45)".
**Impacto:** No puedes ajustar thresholds con datos — no sabes qué tan cerca estuvieron las señales filtradas.
**Fix sugerido:** Loggear `near_miss` cuando confluence = 3 (un filtro debajo del mínimo).

---

### Priorización sugerida (impacto / esfuerzo)

| Prioridad | Item | Esfuerzo | Impacto |
|-----------|------|----------|---------|
| 🔴 Alta | Webhook TradingView | Bajo (1 endpoint Flask) | Alto — cierra el loop visual/algorítmico |
| 🔴 Alta | Memoria episódica estructurada | Medio | Alto — el bot aprende de verdad |
| 🟡 Media | Shadow mode / paper trading | Medio | Alto — validación sin riesgo |
| 🟡 Media | SignalCoordinator | Medio | Medio — elimina contradicciones |
| 🟡 Media | Near-miss logging | Bajo | Medio — datos para tuning |
| 🟢 Baja | Chain-of-thought entre agentes | Alto | Medio — mejora coherencia |
| 🟢 Baja | Correlación de portafolio | Alto | Medio — solo si tienes 3+ posiciones |
| 🟢 Baja | Tool use con Claude | Alto | Bajo en corto plazo |
