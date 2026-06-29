"""
config.py — Configuración Central del Zenith Trading Suite

Todos los thresholds, símbolos e intervalos en un solo lugar.
Importar en cualquier módulo con: from config import RSI_LONG_ENTRY, SYMBOLS, ...
"""

# ── Símbolos operados ─────────────────────────────────────────────────────────
# Plan Fénix F1 — auto-scan AISLADO a ZEC (único experimento auto, V3-REVERSAL, telemetría medida, muerte 30d).
# BTC/ETH/etc. siguen disponibles como contexto macro (se fetchean por el mapa de precios hardcoded,
# no por esta lista) y como tracking manual (MANUAL_SYMBOLS, lista completa abajo).
# Histórico previo a Fénix: SYMBOLS = ["ZEC","BTC","ETH","SOL","HBAR","DOGE","TON","HYPE"] — 18.7% WR ciego, jubilado.
SYMBOLS = ["ZEC"]
MACRO_WATCH = []  # Todos los símbolos ahora son operables

# Plan Fénix F0.3 — kill-switch del macro feed (iShares/BlackRock vía yfinance).
# yfinance devuelve $0.00 desde Railway → BRI siempre NEUTRAL (ruido). Off por default:
# si está off, BRI no entra a la confluencia (honesto: "no hay macro, no lo finjas").
import os as _os
MACRO_FEED_ENABLED = _os.getenv("MACRO_FEED_ENABLED", "false").lower() in ("1", "true", "yes")

# Plan Fénix F1 — Sentinel auto solo para ZEC (el experimento/cockpit core). TAO/TON quedan
# on-demand vía /intel. Antes corrían ZEC+TAO+TON juntos cada ciclo → ~7.5k tokens > 8000 TPM de
# Groq gpt-oss-120b → 429 → ZEC se comía el rate-limit. Narrow a ZEC = sin 429. Coma-separado en env.
SENTINEL_AUTO_SYMS = [s.strip().upper() for s in _os.getenv("SENTINEL_AUTO_SYMS", "ZEC").split(",") if s.strip()]

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

    # ── PTS Reports Apr 13-15 2026 ───────────────────────────────────────────
    {"ticker": "RKLB",  "yf_ticker": "RKLB",  "direction": "LONG",
     "entry": 74.90,  "stop_loss": 91.0,  "take_profit_1": 100.0, "take_profit_2": None, "break_even": 83.0,
     "context": "PTS 08-May-2026. RKLB +30% post-earnings — T1 ($91) superado!! Stop movido a T1. Quienes están dentro siguen con stop en ganancia. Sin reentrada por ahora. GR original -1.1%. 1 acción/$1k."},

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
     "context": "PTS 08-May-2026. MP Materials. Quienes vendieron pre-earnings ganaron. Subió fuerte y se devolvió con fuerza. Pueden tomar ganancias en 68 y esperar. Pendiente reentrada próxima semana — esperar resolución del rango actual. GR original -1.5%."},

    {"ticker": "SOFI",  "yf_ticker": "SOFI",  "direction": "LONG",
     "entry": 16.99,  "stop_loss": 12.94,  "take_profit_1": 25.0,  "take_profit_2": 28.0,  "break_even": 21.0,
     "context": "PTS 08-May-2026. SOFI REENTRADA post-earnings. Muy débil tras earnings, esperando recuperación. Entrar si alcanza 16.99 (barrida post-earnings). GR -1%. 2 acciones/$1k. Options: BUY CALL 18-Sep-2026 Strike 22 (riesgo ~$80, pot $350-550)."},

    # ── PTS Post-earnings May 8 2026 ─────────────────────────────────────────
    {"ticker": "CRWV",  "yf_ticker": "CRWV",  "direction": "LONG",
     "entry": 121.82, "stop_loss": 91.79,  "take_profit_1": 160.0, "take_profit_2": 187.0, "break_even": 140.0,
     "context": "PTS 08-May-2026. CoreWeave SWING ALCISTA. Cayó con earnings, cobertura protegió, volvió a BE. PHY alcista activo. Si sostiene ZR corto plazo se recupera. GR -3%. 1 acción/$1k. Options: BUY CALL 16-Oct-2026 Strike 125 (riesgo ~$1,200, pot $2,600-5,000)."},

    {"ticker": "OKLO",  "yf_ticker": "OKLO",  "direction": "LONG",
     "entry": 73.91,  "stop_loss": 50.26,  "take_profit_1": 101.0, "take_profit_2": 137.0, "take_profit_3": 161.0, "break_even": 84.0,
     "context": "PTS 08-May-2026. OKLO (nuclear SMR). ⚠️ EARNINGS MARTES — QF debe vender Lun/Mar, options reciben cobertura martes. Entry válida post-earnings. GR -2.3%. 1 acción/$1k. Options: BUY CALL 20-Nov-2026 Strike 75 (riesgo ~$1,250, pot $1,800-6,500)."},

    {"ticker": "SMR",   "yf_ticker": "SMR",   "direction": "LONG",
     "entry": 12.67,  "stop_loss": 9.54,   "take_profit_1": 17.0, "take_profit_2": 19.0, "take_profit_3": 22.0, "break_even": 15.0,
     "context": "PTS 08-May-2026. SMR (nuclear small modular reactor). Nueva — pasó earnings. Sector nuclear despertando. GR -1.2%. 4 acciones/$1k. Options: BUY CALL 20-Nov-2026 Strike 13 (riesgo ~$200, pot $220-800)."},

    # ── Mencionadas en PTS — niveles pendientes ───────────────────────────────
    {"ticker": "IREN",  "yf_ticker": "IREN",  "direction": "LONG",
     "entry": 45.22,  "stop_loss": 57.0,  "take_profit_1": 67.0, "take_profit_2": 77.0, "take_profit_3": 89.0, "break_even": 59.0,
     "context": "PTS 08-May-2026. IREN — quienes están dentro: stop de ganancia en 57. Quienes salieron pre-earnings ganaron. Sin reentrada externa aún — esperar resolución del rango (BR.A). Próximos días PTS enviará reentrada. Options dentro siguen en ganancia."},

    {"ticker": "UUUU",  "yf_ticker": "UUUU",  "direction": "LONG",
     "entry": 22.72,  "stop_loss": 18.50,  "take_profit_1": 28.0, "take_profit_2": 31.0, "take_profit_3": 35.0, "break_even": 25.0,
     "context": "PTS 08-May-2026. Energy Fuels (uranium/nuclear). Nueva entrada post-earnings (subió fuerte, llegó a BE y se devolvió). Entry 22.72, BE 25. GR -1%. 3 acciones/$1k. Options: BUY CALL 16-Oct-2026 Strike 22 (riesgo ~$200, pot $400-950)."},

    {"ticker": "IONQ",  "yf_ticker": "IONQ",  "direction": "LONG",
     "entry": 50.05,  "stop_loss": 35.44,  "take_profit_1": 72.0, "take_profit_2": 85.0, "break_even": 62.0,
     "context": "PTS 08-May-2026. IonQ (quantum computing). Nueva entrada post-earnings (quienes salieron pre-earnings ganaron). Entry 50.05. GR -1.5%. 1 acción/$1k. Options: BUY CALL 16-Oct-2026 Strike 55 (riesgo ~$480, pot $1,100-1,500)."},

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

    # ── PTS Reports May 19 + May 22 2026 ─────────────────────────────────────
    {"ticker": "RGTI",  "yf_ticker": "RGTI",  "direction": "LONG",
     "entry": 19.0,  "stop_loss": 21.23, "take_profit_1": 34.21, "take_profit_2": 39.40, "break_even": 30.31,
     "context": "PTS 22-May-2026. Rigetti Computing (quantum). Entry original PTS $19; precio actual $26.42 (ya en ganancia). ATR=$2.60. Niveles ATR-based (Spec 001 May-22). PTS: 'puede ir a máximos, de los trades más grandes del año'."},

    {"ticker": "CORZ",  "yf_ticker": "CORZ",  "direction": "LONG",
     "entry": 25.26, "stop_loss": 22.24, "take_profit_1": 29.79, "take_profit_2": 32.81, "break_even": 27.53,
     "context": "PTS 22-May-2026. CORZ AI infrastructure. Precio $25.26, ATR=$1.51. Niveles ATR-based (Spec 001 May-22). PTS: 'súper acción, puede multiplicar precio'. Confirmar entrada formal próximo reporte (Mar 27-May)."},

    {"ticker": "CIFR",  "yf_ticker": "CIFR",  "direction": "LONG",
     "entry": 21.97, "stop_loss": 18.25, "take_profit_1": 27.56, "take_profit_2": 31.28, "break_even": 24.76,
     "context": "PTS 22-May-2026. CIFR (Cipher Mining / AI infra). Precio $21.97, ATR=$1.86. Niveles ATR-based (Spec 001 May-22). 'Pronto activa, súper acción con enorme potencial'."},

    {"ticker": "JNJ",   "yf_ticker": "JNJ",   "direction": "LONG",
     "entry": 234.36, "stop_loss": 226.48, "take_profit_1": 246.18, "take_profit_2": 254.06, "break_even": 240.27,
     "context": "PTS 22-May-2026. Johnson & Johnson DEFENSIVA pero FUERTE. Precio $234.36, ATR=$3.94. Niveles ATR-based (Spec 001 May-22). 'Activó hoy, arriba del punto de entrada — como defensiva con fuerza alcista de semiconductores'."},

    {"ticker": "KO",    "yf_ticker": "KO",    "direction": "LONG",
     "entry": 81.49, "stop_loss": 79.26, "take_profit_1": 84.83, "take_profit_2": 87.06, "break_even": 83.16,
     "context": "PTS 22-May-2026. Coca-Cola DEFENSIVA. Precio $81.49, ATR=$1.11 (movimiento lento). Niveles ATR-based ajustados (Spec 001 May-22). 'En zona de entrada, válido para operar como sector defensivo'."},

    {"ticker": "CL",    "yf_ticker": "CL",    "direction": "LONG",
     "entry": 90.62, "stop_loss": 86.96, "take_profit_1": 96.12, "take_profit_2": 99.78, "break_even": 93.37,
     "context": "PTS 22-May-2026. Colgate-Palmolive DEFENSIVA. Precio $90.62, ATR=$1.83. Niveles ATR-based (Spec 001 May-22). 'En zona de entrada, válido para operar como sector defensivo'."},

    {"ticker": "CLSK",  "yf_ticker": "CLSK",  "direction": "LONG",
     "entry": None, "stop_loss": None, "take_profit_1": 23.0, "take_profit_2": 32.0, "break_even": None,
     "context": "PTS 19-May-2026. CleanSpark (AI infra, ex-BTC mining). OM alcista formándose, +9% en sesión, ruptura 0.38 fib → target $23 luego $32. NO operativa aún en PTS, solo en monitoreo. Esperar señal formal."},

    {"ticker": "MO",    "yf_ticker": "MO",    "direction": "LONG",
     "entry": None, "stop_loss": None, "take_profit_1": None, "break_even": None,
     "context": "PTS 22-May-2026. Altria DEFENSIVA. 'Va muy bien arriba del punto de entrada'. Niveles pendientes."},

    {"ticker": "ASTS",  "yf_ticker": "ASTS",  "direction": "LONG",
     "entry": None, "stop_loss": None, "take_profit_1": None, "break_even": None,
     "context": "PTS 22-May-2026. AST SpaceMobile. 'Ya va en ganancias muy buenas'. Setup original Apr-26. Niveles pendientes."},

    {"ticker": "CVX",   "yf_ticker": "CVX",   "direction": "LONG",
     "entry": None, "stop_loss": None, "take_profit_1": None, "break_even": None,
     "context": "PTS 22-May-2026. Chevron petrolera. 'Más lenta pero muy sólida, va a seguir subiendo'. XOM tocó BE. Niveles pendientes."},

    {"ticker": "VAL",   "yf_ticker": "VAL",   "direction": "LONG",
     "entry": None, "stop_loss": None, "take_profit_1": None, "break_even": None,
     "context": "PTS 22-May-2026. Valaris petrolera. 'Retrocedió y está más barata, potencial alcista intacto'. Niveles pendientes."},
]

# ── Defensive sectors (no filtrar con bias bajista) ──────────────────────────
# Expandido May-22-2026: nuclear + AI-infra + quantum + petroleras + defensivos
DEFENSIVE_SECTORS = [
    "XOM", "MOO", "GDX", "XBI", "COIN", "RKLB", "HOOD", "MP", "SOFI",
    "UUUU", "IREN", "XLE", "OKLO", "SMR", "IONQ", "RDDT", "CRWV",
    "RGTI", "CORZ", "CIFR", "JNJ", "KO", "CL", "MO", "CVX", "VAL", "ASTS",
]

# ── Clusters de correlación (no acumular 3+ del mismo en una sesión) ─────────
# Riesgo: si un cluster colapsa, exposure concentrado. Bot debe limitar 1-2 por cluster.
SECTOR_CLUSTERS = {
    "nuclear":   ["UUUU", "OKLO", "SMR"],
    "ai_infra":  ["CRWV", "IREN", "CORZ", "CIFR", "CLSK"],
    "quantum":   ["IONQ", "RGTI"],
    "crypto_proxy": ["COIN", "MSTR", "IREN", "CORZ", "CIFR", "CLSK"],
    "petroleras": ["XOM", "CVX", "XLE", "VAL"],
    "defensivos": ["JNJ", "KO", "CL", "MO", "MOO"],
}
MAX_PER_CLUSTER = 2   # Max 2 posiciones simultáneas por cluster (default fallback)

# ── Spec 004 (NotebookLM 2026-05-26): MAX por cluster específico ─────────────
# Justificación detallada en docs/research/notebook-lm/RESULTS.md (Prompt 3).
# Lookup: MAX_PER_CLUSTER_BY_CLUSTER.get(cluster_name, MAX_PER_CLUSTER)
# Notas:
#   nuclear=2: barridas conjuntas, regla explícita Daniel
#   ai_infra=2: default; PRIORITY_BOOST_CLUSTER lo sube a 3 esta semana
#   quantum=0: suprimido hasta QUANTUM_SUPPRESSED_UNTIL (auto-expire)
#   crypto_proxy=1: restringido hasta BTC > CRYPTO_PROXY_BTC_GATE
#   petroleras=3: cobertura descorrelacionada, riesgo bajo
#   defensivos=3: baja volatilidad, riesgo bajo
MAX_PER_CLUSTER_BY_CLUSTER = {
    "nuclear": 2,
    "ai_infra": 2,
    "quantum": 0,
    "crypto_proxy": 1,
    "petroleras": 3,
    "defensivos": 3,
}

# ── Semana 26-30 May 2026 — PTS dinámico (Daniel Marin 25-May 23:00) ─────────
# Reporte rápido apertura semana. SP500 gap alcista, plan semanal:
# PTS 8m (27-May-2026): prioridad por sector actualizada
#   MÁXIMA: AI Infra (IREN activa en $61, CORZ/CIFR subiendo, CRWV>94 válido)
#   ALTA: cuánticas EN BE — esperar BARRIDA para reentrada, no nueva entrada ahora
#   MEDIA: nuclear (OKLO+META acuerdo), tierras raras (MP activa)
#   BAJA: fintech suelo (SOFI>17, HOOD>78), petroleras (barrida CP)
#   SUPRIMIDO: COIN (ZR 172 = última barrera — si pierde = crypto sistémico débil)
WEEK_PRIORITY_HIGH   = ["IREN", "CORZ", "CIFR", "CRWV"]   # AI Infra — más alcista
WEEK_PRIORITY_MEDIUM = ["OKLO", "SMR", "MP", "UUUU"]       # Nuclear + tierras raras
WEEK_PRIORITY_LOW    = ["SOFI", "HOOD", "CVX", "VAL", "XLE", "JNJ", "KO", "CL", "MO"]
QUANTUM_SUPPRESSED   = ["IONQ", "RGTI"]   # En BE — esperar retroceso para nueva entrada
QUANTUM_REENTRY_PULLBACK_PCT = 10.0
QUANTUM_SUPPRESSED_UNTIL = "2026-06-15"   # 8m: extendido (en BE, no sobreextendido — pero esperar barrida)

# PTS 8m: niveles críticos BTC y COIN
BTC_CRITICAL_SUPPORT_8M  = 76000.0   # Pérdida = confirmación bajista → alts bajo presión
COIN_STOP_TOLERANCE_8M   = 172.0     # Última ZR COIN — si pierde = crypto debilidad sistémica
CLSK_WATCH_PULLBACK      = True      # CLSK escapada, no operar ahora — esperar retroceso

# Spec 004: gate de crypto proxies — pipeline solo activa si BTC > este nivel
# PTS reporte 8h: "trigger pendiente de activación si SP500 pierde 6,728" + "Crypto breakout
# pending, trigger si supera $74k". Enforcement real es backlog (requiere fetch BTC en stock_watchdog).
CRYPTO_PROXY_BTC_GATE = 74000.0

# Spec 004: bonos macro vigilancia (PTS reporte 8k jueves 29). Sin alertas directas,
# solo etiqueta cuando aparezcan en signal feed. TLT = bonos 20Y largos; TBT = inverso.
MACRO_BONDS_WATCH = ["TLT", "TBT"]
PRIORITY_BOOST_CLUSTER = "ai_infra"     # Esta semana: permite hasta 3 (vs 2 default) si SP500>7000
PRIORITY_BOOST_MAX_PER_CLUSTER = 3
WEEK_REVIEW_DATE = "2026-05-25"          # Última actualización PTS — invalidar después de 7 días


# ── Thresholds RSI ────────────────────────────────────────────────────────────
RSI_LONG_ENTRY       = 40.0   # Entrada Long estándar (was 42 — too restrictive)
RSI_LONG_ZEC_ENTRY   = 48.0   # ZEC tiene mayor volatilidad — entrada más conservadora
RSI_LONG_EXTREME     = 30.0   # Entrada Long extrema (reversal / modo rescate)
RSI_LONG_TAO_EXTREME = 32.0   # TAO modo rescate (legacy, ahora dict abajo)
RSI_LONG_ZEC_EXTREME = 30.0   # ZEC modo rescate agresivo (legacy)

# Per-symbol RSI threshold para V3-REVERSAL (sincronizado strategies.py + backtester.py)
# Si símbolo no está aquí → usa RSI_LONG_EXTREME (default 30)
RSI_REVERSAL_BY_SYMBOL = {
    "TAO": 28.0,    # ronda 4: 32→28 mejoró TAO V3 OOS de -14.7% a -3.0%
    "ZEC": 20.0,    # backtest tune Jun-2026: 20 → 60% WR +8.38R (vs 30 → 47% -5.35R)
    "ETH": 32.0,    # ETH V3 ✅ campeón OOS (+15.9%)
    "BTC": 32.0,    # BTC V3 marginal positivo OOS
}

# SL más ajustado para V3 — backtest Jun-2026: 1.5 > 2.0 en todos los símbolos
V3_SL_ATR_MULT = 1.5

# Multi-TF filter (NFI style) ronda 5 — bloquea V3 LONG si RSI 4H demasiado alto
# Permite reversal solo cuando 4H también está débil → reduce false signals
MTF_RSI_4H_MAX = 50.0  # V3 LONG: solo si rsi_4h <= 50

RSI_SHORT_ENTRY      = 55.0   # Entrada Short estándar (was 62 — casi nunca en downtrend)
RSI_SHORT_EXTREME    = 70.0   # Entrada Short extrema

# ── ATR Multipliers (gestión de riesgo) ───────────────────────────────────────
ATR_SL_MULT         = 2.0    # Stop Loss = entry ± (ATR * mult)
ATR_TP1_MULT        = 3.0    # TP1 = 2:1 R:R
ATR_TP2_MULT        = 5.0    # TP2 = 3.5:1 R:R
ATR_TP3_MULT        = 7.0    # TP3 = 7:1 R:R (moonshot, V2-AI)
ATR_MIN_SL_PCT      = 0.012  # SL mínimo: 0.7% del precio (evita SL muy ajustados)
ATR_MIN_SL_REVERSAL = 0.010  # SL mínimo para reversals (wider = less noise stops)

# --- STRATEGY KILL SWITCHES (basado en análisis win rate 76 trades) ---
V1_SHORT_ENABLED     = False   # 0% WR en 16 trades — disabled Apr 2026
V1_LONG_ENABLED      = False   # 15.4% WR / -34.1% PnL en backtest 365d → disabled May 2026
V4_BLOCKLIST         = ["ETH", "ZEC"] # ETH (-7% PnL) + ZEC (overfit walk-forward, deg -100%) excluidos
V5_ENABLED           = False   # 0 trades en backtest 365d → bug o filtro muy restrictivo, deshabilitado
TAO_TRADING_ENABLED  = False   # Spec 001 (May-22-2026): bot-generated TAO 0/31 (0% WR). rsi_entry=50 placeholder = pipeline indicadores roto. Kill.
TAO_SHORT_ENABLED    = False   # Spec 001 (May-22-2026): 75% de SHORT losses son TAO-SHORT. Kill explícito.
SWING_BLOCKLIST      = ["TAO", "ZEC"]  # Spec 001 (May-22-2026): ZEC Q3+Q4 WR=0% chase del top. V4_BLOCKLIST no aplica porque vienen por SWING channel.
# Spec NB3 P0 (2026-05-26 NotebookLM 3 audit): GOLD WR 14.3%, 5/15 Top Losers, paradoja conf_score=5 todas LONG ORO.
COMMODITY_BLOCKLIST  = ["GOLD"]        # Bloquear COMMODITY trades en estos símbolos
BLOCK_SCORE_5        = True            # Kill switch conf_score=5 (0% WR overfitted)
MIN_RSI_LONG         = 50.0            # NotebookLM: 15/17 wins en RSI 50-60, RSI 40-50 = 11.1% WR
SHORT_BLOCKED_IN_VERDE_BULL = True     # Spec 001: cuando SP500>7000 + VIX<22 (VERDE_BULL_DORMANT), no abrir shorts en cripto.
# Plan Fénix F1 — HMM régimen (Spec 009/016) off por default. Gateaba V3 en STRONG_TREND pero hmmlearn
# no siempre está instalado → comportamiento no determinista local vs Railway. Se mantiene state machine
# (regime_transitions.py). Re-encender solo con telemetría que justifique el gate.
HMM_ENABLED          = _os.getenv("HMM_ENABLED", "false").lower() in ("1", "true", "yes")

# ── Confluence Score ──────────────────────────────────────────────────────────
MIN_CONFLUENCE_SCORE = 5     # Score mínimo para disparar alerta
USDT_D_THRESHOLD    = 8.05   # Por encima: condición bajista para cripto

# ── Volatilidad / Riesgo ──────────────────────────────────────────────────────
ZEC_MAX_VOL_PCT     = 3.5    # % ATR/Precio máximo para ZEC (guarda anti-manipulación)
VIX_RAPIDA_THRESHOLD = 18.0  # VIX > 18 → trade RAPIDA (was 22 — VIX base post-FOMC Apr-26: ~18-20)
VIX_EXTREME_THRESHOLD = 32.0 # VIX > 32 → no operar / mínima posición (was 35)
VIX_DORMANT_THRESHOLD = 22.0 # PTS May-22: VIX < 22 + SP500 > 7000 → barridas = oportunidad de entrada (no panic mode)

# ── Macro Regime Gate (PTS May-22-2026) ──────────────────────────────────────
# Determina régimen según SP500 + VIX. Bot consulta esto antes de filtrar señales.
#   VERDE_BULL (SP500 > 7000):       no suprimir longs, barridas = entrada
#   AMARILLA_INDECISA (6800-7000):    reducir tamaño 50%, requiere confluencia extra
#   NARANJA_BEAR (< 6800):            activar SHORT SPY, filtrar longs débiles
SP500_VERDE_THRESHOLD     = 7000.0
SP500_NARANJA_THRESHOLD   = 6800.0
SP500_NARANJA_TRIGGER_SHORT = 6728.0  # Pierde 6728 → SHORT SPY activado
DXY_CRIPTO_PRESSURE = 103.0  # DXY > 103 → presión bajista en cripto (was 105 — FOMC: USD safe-haven activo)
OIL_INFLATION_THRESHOLD = 85.0  # Oil > $85 = presión inflacionaria → hawkish Fed (FOMC Mar-26)

# ── FOMC Calendar ────────────────────────────────────────────────────────────
FOMC_NEXT_MEETING = "2026-06-17"   # Próxima reunión FOMC (Apr 28-29 ya pasó) — suprimir señales 24h antes
RATE_BIAS = "HAWKISH_HOLD"         # FOMC Mar-26: tasas 3.50-3.75%, 30% prob de subida, sin recortes hasta dic

# ── Earnings Suppression (Spec 001 May-22-2026) ──────────────────────────────
# Símbolos con earnings críticos. Bot debe suprimir señales 24h antes/después
# (igual que FOMC logic). Fechas en EARNINGS_CALENDAR per-symbol abajo.
EARNINGS_SUPPRESS_24H = ["NVDA", "OKLO", "TSLA", "MSFT", "META", "AAPL", "GOOGL"]
# Fechas de earnings conocidas (YYYY-MM-DD). Actualizar al recibir confirmación.
EARNINGS_CALENDAR = {
    "OKLO": "2026-05-27",  # PTS 08-May: earnings martes (siguiente martes)
    "NVDA": "2026-05-21",  # PTS 19-May referenció earnings esta semana — ya pasó
}

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
V4_EMA_PROXIMITY_MIN = 1.005   # Precio min 0.1% arriba (confirma no quiebre)
V4_RSI_LOW           = 35.0    # RSI minimo (zona de recuperacion)
V4_RSI_HIGH          = 50.0    # RSI maximo (no sobrecomprado)
V4_RSI_HIGH_ZEC      = 55.0    # ZEC: umbral mas alto por volatilidad
V4_MIN_CONFLUENCE    = 3       # Confluencia minima (vs 4 de V1)
V4_ATR_SL_MULT       = 1.5    # SL mas ajustado: 1.5x ATR
V4_COOLDOWN          = 600     # 10 min cooldown (vs 5 min de V1)
# Per-symbol EMA proximity (altcoins need wider window due to higher ATR/price)
V4_EMA_PROX_MAP = {"BTC": 1.02, "ETH": 1.025, "TAO": 1.03, "ZEC": 1.03, "TON": 1.03}

# ── V3 Reversal improvements ────────────────────────────────────────────────
V3_MIN_CONFLUENCE    = 4       # Was 3 — too many false reversals
V3_MAX_HOLDING_BARS  = 96      # Force-close stale V3 trades after 48 bars (48h)
V3_REQUIRE_DIVERGENCE = True   # RSI bullish divergence required
V3_REQUIRE_BB_SQUEEZE = True   # BB width contracting (sell-off losing steam)

# ── V1-SHORT improvements ───────────────────────────────────────────────────
SHORT_MIN_CONFLUENCE = 3       # Was 4 — hard to accumulate for shorts
SHORT_REGIMES = ("TRENDING_DOWN", "VOLATILE")  # Was only TRENDING_DOWN
SHORT_EMA_SLOPE_MIN  = -0.001  # EMA200 must be declining

# ── Regime improvements ─────────────────────────────────────────────────────
ADX_CHOPPY_THRESHOLD = 20      # ADX < 20 + BB 2-4% = CHOPPY (suppress all)
REGIME_COOLDOWN_BARS = 6       # Bars to wait after regime transition
RVOL_MIN_ENTRY       = 0.8     # Relative Volume minimum for entries
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

# Spec 006 (2026-05-26 — NotebookLM 4): Funding Rate gate para V3-REVERSAL.
# Annualized % por encima del threshold = latigazo volatilidad inminente, apalancamiento extremo.
# NotebookLM recomendó 10%. Empezamos en 30% conservador, bajar a 10 tras 1 semana de logs.
FUNDING_REVERSAL_BLOCK_ANNUALIZED = 30.0  # % anualizado. > threshold = skip V3 reversal.
ADX_TRENDING_THRESHOLD = 25      # ADX > 25 = trending
BB_WIDTH_RANGING_PCT   = 0.01    # BB width < 2% = ranging (bajo edge)
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

# ── v1.3.0: Buttons kill switch ──────────────────────────────────────────────
# Período de análisis exhaustivo: sin botones inline ni menús reply en Telegram.
# Reenchufar caso por caso bajando este flag o filtrando por tipo de alerta.
ENABLE_TELEGRAM_BUTTONS = True  # UX redesign 2026-05-26: 6 botones reply keyboard activo

# ── v1.3.0: Quiet mode (análisis exhaustivo) ─────────────────────────────────
# Mata alertas NO accionables: PULSO NYSE, PANORAMA AI, NINJA pre-warning,
# startup ONLINE msgs. Mantiene: V2-AI, SENTINEL ZEC, SWING, STOCK NEAR ENTRY,
# trade lifecycle (TP/SL/BE), daily report.
# Bajar flag = restaurar todas las alertas previas.
ANALYSIS_MODE_QUIET = True

# ── Manual Positions ─────────────────────────────────────────────────────────
# Storage unificado en trades.db (flag is_manual=1). Sin seed hardcoded.
# Lista de símbolos preferidos para el picker de /open (inline keyboard).
MANUAL_SYMBOLS = ["TAO", "ZEC", "DOGE", "SOL", "BTC", "ETH", "TON", "HYPE", "BNB"]
# BNB: backtest Jun-2026 V4-EMA → +84.8R, 54.6% WR, mejor símbolo en el universe.
# Candidato a SYMBOLS[] para auto-scan V4 post-Fénix F1 (hoy aislado a ZEC).

# ── Spec 010: Whale Netflows (on-chain tracker, NotebookLM 4 Prompt 3) ───────
# Fuente: Etherscan + BscScan free APIs. Tracking transfers >$1M to/from exchanges.
# Net inflow = bearish (whales depositan para vender). Net outflow = bullish (accum).
# Thresholds basados en ranking NotebookLM (signal noise floor ~$10M para ETH).
WHALE_NETFLOW_BEARISH_USD = 10_000_000   # net_flow > 10M = BEARISH (whale dump incoming)
WHALE_NETFLOW_BULLISH_USD = -10_000_000  # net_flow < -10M = BULLISH (accumulation)
WHALE_NETFLOW_CACHE_TTL = 300            # 5 min cache (Etherscan free tier: 5 calls/sec)
WHALE_NETFLOW_TIMEOUT = 8.0              # seconds — HTTP request timeout
