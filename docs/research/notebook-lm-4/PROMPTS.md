# NotebookLM 4 — Estrategias a Implementar (Research)

> **Objetivo:** identificar estrategias probadas y técnicas avanzadas que se puedan SUMAR al bot scalp_bot/Zenith — sin duplicar lo que ya existe.
>
> **Setup NotebookLM:**
> 1. https://notebooklm.google.com → New notebook → "Trading Strategies Research"
> 2. **Source principal:** subir `bot-capabilities-corpus.md` (este folder)
> 3. **Sources externos vía "Discover"** (botón en NotebookLM):
>    - Buscar: "quantitative trading strategies retail crypto"
>    - Buscar: "smart money concepts SMC trading"
>    - Buscar: "AI agent trading strategy backtesting"
>    - Buscar: "options flow unusual activity bot"
>    - Buscar: "on-chain analysis bitcoin signals"
>    - Buscar: "market regime detection machine learning"
>    - Discover seleccionará 5-10 sources confiables.
> 4. Correr los 6 prompts en orden, pegar outputs en `RESULTS.md`.

---

## Prompt 1 — Top 5 estrategias factibles para el bot actual

```
Considerando el corpus "bot-capabilities-corpus.md" que describe lo que el bot YA tiene (Cuadrilla Zenith 4 voces Gemini, RSI/BB/EMA/ATR, MACRO PHY referencia, MTF parcial 4H, NinjA/SCALPER/SWING/V2/V3/V4/COMMODITY strategies, kill switches activos, $10/mes budget IA), identifica las 5 estrategias o capacidades NUEVAS más factibles de implementar.

Para cada una incluye:

| # | Estrategia | Qué aporta | Complejidad (1-5) | Costo extra mensual | WR esperado | Compatibilidad con Cuadrilla Zenith |

Reglas:
- Excluir lo que ya está en el corpus.
- "Factible" = se puede implementar en Python con APIs gratis o <$50/mes.
- Justificar cada WR esperado con cita a la fuente discover o conocimiento general.
- Compatibilidad = ¿se integra con las 4 voces o requiere nueva voz?

Termina con: tu top 1 candidato para empezar la próxima semana.
```

---

## Prompt 2 — Smart Money Concepts (SMC) — ¿implementable?

```
Smart Money Concepts (SMC) es una metodología popular en cripto y forex retail. Incluye:
- BOS (Break of Structure)
- CHoCH (Change of Character)
- Order Blocks (OB)
- Fair Value Gaps (FVG)
- Liquidity sweeps
- Mitigation

Analiza si SMC se puede implementar en el bot:

1. **Detección algorítmica:** ¿Hay implementación open-source en Python (TradingView Pine Script → Python)?
2. **Compatibility con Cuadrilla Zenith:** ¿podría ser una 5ta voz "Liquidez" o se mete en Salmos?
3. **Evidencia empírica:** ¿Hay backtests publicados? ¿WR realista en cripto?
4. **Critique:** ¿Es SMC realmente edge o es repackaging de support/resistance?

Termina con un veredicto: SI/NO/Híbrido (qué partes valen la pena) + estimación de tiempo de implementación.
```

---

## Prompt 3 — On-chain signals (BTC/ETH)

```
El bot opera BTC, ETH, SOL, ZEC, TAO y proxies (COIN, MSTR, IBIT, mineras). On-chain podría dar señales que precio/RSI no capturan.

Investiga qué señales on-chain son MÁS predictivas (no las que generan más buzz):

| Señal | Provider gratis | Provider paid | Trigger threshold | Lead/lag time vs precio |
| ----- | --------------- | ------------- | ----------------- | ----------------------- |

Top candidatos a investigar (NO te limites a estos):
- MVRV Z-Score (top/bottom global)
- NUPL (Net Unrealized Profit/Loss)
- Exchange netflows (BTC, ETH, USDT)
- Stablecoin supply (USDT + USDC + DAI)
- Whale wallet movements (>1000 BTC)
- Miner reserves
- Funding rates aggregated (perps)
- Open Interest delta

Para cada uno:
1. ¿Provider FREE existe vía API? (Glassnode community, CryptoQuant, CoinMetrics)
2. ¿Threshold accionable documentado en papers o tweets de quant?
3. ¿Como se enchufaría con Cuadrilla Zenith? (probable Genesis = institucional/whale).

Termina con: top 3 señales on-chain que sumar primero, con costo total mensual.
```

---

## Prompt 4 — Market regime detection (ML)

```
El bot tiene macro_regime hardcoded (VERDE_BULL/AMARILLA_INDECISA/NARANJA_BEAR) basado en SP500 + VIX thresholds. Pero internamente cada símbolo tiene su propio régimen (trend/range/volatile).

Investiga métodos de market regime detection:

1. **HMM (Hidden Markov Models):** ¿se usan en cripto? ¿Edge real o overfitting?
2. **Volatility clustering (GARCH):** ¿identifica vol regimes accionables?
3. **Trend strength indicators:** ADX clásico vs alternativas modernas (TSI, Choppiness Index).
4. **Clustering (K-means o DBSCAN):** ¿agrupa días/horas por régimen?
5. **Deep learning (LSTM):** ¿realmente vale la pena vs simple ATR ratio?

Para cada uno:
- ¿Open-source Python? (sklearn, hmmlearn, arch)
- ¿Backtest validado en cripto BTC/ETH?
- ¿Compute cost? (CPU o GPU?)
- ¿Integración con Cuadrilla Zenith? (probable Salmos para confluencia técnica regime-aware)

Termina con: ¿qué método sumarías al bot? ¿Por qué descartas los otros?
```

---

## Prompt 5 — Cómo aprovechar Gemini Flash 2.5 mejor

```
El bot usa Gemini Flash 2.5 para:
- Sentinel Compact (JSON 6 líneas con 4 voces)
- Panorama cross-asset
- Multi-symbol event detector
- Weekly bias per symbol
- BitLobo vision (imágenes de gráficas)

Gemini Flash 2.5 capabilities NO usadas:
- Function calling (tools)
- Code execution
- Grounding con Google Search
- Multimodal: video (no solo image)
- Context caching (descuento 25%)

Investiga:

1. **Function calling:** ¿podría el agente Salmos LLAMAR funciones del bot (get_ohlcv, get_indicators) directamente en lugar de recibirlas pre-calculadas? Ventaja: análisis más flexible. Riesgo: latencia + costo.

2. **Grounding con Google Search:** ¿podría Apocalipsis hacer queries reales de noticias macro (ej. "FOMC decision today") y traer contexto fresco? ¿Cuál es el límite de queries/día?

3. **Context caching:** los prompts del bot tienen ~80% de boilerplate igual. ¿Vale la pena cachear el system prompt para reducir costo 25%?

4. **Multi-image input:** ¿podría BitLobo analizar gráfica + chart de macro + ranking sectorial en UN solo prompt?

5. **Structured output (Pydantic):** ¿más robusto que JSON mode actual?

Top 2 cambios recomendados — quick wins de Gemini que sumar este mes.
```

---

## Prompt 6 — Plan implementación 90 días

```
Basado en los 5 prompts anteriores, construye un roadmap de 90 días:

### Mes 1 (Junio 2026) — Quick wins
| Semana | Item | Spec # | Tiempo estim | Costo |

### Mes 2 (Julio) — Estructura
| Semana | Item | Spec # | Tiempo estim | Costo |

### Mes 3 (Agosto) — Aprendizaje
| Semana | Item | Spec # | Tiempo estim | Costo |

Reglas:
- Quick wins primero (cambios <1 día, costo $0).
- Cada item linkeable a "Spec 005, 006, 007..." (continuar numeración existente).
- Tope: 12 items en 12 semanas, 1 por semana.
- Mes 1 termina con commit deployable.
- Mes 3 termina con un dashboard de métricas live por estrategia.

Termina con 3 métricas que indiquen "el roadmap está funcionando":
1. (cuantitativa, ej. WR > X%)
2. (cualitativa, ej. menos tiempo de Fernando en babysitting)
3. (de operación, ej. cero false alarms en N semanas)
```

---

## Después de correr

Pegar outputs en `RESULTS.md`. Avisar: "listo notebook 4, pegué resultados". Yo:
1. Cruzo findings con Spec 005 backlog actual.
2. Genero specs nuevos por cada quick win (P0).
3. Actualizo `_NEXT.md` con roadmap aceptado.
4. Sugerir si vale la pena instalar Anthropic SDK (Spec 006 candidato).
