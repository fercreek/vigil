"""
config.py — Configuración Central del Zenith Trading Suite

Todos los thresholds, símbolos e intervalos en un solo lugar.
Importar en cualquier módulo con: from config import RSI_LONG_ENTRY, SYMBOLS, ...
"""

# ── Símbolos operados ─────────────────────────────────────────────────────────
SYMBOLS = ["ZEC", "TAO"]
MACRO_WATCH = ["BTC", "ETH"]  # Solo para contexto macro, no se opera

# ── Watchlist estática de acciones (siempre monitoreada, independiente del reporte)
# yf_ticker: símbolo que entiende Yahoo Finance (CL=F = crude front month, GC=F = gold front month)
# Niveles marcados con ⚠️ = estimados con ATR pre-mercado (08-Apr-2026).
# Confirmar y ajustar al precio real de apertura antes de operar.
STOCK_WATCHLIST = [
    # ── Tu lista personal ─────────────────────────────────────────────────────
    {"ticker": "TSLA",  "yf_ticker": "TSLA",  "direction": "SHORT",
     "entry": 346.65, "stop_loss": 377.02, "take_profit_1": 285.91, "break_even": 316.28,
     "context": "⚠️ Niveles pre-mercado. MACRO PHY bajista activo. Confirmar apertura antes de entrar."},

    {"ticker": "PLTR",  "yf_ticker": "PLTR",  "direction": "LONG",
     "entry": 150.07, "stop_loss": 135.79, "take_profit_1": 178.62, "break_even": 164.35,
     "context": "⚠️ Niveles pre-mercado. Sector AI/defensa. Confirmar ruptura con volumen en apertura."},

    {"ticker": "SIL",   "yf_ticker": "SIL",   "direction": "LONG",
     "entry": 92.84,  "stop_loss": 82.55,  "take_profit_1": 113.43, "break_even": 103.13,
     "context": "⚠️ Niveles pre-mercado. Silver Miners ETF. DXY débil → setup alcista mineras plata."},

    {"ticker": "GCM6",  "yf_ticker": "GC=F",  "direction": "LONG",
     "entry": 4838.80, "stop_loss": 4476.47, "take_profit_1": 5563.46, "break_even": 5201.13,
     "context": "⚠️ Niveles pre-mercado. Oro Jun-2026. PHY alcista activo. DXY débil = setup largo."},

    {"ticker": "CLK6",  "yf_ticker": "CL=F",  "direction": "SHORT",
     "entry": 95.95,  "stop_loss": 115.04, "take_profit_1": 57.78,  "break_even": 76.86,
     "context": "⚠️ Niveles pre-mercado. Crudo May-2026. Monitorear soporte $60 y noticias OPEP+."},

    # ── Recomendaciones del bot ────────────────────────────────────────────────
    {"ticker": "GDX",   "yf_ticker": "GDX",   "direction": "LONG",
     "entry": 92.78,  "stop_loss": 82.16,  "take_profit_1": 102.0,  "break_even": 97.0,
     "context": "Setup PTS confirmado: DXY retrocede + oro rebota PHY. Operación rápida. BE en 97."},

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

# ── Confluence Score ──────────────────────────────────────────────────────────
MIN_CONFLUENCE_SCORE = 4     # Score mínimo para disparar alerta
USDT_D_THRESHOLD    = 8.05   # Por encima: condición bajista para cripto

# ── Volatilidad / Riesgo ──────────────────────────────────────────────────────
ZEC_MAX_VOL_PCT     = 3.5    # % ATR/Precio máximo para ZEC (guarda anti-manipulación)
VIX_RAPIDA_THRESHOLD = 25.0  # VIX > 25 → trade RAPIDA
VIX_EXTREME_THRESHOLD = 35.0 # VIX > 35 → no operar / mínima posición
DXY_CRIPTO_PRESSURE = 105.0  # DXY > 105 → presión bajista en cripto

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

# ── Phase 2: Market Intelligence ─────────────────────────────────────────────
FUNDING_EXTREME_LONG  = 0.0005   # 0.05% — ccxt devuelve decimal (longs crowded)
FUNDING_EXTREME_SHORT = -0.0005  # -0.05% (shorts crowded)
ADX_TRENDING_THRESHOLD = 25      # ADX > 25 = trending
BB_WIDTH_RANGING_PCT   = 0.02    # BB width < 2% = ranging (bajo edge)
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
