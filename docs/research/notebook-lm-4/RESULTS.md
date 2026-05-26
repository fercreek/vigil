# NotebookLM 4 — Trading Strategies Research Results

> **Fecha ejecución:** 2026-05-26
> **NotebookLM URL:** https://notebooklm.google.com/notebook/42d629b8-c782-40a0-9140-035f01891d00
> **Sources:** 11 (1 corpus + 10 Discover externos: HMM regime classifier, on-chain Glassnode, SMC crypto, ML sentiment, etc.)
> **Operador:** Fernando

## Prompt 1 — Top 5 estrategias factibles

| # | Estrategia | Qué aporta | Complej | Costo | WR esperado | Voz Zenith |
|---|-----------|-----------|---------|-------|-------------|------------|
| 1 | **HMM Regime Classifier** | Detecta tendencia/rango/vol extrema. Prende/apaga estrategias por régimen | 3 | $0 (hmmlearn) | ~60%+ filtra laterales | Transversal (Salmos + Apocalipsis) |
| 2 | **Spot CVD (Cumulative Volume Delta)** | Rastrea compras vs ventas a mercado. Identifica smart money + divergencias reales | 3 | $0 (Binance Trades API) | ~55-65% en S/R | Genesis (institucional) |
| 3 | **Sentimiento Social Quant** | Reddit + Google Trends → anticipa cambios régimen irracionales | 4 | $0 (praw, pytrends) | +6-7% sobre baseline | Exodo (narrativa) |
| 4 | **On-Chain Tracker (Glassnode)** | Direcciones activas + flujos exchange → adopción real + venta inminente | 2 | $0 (Glassnode Community) | ~55-60% macro | Genesis (flujo capital) |
| 5 | **Funding Rate Filter** | Tasas perps como predictor volatilidad + apalancamiento extremo | 1 | $0 (Binance) | Reduce drawdown | Apocalipsis (riesgo) |

### Top 1: Funding Rate Filter (Estrategia 5)

**Justificación:** Complejidad 1, cost $0, aborda inmediatamente protección capital ("No SHORT en bull" + mitigación TDAH). Endpoint gratuito Binance trae Funding Rate, configurable en pocas líneas como Kill Switch macro adicional al gate SP500/VIX. Apocalipsis absorbe el dato — si `Funding Rate > X%` bloquea entradas reversión (V3) porque viene latigazo de volatilidad. **Quick win más rápido** para supervivencia del sistema.

### Justificaciones por estrategia

- **HMM:** RMSE pronóstico volatilidad 0.015. Bot deja de predecir precio para predecir condición mercado. V3/SCALPER se desactivarían automáticamente en régimen incorrecto.
- **CVD:** Líneas por tamaño (retail <$1k, ballenas >$1M). Divergencia bajista (precio sube + CVD cae) = techo. Acumulación institucional (consolidación + CVD ballenas sube) = movimiento alcista.
- **Sentiment ML:** VADER o modelos NLP. Recall +7.7%, precisión +6.1%. Permite evadir crashes críticos.
- **On-chain:** Regresiones lineales sobre direcciones activas + volumen. Depósitos masivos a exchanges anticipan caídas.
- **Funding rate:** Históricamente tasas elevadas persistentes preceden colapsos longs. Gate macro como VIX.

## Prompt 2 — Smart Money Concepts (SMC)

### Veredicto: HÍBRIDO (extraer partes útiles, NO full SMC)

**Por qué NO full SMC:**
- WR rigoroso 35-45% en backtests cripto (SMC no busca WR alto, busca R:R 1:3 a 1:5).
- BOS/CHoCH en Python puro frágil, mucho ruido en TF menores.
- SMC es en gran medida repackaging de soporte/resistencia + zonas de liquidez (mapas de calor de volumen prueban gravedad hacia high-volume nodes).
- Real edge institucional NO está en dibujar bloques, sino en **Order Flow real** (CVD segmentado por tamaño — ballenas marrones vs retail amarillo).

### Detección algorítmica
- Sí factible: librería `smartmoneyconcepts` GitHub (pandas + numpy). Detecta fractales/pivotes para BOS/CHoCH + velas envolventes para Order Blocks (OB) + Fair Value Gaps (FVG).
- Encaja en stack Python 3.12.

### Compatibilidad Cuadrilla Zenith
- NO necesita 5ta voz (preserva budget IA $10/mes).
- **Salmos:** FVG/OB como confirmadores de entrada (confluencia técnica).
- **Genesis:** Liquidity sweeps encajan en narrativa de "Smart Money manipulando mercado".

### Partes que valen la pena

1. **Fair Value Gaps (FVG):** fáciles de codificar matemáticamente. Sirven para refinar TP dinámico ATR-based del bot.
2. **Liquidity Sweeps (Barridas):** combinables con macro gate actual (VIX<22 + SP500>7000 → barridas son oportunidades).

### Implementación
- Tiempo estimado: **1-2 semanas**.
- Foco: FVG + cálculo max/min para barridas.
- Inyectar datos al JSON mode de Salmos + Genesis (sin reescribir lógica Flask).

**Nota fuente:** la fuente SMC específica devolvió 404. WR data viene de conocimiento general — verificar empíricamente con backtest.

## Prompt 3 — On-chain signals

### Tabla señales más predictivas

| Señal | Provider gratis | Provider paid | Trigger threshold | Lead/lag vs precio |
|-------|-----------------|---------------|-------------------|---------------------|
| Whale Movements + Exchange Netflows | Etherscan/BscScan API | Nansen | >$1M o >1,000 ETH (inflow=sell, outflow=hold) | **Lead** anticipa caídas/acumulación |
| Funding Rates (perps) | Binance/Coinbase API | CoinMetrics | >10% anualizado persistente | Lag precio / **Lead** volatilidad |
| Spot CVD segmentado | Binance Trades API | Nansen/TradingLite | Línea marrón sube + línea amarilla baja | **Lead** anticipa reversiones |
| Active Addresses + Tx Volume + Gas | Glassnode Community (Alpaca SDK) | Glassnode Studio Pro | Regresión lineal slope > margin positivo | **Lead** indica adopción/crecimiento |

### Detalles por señal

**1. Exchange Netflows + Whale wallets:**
- Etherscan/BscScan API gratis. Movimientos >$1M o >1000 ETH.
- Inflows masivos a exchanges = presión venta (bearish). Outflows = acumulación (bullish).
- Voz Zenith: **Genesis** (institucional). Bloquear LONG si detecta inflows masivos.

**2. Funding Rates (perps):**
- Endpoints públicos Coinbase/Binance/Bybit.
- >10% anualizado persistente. Por diseño positivo >85% tiempo en BTC.
- NO predice dirección — sí predice **picos volatilidad inminente**.
- Voz Zenith: **Apocalipsis**. Si funding sobrecalentado → reducir tamaño posición (1→0.5 unidad).

**3. Active Addresses + Tx Volume + Gas fees:**
- Glassnode Community gratis (Alpaca SDK).
- Regresión lineal sobre 2+ métricas — slope positivo > margin = adopción real.
- Voz Zenith: **Exodo** (narrativa/tech). Sesgo macro alcista si blockchain ETH/SOL crece.

**4. Spot CVD segmentado:**
- Procesar Binance Time & Sales API (datos crudos).
- Divergencia: línea marrón ($1M-$10M) sube + línea amarilla ($100-$1k) baja = acumulación institucional → precede movimientos alcistas explosivos.
- Voz Zenith: **Salmos** (divergencias volumen) + **Genesis** (smart money).

### Top 3 señales a sumar primero (próxima semana)

1. **Funding Rates** ($0, 1h implementación) — quick win Apocalipsis, prever volatilidad extrema.
2. **Exchange Netflows ballenas** ($0, Etherscan API) — Genesis fundamental para bloquear longs pre-dump.
3. **CVD segmentado** ($0, más código pero cero costo runtime) — huella digital smart money sin pagar Nansen.

**Costo total: $0/mes.** Mantiene budget IA Gemini Flash 2.5 intacto.

## Prompt 4 — Market regime detection (ML)

### Veredicto: **HMM (Hidden Markov Models)** es el ganador

### Análisis por método

**1. HMM (Hidden Markov Models) — ✅ Recomendado**
- Edge real, no overfitting. Modelo no predice precio sino **condición subyacente**.
- NHHMM (non-homogéneo): RMSE volatilidad 0.015. Identifica consolidación/expansión alcista/corrección bajista.
- Python: `hmmlearn` library + repos cripto-específicos.
- Validado BTC OHLCV multi-TF (5m, 15m) + macro.
- Compute: CPU ligero (Expectation-Maximization).
- Voz Zenith: **Salmos**. Semáforo maestro — si HMM detecta "Strong Trend", bloquea V3-REVERSAL.

**2. GARCH (TV-MSGARCH) — Útil pero secundario**
- TV-MSGARCH efectivo para persistencia + jumps volatilidad BTC.
- Python: `arch` library.
- Supera baseline out-of-sample.
- Voz Zenith: **Apocalipsis**. Ajustar position sizing — si cluster volatilidad anticipado → 0.5 unidades.

**3. ADX vs TSI — Demasiado simples**
- Indicadores lagging puro precio pasado.
- Usados como features en ML (Random Forest, SVM) backtest hasta 4840% (2017, dudoso).
- Compute: ultra-bajo.
- Voz Zenith: Salmos como input crudo.

**4. K-means / DBSCAN — ❌ Descartado**
- Ignoran estructura secuencial temporal (no entienden orden).
- Defecto fatal en series de tiempo financieras vs HMM.

**5. LSTM (Deep Learning) — Híbrido con HMM, futuro**
- Híbrido HMM → LSTM: HMM etiqueta régimen, LSTM predice transición.
- Validado BTC/ETH direccional.
- **Requiere GPU para training** (cuello botella Railway CPU-only).
- Voz Zenith: pesos pre-entrenados a Salmos (no entrenar en prod).

### Por qué HMM (resumen)

1. **Ataca gap principal:** bot tiene macro gate rígido SP500, falta classifier mean-reversion vs momentum **por símbolo** (HMM resuelve BTC vs SOL individualmente).
2. **Costo cero / complejidad manejable:** repos open-source con OHLCV 5m/15m. Corre en CPU Railway.
3. **Integración nativa Salmos:** decisiones contextuales — "HMM detecta Rango → habilitar V3-REVERSAL; HMM detecta Trend → bloquear V3, habilitar momentum".

### Por qué descarto otros

- **LSTM:** GPU requerida + mantenimiento constante rompe operación liviana.
- **GARCH:** excelente para pronosticar picos volatilidad, pero NO clasifica régimen direccional.
- **K-means/DBSCAN:** ignoran secuencia temporal.
- **ADX/TSI:** demasiado simples para edge real (mejor como input a HMM).

## Prompt 5 — Gemini Flash 2.5 mejor uso

### Análisis por feature

**1. Function Calling — ⚠️ Riesgo costo/latencia**
- Salmos podría pedir datos en vivo (cambiar TF si ve duda en 4H).
- Múltiples turnos = más tokens = riesgo presupuesto $10/mes.
- Veredicto: posponer hasta tener budget mayor.

**2. Grounding con Google Search — Apocalipsis macro**
- Reemplaza web fetch FOMC PDFs + BlackRock manual.
- Costo extra por 1k consultas, sin límite estricto.
- Veredicto: implementar con cap diario (max 5 grounding/día).

**3. Context Caching — 🔥 VITAL**
- Sentinel Compact corre 4 voces por símbolo + 80% boilerplate repetido.
- Cargar system prompt + risk rules + state UNA vez → descuento significativo en consultas posteriores.
- Veredicto: **vital para budget protection** + permite más símbolos por mismo precio.

**4. Multi-image input — BitLobo upgrade**
- Gemini Flash 2.5 multimodal nativo.
- Enviar gráfica precio + mapa calor sectorial + VIX simultáneo.
- Emula "Panorama cross-asset" visualmente.
- Veredicto: upgrade BitLobo para análisis visual integrado.

**5. Structured Output (Pydantic) — 🔥 Quick win**
- Pydantic enforce tipos exactos: `score: float`, `recommendation: Enum[BUY/SELL/HOLD]`.
- Más robusto que JSON mode puro — evita parseo malformado + claves faltantes.
- Veredicto: adiós fallos silenciosos.

### Top 2 quick wins este mes

1. **Structured Output (Pydantic)** — cambio backend puro, $0 extra, latencia 0. Respuestas Cuadrilla Zenith 100% predecibles para SQLite + filtros dinámicos. **Cero errores de parseo malformado**.

2. **Context Caching** — cachear system prompt + risk rules + state. Sentinel corre 4 voces × N símbolos + 80% boilerplate → caching reduce consumo tokens significativamente. Libera presupuesto para Grounding más adelante o aumentar frecuencia Sentinel.

**Nota:** especificaciones técnicas exactas Gemini API + límites cuota deben verificarse en docs oficiales Google. Estos consejos son knowledge externo, no del corpus.

## Prompt 6 — Roadmap 90 días

### Mes 1 (Junio 2026) — Quick wins

| Semana | Item | Spec # | Tiempo | Costo |
|--------|------|--------|--------|-------|
| 1 | **Structured Output (Pydantic)** — migrar respuesta Cuadrilla Zenith de JSON mode a Pydantic. Elimina errores parsing. | Spec 005 | <1d | $0 |
| 2 | **Context Caching (Gemini)** — cachear system prompt base (80% texto repetido). Reduce consumo tokens ~25%. | Spec 006 | <1d | $0 |
| 3 | **Filtro Volatilidad (Funding Rates)** — HTTP simple a Binance. Bloquear V3 reversal si funding >10% anualizado. | Spec 007 | <1d | $0 |
| 4 | **Liquidity Sweeps** — detección máx/mín anteriores cruzada con Macro Gate. Commit deployable v1.1. | Spec 008 | <1d | $0 |

### Mes 2 (Julio) — Estructura

| Semana | Item | Spec # | Tiempo | Costo |
|--------|------|--------|--------|-------|
| 5 | **Clasificador HMM** (3 estados) — Hidden Markov Models OHLCV 5m/15m. Salmos detecta Tendencia/Rango/Squeeze. | Spec 009 | 2-3d | $0 |
| 6 | **Fair Value Gaps (FVG)** — lógica matemática velas de 3 pasos. Salmos usa como imanes precio en TP dinámico. | Spec 010 | 1-2d | $0 |
| 7 | **Whale Netflows (On-chain)** — Etherscan/BscScan API. Genesis rastrea transferencias >$1M hacia exchanges. | Spec 011 | 2d | $0 |
| 8 | **Multi-image Input (BitLobo)** — prompt multimodal Gemini con gráfica precio + mapa calor sectorial en una llamada. | Spec 012 | 1d | $0 |

### Mes 3 (Agosto) — Aprendizaje

| Semana | Item | Spec # | Tiempo | Costo |
|--------|------|--------|--------|-------|
| 9 | **Spot CVD Segmentado** — Binance Trades API. Clasificar flujo retail vs institucional. Cazar divergencias. | Spec 013 | 3-4d | $0 |
| 10 | **Social Sentiment Quant** — `praw` Reddit + `vaderSentiment`. Euforia/pánico retail → Exodo. | Spec 014 | 2-3d | $0 |
| 11 | **Grounding Google Search (Apocalipsis)** — capturar datos FOMC + crisis geopolíticas tiempo real. Cap diario queries. | Spec 015 | 1-2d | $0 |
| 12 | **Live Metrics Dashboard** — panel Flask consultando SQLite. WR + distribución por símbolo + performance por estrategia. | Spec 016 | 3d | $0 |

### Métricas de éxito del roadmap

1. **Cuantitativa:** WR consolidado **>55%** + Drawdown reducido. Especialmente V3/V4 — gracias a bloqueo automático de laterales (HMM) + picos Funding Rate.

2. **Cualitativa:** **<1h/semana** de babysitting Fernando. Eliminación total de excepciones JSON malformado (Pydantic) + decisiones más autónomas (Context Caching).

3. **De operación:** **Cero falsas alarmas** (falsos quiebres) operadas en 3 semanas consecutivas. Evidencia que Spot CVD + Genesis (Whale Netflows) filtran fakeouts del mercado.

### Costo total roadmap

**$0 nuevo software/data.** Mantiene budget IA Gemini Flash 2.5 $10/mes. 12 specs en 12 semanas, 1 por semana.

## Notas operador
<!-- Observaciones de Fernando al revisar -->
