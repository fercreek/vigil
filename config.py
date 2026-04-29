"""
config.py — Configuración Central del Zenith Trading Suite

Todos los thresholds, símbolos e intervalos en un solo lugar.
Importar en cualquier módulo con: from config import RSI_LONG_ENTRY, SYMBOLS, ...
"""

# ── Símbolos operados ─────────────────────────────────────────────────────────
SYMBOLS = ["ZEC", "TAO", "BTC", "ETH", "SOL", "HBAR", "DOGE"]
MACRO_WATCH = []  # Todos los símbolos ahora son operables

# ── Watchlist estática de acciones (siempre monitoreada, independiente del reporte)
# yf_ticker: símbolo que entiende Yahoo Finance (CL=F = crude front month, GC=F = gold front month)
# Niveles marcados con ⚠️ = estimados con ATR pre-mercado (08-Apr-2026).
# Confirmar y ajustar al precio real de apertura antes de operar.
STOCK_WATCHLIST = [
    # ── Tu lista personal ─────────────────────────────────────────────────────
    {"ticker": "TSLA",  "yf_ticker": "TSLA",  "direction": "LONG",
     "entry": 400.62, "stop_loss": 367.55, "take_profit_1": 441.96, "take_profit_2": 475.03, "break_even": 421.0,
     "context": "Actualizado 17-Abr-2026. Setup SHORT Apr-13 ($335.65) invalidado — precio en $400. Nuevo monitoreo LONG ATR-based. Esperar pullback a zona 375-390 para entrar. Setup original era bajista pero recuperó fuerza."},

    {"ticker": "NVDA",  "yf_ticker": "NVDA",  "direction": "LONG",
     "entry": 201.68, "stop_loss": 193.36, "take_profit_1": 212.07, "take_profit_2": 220.39, "break_even": 207.0,
     "context": "Agregado 17-Abr-2026. NVIDIA LONG. Precio en máximo 5d ($201.70). ATR ~$4.16. R:R 1.3:1. También usado como indicador macro en scalp_bot. Esperar pullback a zona $193-196 para mejor entrada. AI infrastructure play."},

    {"ticker": "PLTR",  "yf_ticker": "PLTR",  "direction": "LONG",
     "entry": 150.07, "stop_loss": 135.79, "take_profit_1": 178.62, "break_even": 164.35,
     "context": "⚠️ Niveles pre-mercado. Sector AI/defensa. Confirmar ruptura con volumen en apertura."},

    {"ticker": "SIL",   "yf_ticker": "SIL",   "direction": "LONG",
     "entry": 92.84,  "stop_loss": 82.55,  "take_profit_1": 113.43, "break_even": 103.13,
     "context": "⚠️ Niveles pre-mercado. Silver Miners ETF. DXY débil → setup alcista mineras plata."},

    {"ticker": "GCM6",  "yf_ticker": "GC=F",  "direction": "LONG",
     "entry": 4838.80, "stop_loss": 4476.47, "take_profit_1": 5563.46, "break_even": 5201.13,
     "context": "⚠️ Niveles pre-mercado. Oro Jun-2026. PHY alcista activo. DXY débil = setup largo."},

    {"ticker": "CLK6",  "yf_ticker": "CLM26.NYM",  "direction": "SHORT",
     "entry": 95.95,  "stop_loss": 115.04, "take_profit_1": 57.78,  "break_even": 76.86,
     "context": "⚠️ Niveles pre-mercado. Crudo Jun-2026. Monitorear soporte $60 y noticias OPEP+."},

    # ── PTS Reports Apr 13-15 2026 ───────────────────────────────────────────
    {"ticker": "RKLB",  "yf_ticker": "RKLB",  "direction": "LONG",
     "entry": 74.90,  "stop_loss": 63.35,  "take_profit_1": 91.0,  "take_profit_2": 100.0, "break_even": 83.0,
     "context": "PTS 13-Abr-2026. Rocket Lab OPERACIÓN RÁPIDA. Si SP500 se mantiene arriba puede llegar rápido a targets. GR -1.1%. 1 acción/$1k."},

    {"ticker": "XBI",   "yf_ticker": "XBI",   "direction": "LONG",
     "entry": 133.0,  "stop_loss": 119.09, "take_profit_1": 150.0, "take_profit_2": 174.0, "break_even": 143.0,
     "context": "PTS 14-Abr-2026. Biotech ETF DEFENSIVA SWING. Entrada activa zona 133-136. No cayó con SP500. GR -1.4%. 1 acción/$1k."},

    {"ticker": "HOOD",  "yf_ticker": "HOOD",  "direction": "LONG",
     "entry": 70.0,   "stop_loss": 65.35,  "take_profit_1": 120.0, "take_profit_2": 134.0, "break_even": 97.84,
     "context": "PTS 29-Abr-2026. HOOD post-earnings. Entry zona 70-85 (bajada vs 85.97 original). Earnings: crypto bajo pero options +8%, stocks +46%, subs Gold +36%, nuevos depósitos +22%. Buyback $1.5B a avg $81 = soporte invisible. GR -2%. 1 acción/$1k. Options: BUY CALL 21-Ago-2026 Strike 90."},

    {"ticker": "COIN",  "yf_ticker": "COIN",  "direction": "LONG",
     "entry": 178.0,  "stop_loss": 160.32, "take_profit_1": 286.0, "take_profit_2": 328.0, "take_profit_3": 382.0, "break_even": 254.0,
     "context": "PTS 29-Abr-2026. Coinbase SWING ALCISTA. Entry zona 178-200 (bajada post-barrida). Rebotando en ZR. Mejor proxy crypto. GR -2%. 1 acción/$2k. Options: BUY CALL 18-Sep-2026 Strike 220."},

    {"ticker": "MP",    "yf_ticker": "MP",    "direction": "LONG",
     "entry": 63.28,  "stop_loss": 48.11,  "take_profit_1": 79.0,  "take_profit_2": 89.0,  "break_even": 73.0,
     "context": "PTS 15-Abr-2026. MP Materials SWING ALCISTA. Rare earth materials. Enorme rango de consolidación. GR -1.5%. 1 acción/$1k."},

    {"ticker": "SOFI",  "yf_ticker": "SOFI",  "direction": "LONG",
     "entry": 19.29,  "stop_loss": 15.60,  "take_profit_1": 25.0,  "take_profit_2": 28.0,  "break_even": 21.0,
     "context": "PTS 15-Abr-2026. SoFi Technologies SWING ALCISTA. Posible formación de suelo tras fuertes caídas. GR -1.2%. 3 acciones/$1k."},

    {"ticker": "SPY",   "yf_ticker": "SPY",   "direction": "SHORT",
     "entry": 673.0,  "stop_loss": 700.0,  "take_profit_1": 632.0, "take_profit_2": 600.0, "break_even": 659.0,
     "context": "PTS 15-Abr-2026. SP500 vigilancia bajista. Alerta si SP500 pierde 6,832 (SPY ~683) — prepararse. Entrada en SPY ~673 (SP500 6,728). Mientras no active, dejar tranquilo."},

    # ── Mencionadas en PTS — niveles pendientes ───────────────────────────────
    {"ticker": "IREN",  "yf_ticker": "IREN",  "direction": "LONG",
     "entry": 45.22,  "stop_loss": 35.78,  "take_profit_1": 67.0, "take_profit_2": 77.0, "take_profit_3": 89.0, "break_even": 59.0,
     "context": "PTS 29-Abr-2026. Iris Energy (bitcoin mining/data centers) SWING ALCISTA. Re-entry bajado de 52.38. Esperar recuperación a 45.22. GR -1%. 1 acción/$1k. Options: BUY CALL 18-Sep-2026 Strike 55."},

    {"ticker": "UUUU",  "yf_ticker": "UUUU",  "direction": "LONG",
     "entry": 21.14,  "stop_loss": 18.50,  "take_profit_1": 28.0, "take_profit_2": 31.0, "take_profit_3": 35.0, "break_even": 25.36,
     "context": "PTS 29-Abr-2026. Energy Fuels (uranium/nuclear) SWING ALCISTA. Entrar si recupera 21.14. Sector nuclear despertando. GR -1%. 3 acciones/$1k. Options: BUY CALL 16-Oct-2026 Strike 22 (riesgo ~$200, pot $400-950). Solo brokers de options (no QF)."},

    {"ticker": "IONQ",  "yf_ticker": "IONQ",  "direction": "LONG",
     "entry": 42.45,  "stop_loss": 35.44,  "take_profit_1": 62.0, "take_profit_2": 72.0, "break_even": 50.0,
     "context": "PTS 29-Abr-2026. IonQ (quantum computing) SWING ALCISTA. Entry bajado a 42.45 (era 45.30). Sector cuántico despertando. GR -2%. 2 acciones/$1k. Options: BUY CALL 16-Oct-2026 Strike 50 (riesgo ~$480, pot $1,100-1,500)."},

    {"ticker": "MSFT",  "yf_ticker": "MSFT",  "direction": "LONG",
     "entry": None, "stop_loss": None, "take_profit_1": None, "break_even": None,
     "context": "PTS 14-Abr-2026. Microsoft. Candidata a rebote rápido si SP500 continúa arriba. Niveles pendientes próximo reporte."},

    # ── PTS Report 9-Abr-2026 (Operaciones Defensivas) ───────────────────────
    {"ticker": "XOM",   "yf_ticker": "XOM",   "direction": "LONG",
     "entry": 162.49, "stop_loss": 149.60, "take_profit_1": 185.0, "take_profit_2": 205.0, "take_profit_3": 227.0, "break_even": 176.0,
     "context": "PTS 9-Abr-2026. ExxonMobil DEFENSIVA SWING. Sector energía, correlación inversa al mercado tech. GR -1%. 1 acción/$1k. Options: BUY CALL 18-Sep-2026 Strike 165."},

    {"ticker": "MOO",   "yf_ticker": "MOO",   "direction": "LONG",
     "entry": 87.64,  "stop_loss": 83.39,  "take_profit_1": 95.0,  "take_profit_2": 98.0,  "take_profit_3": 109.0, "break_even": 90.0,
     "context": "PTS 9-Abr-2026. VanEck Agribusiness ETF DEFENSIVA SWING. Sector agrícola, descorrelacionado de tech. GR -1%. 3 acciones/$1k. Options: BUY CALL 21-Ago-2026 Strike 88."},

    # ── Ideas del live BitLobo 9-Abr-2026 ────────────────────────────────────
    {"ticker": "CRCL",  "yf_ticker": "CRCL",  "direction": "LONG",
     "entry": 83.53, "stop_loss": 60.75, "take_profit_1": 145.67, "take_profit_2": 174.51, "break_even": 105.0,
     "context": "BitLobo live 9-Abr-2026. Circle Internet Group 4H. Zona verde entrada: 60.75-83.53. Zona roja targets: 145.67-174.51. Entrar en pullback a zona verde."},

    {"ticker": "NKE",   "yf_ticker": "NKE",   "direction": "LONG",
     "entry": None, "stop_loss": None, "take_profit_1": None, "break_even": None,
     "context": "BitLobo live 9-Abr-2026. Nike. TF: Semanal. PENDIENTE niveles — confirmar setup antes de entrar."},

    {"ticker": "WEN",   "yf_ticker": "WEN",   "direction": "LONG",
     "entry": 7.06,  "stop_loss": 4.30,  "take_profit_1": None, "break_even": None,
     "context": "BitLobo live 9-Abr-2026. Wendy's NASDAQ semanal. Zona acumulación: 4.30-7.06. Largo plazo. Target pendiente. Precio actual ~7.09 tocando techo de zona verde."},

    # ── Recomendaciones del bot ────────────────────────────────────────────────
    {"ticker": "GDX",   "yf_ticker": "GDX",   "direction": "LONG",
     "entry": 92.78,  "stop_loss": 96.0,  "take_profit_1": 102.0,  "break_even": 97.0,
     "context": "PTS actualizado 14-Abr-2026. GDX en ganancias ~100. Stop movido a 96 (break even zone). Gold debilitándose — hold defensivo."},

    {"ticker": "MSTR",  "yf_ticker": "MSTR",  "direction": "LONG",
     "entry": 123.72, "stop_loss": 109.22, "take_profit_1": 152.73, "break_even": 138.22,
     "context": "⚠️ Niveles pre-mercado. Proxy BTC. Alta correlación con Bitcoin."},

    {"ticker": "UVXY",  "yf_ticker": "UVXY",  "direction": "LONG",
     "entry": 51.17,  "stop_loss": 39.93,  "take_profit_1": 73.65,  "break_even": 62.41,
     "context": "⚠️ Niveles pre-mercado. VIX cobertura. SPY con MACRO PHY bajista activo."},
]

# ── Thresholds RSI ────────────────────────────────────────────────────────────
RSI_LONG_ENTRY       = 45.0   # Entrada Long estándar (was 42 — too restrictive)
RSI_LONG_ZEC_ENTRY   = 48.0   # ZEC tiene mayor volatilidad — entrada más conservadora
RSI_LONG_EXTREME     = 30.0   # Entrada Long extrema (reversal / modo rescate)
RSI_LONG_TAO_EXTREME = 28.0   # TAO modo rescate
RSI_LONG_ZEC_EXTREME = 26.0   # ZEC modo rescate agresivo
RSI_SHORT_ENTRY      = 55.0   # Entrada Short estándar (was 62 — casi nunca en downtrend)
RSI_SHORT_EXTREME    = 70.0   # Entrada Short extrema

# ── ATR Multipliers (gestión de riesgo) ───────────────────────────────────────
ATR_SL_MULT         = 2.0    # Stop Loss = entry ± (ATR * mult)
ATR_TP1_MULT        = 2.0    # TP1 = 2:1 R:R
ATR_TP2_MULT        = 3.5    # TP2 = 3.5:1 R:R
ATR_TP3_MULT        = 7.0    # TP3 = 7:1 R:R (moonshot, V2-AI)
ATR_MIN_SL_PCT      = 0.007  # SL mínimo: 0.7% del precio (evita SL muy ajustados)
ATR_MIN_SL_REVERSAL = 0.010  # SL mínimo para reversals (wider = less noise stops)

# --- STRATEGY KILL SWITCHES (basado en análisis win rate 76 trades) ---
V1_SHORT_ENABLED     = False   # 0% WR en 16 trades — disabled Apr 2026
TAO_TRADING_ENABLED  = False   # 0% WR en 28 trades — disabled Apr 2026

# ── Confluence Score ──────────────────────────────────────────────────────────
MIN_CONFLUENCE_SCORE = 4     # Score mínimo para disparar alerta
USDT_D_THRESHOLD    = 8.05   # Por encima: condición bajista para cripto

# ── Volatilidad / Riesgo ──────────────────────────────────────────────────────
ZEC_MAX_VOL_PCT     = 3.5    # % ATR/Precio máximo para ZEC (guarda anti-manipulación)
VIX_RAPIDA_THRESHOLD = 18.0  # VIX > 18 → trade RAPIDA (was 22 — VIX base post-FOMC Apr-26: ~18-20)
VIX_EXTREME_THRESHOLD = 32.0 # VIX > 32 → no operar / mínima posición (was 35)
DXY_CRIPTO_PRESSURE = 103.0  # DXY > 103 → presión bajista en cripto (was 105 — FOMC: USD safe-haven activo)
OIL_INFLATION_THRESHOLD = 85.0  # Oil > $85 = presión inflacionaria → hawkish Fed (FOMC Mar-26)

# ── FOMC Calendar ────────────────────────────────────────────────────────────
FOMC_NEXT_MEETING = "2026-06-17"   # Próxima reunión FOMC (Apr 28-29 ya pasó) — suprimir señales 24h antes
RATE_BIAS = "HAWKISH_HOLD"         # FOMC Mar-26: tasas 3.50-3.75%, 30% prob de subida, sin recortes hasta dic

# ── Cache TTL (segundos) ──────────────────────────────────────────────────────
TTL_PRICES     = 20    # Precios live
TTL_INDICATORS = 120   # RSI, BB, EMA, ATR
TTL_GLOBAL     = 600   # USDT.D, BTC.D
TTL_MACRO      = 900   # SPY, Oil, DXY, VIX

# ── Execution ────────────────────────────────────────────────────────────────
DEFAULT_LEVERAGE     = 5
POSITION_TTL_SECONDS = 3600   # 1h: posición expirada si no hay TP/SL
MIN_BALANCE_USD      = 10.0   # Balance mínimo para ejecutar orden
RISK_PER_TRADE_PCT   = 0.01   # 1% por defecto

# ── Alertas / Cooldown ────────────────────────────────────────────────────────
ALERT_COOLDOWN_SECONDS = 300  # 5 min entre alertas del mismo tipo

# ── Estrategia V4: EMA 200 Bounce (Mean Reversion) ──────────────────────────
V4_EMA_PROXIMITY_MAX = 1.02    # Precio max 2% arriba de EMA200 (BTC default)
V4_EMA_PROXIMITY_MIN = 1.001   # Precio min 0.1% arriba (confirma no quiebre)
V4_RSI_LOW           = 35.0    # RSI minimo (zona de recuperacion)
V4_RSI_HIGH          = 50.0    # RSI maximo (no sobrecomprado)
V4_RSI_HIGH_ZEC      = 55.0    # ZEC: umbral mas alto por volatilidad
V4_MIN_CONFLUENCE    = 3       # Confluencia minima (vs 4 de V1)
V4_ATR_SL_MULT       = 1.5    # SL mas ajustado: 1.5x ATR
V4_COOLDOWN          = 600     # 10 min cooldown (vs 5 min de V1)
# Per-symbol EMA proximity (altcoins need wider window due to higher ATR/price)
V4_EMA_PROX_MAP = {"BTC": 1.02, "ETH": 1.025, "TAO": 1.03, "ZEC": 1.03}

# ── V3 Reversal improvements ────────────────────────────────────────────────
V3_MIN_CONFLUENCE    = 4       # Was 3 — too many false reversals
V3_MAX_HOLDING_BARS  = 48      # Force-close stale V3 trades after 48 bars (48h)
V3_REQUIRE_DIVERGENCE = True   # RSI bullish divergence required
V3_REQUIRE_BB_SQUEEZE = True   # BB width contracting (sell-off losing steam)

# ── V1-SHORT improvements ───────────────────────────────────────────────────
SHORT_MIN_CONFLUENCE = 3       # Was 4 — hard to accumulate for shorts
SHORT_REGIMES = ("TRENDING_DOWN", "VOLATILE")  # Was only TRENDING_DOWN
SHORT_EMA_SLOPE_MIN  = -0.001  # EMA200 must be declining

# ── Regime improvements ─────────────────────────────────────────────────────
ADX_CHOPPY_THRESHOLD = 20      # ADX < 20 + BB 2-4% = CHOPPY (suppress all)
REGIME_COOLDOWN_BARS = 6       # Bars to wait after regime transition
RVOL_MIN_ENTRY       = 1.0     # Relative Volume minimum for entries
RVOL_MIN_BTC         = 0.7    # BTC has stable volume — less aggressive filter

# ── Estrategia V5: Momentum Breakout (RSI Midline Cross) ─────────────────────
V5_MOMENTUM_RSI_CROSS  = 50.0   # RSI cruza arriba de este nivel = señal de momentum
V5_MOMENTUM_MIN_CONF   = 3      # Confluencia mínima (más lenient que V1's 4)
V5_MOMENTUM_COOLDOWN   = 1200   # 20 min cooldown (evita señales repetidas en tendencia)
V5_MOMENTUM_RVOL_MIN   = 1.2    # Volume ratio mínimo para confirmar momentum

# ── Versiones de estrategia ───────────────────────────────────────────────────
VERSIONS = ["V1-TECH", "V2-AI", "V4-EMA", "V5-MOMENTUM"]

# ── Iteración del sistema (actualizar en cada mejora significativa) ───────────
# Formato: v{major}.{minor} — major sube cuando cambia la lógica core
# Minor sube cuando se ajustan parámetros o se agregan filtros
STRATEGY_ITERATION = "v4.4"  # Apr 29 2026: gold bull lock + commodities MIN_CONFLUENCE 3→4 + FOMC update

# ── Win Rate Target (matemática real, no wishful thinking) ──────────────────
# Fórmula break-even: WR_min = 1 / (1 + R:R)
#   R:R 1.2 → WR_min = 45.5%  |  R:R 1.5 → WR_min = 40.0%  |  R:R 2.0 → WR_min = 33.3%
#
# Targets por categoría (industria, swing 4H crypto):
#   Funcional:     40-50%  — rentable si R:R ≥ 1.5
#   Profesional:   55-62%  — target real sostenible para retail algo
#   Elite:         65-70%  — con tendencia fuerte + filtros avanzados
#   Overfitting:   >75%    — casi seguro curve-fitted en <200 trades
#
# Target v4.2: 60-65% WR  |  R:R objetivo: 1.5:1  |  Half-Kelly bet: ~11%
WR_TARGET_MIN   = 0.55   # mínimo aceptable para seguir operando el símbolo
WR_TARGET_IDEAL = 0.62   # objetivo sostenible — re-evaluar cada 50 trades

# ── Swing strategy hardening params ──────────────────────────────────────────
SWING_CONSEC_LOSS_PAUSE = 2   # Pausar símbolo tras N pérdidas SWING consecutivas
SWING_EMA50_TREND_FILTER = True  # Only enter with EMA50 direction (4H)

# ── Phase 2: Market Intelligence ─────────────────────────────────────────────
FUNDING_EXTREME_LONG  = 0.0005   # 0.05% — ccxt devuelve decimal (longs crowded)
FUNDING_EXTREME_SHORT = -0.0005  # -0.05% (shorts crowded)
ADX_TRENDING_THRESHOLD = 20      # ADX > 25 = trending
BB_WIDTH_RANGING_PCT   = 0.015    # BB width < 2% = ranging (bajo edge)
ATR_VOLATILE_PERCENTILE = 80     # ATR > percentil 80 = volatile
REGIME_CACHE_TTL       = 900     # 15 min cache por simbolo
FUNDING_CACHE_TTL      = 300     # 5 min cache
COINGLASS_CACHE_TTL    = 600     # 10 min cache (limite free tier: 10 calls/min)

# ── Phase 5: Dynamic Leverage + Portfolio Risk ───────────────────────────────
LEVERAGE_MIN = 2           # VIX > 35 o VOLATILE
LEVERAGE_LOW = 3           # VIX > 25 o RAPIDA
LEVERAGE_DEFAULT = 5       # Normal
LEVERAGE_MAX = 7           # Low vol + TRENDING
MAX_CONCURRENT_POSITIONS = 3       # Maximo 3 posiciones simultaneas
MAX_PORTFOLIO_EXPOSURE = 3.0       # Exposure < 3x balance

# ── Webhook TradingView: auth + rate limit ───────────────────────────────────
# Los valores reales viven en .env (TV_WEBHOOK_SECRET, TV_WEBHOOK_TOKEN,
# ENFORCE_HMAC, TV_RATE_LIMIT_PER_MIN). Ver webhook_security.py.
# ENFORCE_HMAC=false default (canary) — activar tras validar Pine firma OK.
TV_RATE_LIMIT_PER_MIN_DEFAULT = 10

# ── v1.2.0: Cuadrilla Zenith — formato compacto + filtros ratio S/N ──────────
# Cambios: SENTINEL solo si score >=4/5, dedupe 90min, frecuencia 4h (era 2h),
# SALMOS PROPHECY hourly removido (duplicaba PANORAMA). /verbose toggle revierte.
SENTINEL_MIN_SCORE_OF_5 = 4       # Skip si veredict score < 4/5
SENTINEL_INTERVAL_SEC   = 14400   # 4h (era 7200 = 2h)
SENTINEL_DEDUPE_MIN     = 90      # No re-enviar mismo (sym, bias) en últimos 90min
KILL_SALMOS_PROPHECY    = True    # Mata trigger_salmos_prophecy() en main loop

# ── Manual Positions (Fernando) — contexto para Cuadrilla Zenith ─────────────
# Actualizado: 2026-04-29. Usar en gemini_analyzer.py para que el análisis
# considere exposición existente al calcular bias y tamaño de señal.
MANUAL_POSITIONS = [
    {
        "symbol": "TAO", "side": "LONG", "entry": 295.0,
        "current_approx": 261.0, "pnl_usd": -345.0,
        "leverage_loss_usd": -163.0,  # pérdida realizada por apalancamiento
        "platform": "Quantfy+leverage",
        "note": "Posición en drawdown. Nivel clave de soporte: ~$250. Evaluar BE o cierre parcial si rebota a $280+."
    },
    {
        "symbol": "ZEC", "side": "LONG", "entry": 358.0,
        "current_approx": 334.0, "pnl_usd": -107.0,
        "platform": "Binance spot",
        "note": "En drawdown. ZEC WR histórico 29.5% — mejor activo del bot. Esperar confirmación técnica."
    },
    {
        "symbol": "DOGE", "side": "LONG", "entry": 0.10299,
        "current_approx": 0.10948, "pnl_usd": 136.0,
        "platform": "Binance spot",
        "note": "En ganancia +$136. Considerar mover SL a BE (~0.10299)."
    },
]
