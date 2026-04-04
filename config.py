"""
config.py — Configuración Central del Zenith Trading Suite

Todos los thresholds, símbolos e intervalos en un solo lugar.
Importar en cualquier módulo con: from config import RSI_LONG_ENTRY, SYMBOLS, ...
"""

# ── Símbolos operados ─────────────────────────────────────────────────────────
SYMBOLS = ["ZEC", "TAO"]
MACRO_WATCH = ["BTC", "ETH"]  # Solo para contexto macro, no se opera

# ── Thresholds RSI ────────────────────────────────────────────────────────────
RSI_LONG_ENTRY       = 42.0   # Entrada Long estándar
RSI_LONG_ZEC_ENTRY   = 48.0   # ZEC tiene mayor volatilidad — entrada más conservadora
RSI_LONG_EXTREME     = 30.0   # Entrada Long extrema (reversal / modo rescate)
RSI_LONG_TAO_EXTREME = 28.0   # TAO modo rescate
RSI_LONG_ZEC_EXTREME = 26.0   # ZEC modo rescate agresivo
RSI_SHORT_ENTRY      = 62.0   # Entrada Short estándar
RSI_SHORT_EXTREME    = 70.0   # Entrada Short extrema

# ── ATR Multipliers (gestión de riesgo) ───────────────────────────────────────
ATR_SL_MULT         = 2.0    # Stop Loss = entry ± (ATR * mult)
ATR_TP1_MULT        = 2.0    # TP1 = 2:1 R:R
ATR_TP2_MULT        = 3.5    # TP2 = 3.5:1 R:R
ATR_TP3_MULT        = 7.0    # TP3 = 7:1 R:R (moonshot, V2-AI)
ATR_MIN_SL_PCT      = 0.007  # SL mínimo: 0.7% del precio (evita SL muy ajustados)
ATR_MIN_SL_REVERSAL = 0.008  # SL mínimo para reversals (mayor margen)

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
V4_EMA_PROXIMITY_MAX = 1.02    # Precio max 2% arriba de EMA200
V4_EMA_PROXIMITY_MIN = 1.001   # Precio min 0.1% arriba (confirma no quiebre)
V4_RSI_LOW           = 35.0    # RSI minimo (zona de recuperacion)
V4_RSI_HIGH          = 50.0    # RSI maximo (no sobrecomprado)
V4_RSI_HIGH_ZEC      = 55.0    # ZEC: umbral mas alto por volatilidad
V4_MIN_CONFLUENCE    = 3       # Confluencia minima (vs 4 de V1)
V4_ATR_SL_MULT       = 1.5    # SL mas ajustado: 1.5x ATR
V4_COOLDOWN          = 600     # 10 min cooldown (vs 5 min de V1)

# ── Versiones de estrategia ───────────────────────────────────────────────────
VERSIONS = ["V1-TECH", "V2-AI", "V4-EMA"]

# ── Phase 2: Market Intelligence ─────────────────────────────────────────────
FUNDING_EXTREME_LONG  = 0.0005   # 0.05% — ccxt devuelve decimal (longs crowded)
FUNDING_EXTREME_SHORT = -0.0005  # -0.05% (shorts crowded)
ADX_TRENDING_THRESHOLD = 25      # ADX > 25 = trending
BB_WIDTH_RANGING_PCT   = 0.02    # BB width < 2% = ranging (bajo edge)
ATR_VOLATILE_PERCENTILE = 80     # ATR > percentil 80 = volatile
REGIME_CACHE_TTL       = 900     # 15 min cache por simbolo
FUNDING_CACHE_TTL      = 300     # 5 min cache
COINGLASS_CACHE_TTL    = 600     # 10 min cache (limite free tier: 10 calls/min)
