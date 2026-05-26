# Bot scalp_bot/Zenith — Capabilities + Gaps

> **Snapshot:** 2026-05-26
> **Propósito:** corpus para NotebookLM. Describe qué tiene el bot HOY para que NotebookLM identifique estrategias NUEVAS a sumar (no duplicar lo existente).

## 1. Stack actual

**Lenguaje + infra:**
- Python 3.12, Flask dashboard, SQLite (`trades.db`)
- Deploy Railway, restart automático con watchdog
- Telegram bot + webhook TradingView

**Data sources:**
- Binance (cripto OHLCV + precio live)
- yfinance (stocks NYSE/NASDAQ)
- Web fetch para FOMC PDFs, BlackRock commentary
- Reportes PTS (Daniel Marin) parseados manual a CLAUDE.md

**AI providers:**
- Gemini Flash 2.5 (default — JSON mode, function calling)
- Anthropic Claude (preparado pero SDK no instalado en prod)
- Budget tracker `ai_budget.py` máx $10/mes

## 2. Análisis técnico — qué tenemos

**Indicadores clásicos:**
- RSI(14) con buckets per-symbol
- Bollinger Bands (status: above/below/inside)
- EMA50, EMA200 (trend filter)
- ATR(14) para SL/TP dinámicos
- Pivot Points (R1, S1) diarios
- Elliott Wave (manual tag en alerts)

**Multi-timeframe (limitado):**
- Filtro `MTF_RSI_4H_MAX = 50` para V3 LONG (bloquea reversal si 4H sobrecomprado)
- No hay cascada completa W → 1D → 4H → 1H

**Patrones:**
- MACRO PHY (Head & Shoulders) — referenciado en CLAUDE.md, NO detectado automáticamente
- BitLobo zonas verdes/rojas — análisis visual via Gemini Vision (imagen Telegram)
- ZR (Zona de Resistencia) — niveles manuales del corpus PTS

**Sesión:**
- Filtro horario (HourFilter) por win rate histórico
- NYSE gate: stocks solo Mon-Fri 09:30-16:00 ET
- VIX dormant gate: <22 + SP500>7000 = barridas son oportunidad

## 3. AI agents — Cuadrilla Zenith

4 voces en cada análisis:
- 🎩 **Genesis** — capital institucional / acumulación
- ⚡ **Exodo** — narrativa / tecnología
- 🌊 **Salmos** — confluencia técnica (RSI/EMA/BB)
- 💀 **Apocalipsis** — riesgo macro / geopolítico

**Modos:**
- Sentinel Compact (JSON 6 líneas, default)
- Sentinel Verbose (texto largo, solo si /verbose on)
- Panorama (sentinel cross-asset cada 2h)
- Multi-symbol event detector

**Especiales:**
- Neural Memory — lecciones aprendidas persistentes
- BitLobo agent — Gemini Vision para gráficas
- Social Analyzer — sentiment X/Reddit (limitado)
- ZEC compact sentinel (mayor confianza ZEC tras backtest 4H)

## 4. Estrategias activas

| Strategy | Versión | Status | Símbolos | Notas |
|----------|---------|--------|----------|-------|
| V1-TECH (LONG) | v1 | **DISABLED** | - | 15.4% WR en backtest 365d |
| V1-SHORT | v1 | **DISABLED** | - | 0% WR en 16 trades |
| V2-AI Swing | v2 | ACTIVE | BTC/ETH/SOL/HBAR/TON/DOGE | Bias semanal AI + confluence |
| V3-REVERSAL | v3 | ACTIVE | BTC/ETH/ZEC (block TAO/ZEC swing) | RSI extreme + MTF filter |
| V4 | v4 | ACTIVE (blocklist ETH/ZEC) | TAO blocked | Overfit walk-forward |
| V5 | v5 | **DISABLED** | - | 0 trades en backtest (bug) |
| SWING | swing | ACTIVE (blocklist TAO/ZEC) | BTC/ETH/SOL | Ichimoku + AI bias |
| COMMODITY | commodity | ACTIVE | GOLD/OIL/NG/SLV | NG/SLV backtested 53-61% |
| NINJA | sentinel | ACTIVE | ZEC | Quiet mode (Spec 002) |
| SCALPER_SHORTS | scalper | ACTIVE | DOGE/FIL/TAO | Status menu only |
| MANUAL | manual | ACTIVE | Cualquier | Webhook TradingView |

**Macro gate dinámico (Spec 003+004):**
- VERDE_BULL (SP500 > 7000): no suprimir longs, barridas = oportunidad
- AMARILLA_INDECISA (6800-7000): reducir tamaño 50%
- NARANJA_BEAR (<6800): activar SHORT SPY/TSLA, filtrar longs débiles

## 5. Risk management

**Stop Loss + Targets:**
- ATR-based: `SL = entry ± (ATR × 2.0)`
- TP1 = 2:1, TP2 = 3.5:1, TP3 = 7:1
- ATR min: 1.2% del precio (evita SL muy ajustados)
- BE automático al alcanzar primer TP

**Tamaño de posición:**
- 1 unidad / $1000 normal
- 0.5 unidad / $1000 si VIX>18 (RAPIDA mode)
- Máximo 1 contrato en options de baja convicción

**Cluster correlation (Spec 004):**
- MAX_PER_CLUSTER_BY_CLUSTER dict (nuclear=2, quantum=0, etc.)
- PRIORITY_BOOST_CLUSTER esta semana ai_infra=3

**Kill switches:**
- TAO_TRADING_ENABLED=False (3.1% WR)
- SHORT_BLOCKED_IN_VERDE_BULL=True (8.3% WR shorts)
- ENABLE_TELEGRAM_BUTTONS=False (UX cleanup)
- ANALYSIS_MODE_QUIET=True (silencia status alerts)

## 6. Tracking + telemetría

**DB tables:**
- `trades` (91 rows, Mar-Apr 2026): entry/SL/TP, status, conf_score, macro_bias, ai_analysis
- `signal_episodes` (39 rows): outcome (WIN/LOSS/None), source (STOCK/CRYPTO/BITLOBO)
- `ai_calls`: tracker presupuesto IA por persona/símbolo
- `backtest_sessions`: histórico backtests

**Métricas calculadas:**
- WR global, por símbolo, por estrategia, por conf_score
- Distribution por RSI bucket / direction / macro_bias
- Huérfanas detector (Spec 002 yfinance fallback)

**Reportes:**
- Daily report 13:00 UTC (resumen del día)
- Sentinel ZEC compact cada N min
- Panorama BTC+TAO cross-asset cada 2h
- Stock watchlist scan cada 15 min (NYSE open)

## 7. Lo que NO tenemos (gaps conocidos)

**Datos:**
- ❌ Orderbook depth / liquidity heatmaps
- ❌ Funding rates de perps (Bybit/dYdX)
- ❌ On-chain: whale alerts, exchange in/outflows, MVRV, NUPL
- ❌ Options flow (unusual activity, dark pool, IV rank)
- ❌ Volume profile / VWAP por sesión
- ❌ CVD (Cumulative Volume Delta) / footprint charts
- ❌ News NLP sentiment automático (web scrape + GPT)
- ❌ Social sentiment quant (X engagement, Reddit r/wsb)
- ❌ Insider trading data (Form 4 SEC)
- ❌ Earnings calendar full (solo lista hardcoded en config)

**Análisis técnico:**
- ❌ Smart Money Concepts (BOS, CHoCH, order blocks, FVG)
- ❌ Wyckoff phases (accumulation/distribution detector)
- ❌ Patterns automáticos (H&S, triangles, flags) — solo manual
- ❌ Volume profile (POC, VAH, VAL)
- ❌ Market profile (TPO, value area)
- ❌ Cointegration / pairs trading
- ❌ Statistical arbitrage cripto-stock (COIN vs BTC, IBIT vs BTC)
- ❌ Mean reversion vs momentum regime classifier
- ❌ Seasonality (day of week, hour, monthly)

**Ejecución:**
- ❌ Auto-execute Binance (configurado pero modo MANUAL)
- ❌ DCA splits inteligentes (entry en varios precios)
- ❌ Trailing stop dinámico ATR-based
- ❌ Partial close inteligente (FOMO check + tomar 50% en TP1)

**Backtesting:**
- ❌ Walk-forward optimization automática
- ❌ Monte Carlo simulation
- ❌ Stress test contra crashes históricos (LUNA, FTX, COVID)
- ❌ Backtest framework live (parámetros cambian con régimen)

**Aprendizaje:**
- ❌ Reinforcement learning agent
- ❌ Ensemble voting multi-estrategia
- ❌ Auto-tuning de thresholds vía RL
- ❌ Detección de drift de régimen automática
- ❌ Replay de trades pasados para fine-tune

**Otros:**
- ❌ Multi-exchange (solo Binance)
- ❌ Cross-asset correlation (cripto-stocks-bonds-oil)
- ❌ Macro nowcasting (FOMC nowcaster, NFP whisper)
- ❌ Whale tracker (top wallets BTC/ETH on-chain)
- ❌ Tax-loss harvesting / FIFO accounting

## 8. Constraints reales

**Costo:**
- API IA: $10/mes budget (Gemini Flash es barato; Claude más caro)
- yfinance: gratis pero rate-limited
- Binance API: gratis lectura, paid heavy use
- On-chain: gratis (Glassnode community) o $30+/mes premium

**Operación:**
- Fernando = 1 persona. Tiempo limitado para reaccionar a cada alert.
- TDAH → necesita alerts CONCISAS + accionables, no walls of text.
- Prefiere automatización vs manual cuando sea reversible.

**Capital:**
- Cuenta pequeña real + cuentas demo
- Posiciones max 1-2 simultáneas por seguridad

**Riesgo:**
- No usar leverage agresivo
- No SHORT en mercado bull (regla validada empíricamente)
- Respetar feriados (Memorial Day, FOMC suppress 24h, earnings 24h)

## 9. Triggers de mejora a investigar

Preguntas que NotebookLM debe responder cruzando este corpus con investigación externa:

1. ¿Qué señales DE MERCADO (no técnicas tradicionales) deberíamos sumar?
2. ¿Qué estrategia probada en cripto + stocks tiene WR consistente >50%?
3. ¿Qué se puede hacer con Gemini Flash que NO estamos haciendo?
4. ¿Cómo aprovechar la Cuadrilla Zenith mejor (los 4 agentes)?
5. ¿Vale la pena pasarse a Claude Sonnet para análisis críticos?
6. ¿Qué papers académicos validan el approach actual o sugieren cambios?
7. ¿Cuáles bots open-source de cripto tienen ideas reutilizables?
8. ¿Cómo medir si una nueva estrategia FUNCIONA antes de poner capital?
