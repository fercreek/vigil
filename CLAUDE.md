# CLAUDE.md — Scalp Bot / Zenith Trading Suite

## Meta-contexto: Cortex Consejo

Este proyecto vive bajo el marco operativo personal de Fernando documentado en `~/Documents/context/CLAUDE.md` sección 11 y en el plugin `~/.claude/plugins/cortex-consejo/`. Para decisiones estratégicas del bot (agregar sector, cambiar thresholds, abrir nueva cuenta, matar feature), usar `/consejo [decisión]` antes de ejecutar. Cuadrilla Zenith en `gemini_analyzer.py` es la **prueba validada** del patrón multi-voz que inspiró el plugin.

Axiomas que aplican también al bot:
- **Sabiduría > instinto** — el bot ya implementa esto con filtros (no tomar señal solo por RSI; requiere confluencia).
- **Su suerte no está donde usted trabaja** (frase ancla Odi Sa) — si TAO lleva 0% win rate, validar si seguir ahí es el esfuerzo correcto.
- **Hacer negocio solo** (Ojuani Tanshela) — ejecutar con cuenta propia, no partnerships de trading.

---

## Contexto del Proyecto

Bot de alertas de trading (Python/Flask) enfocado en cripto (BTC, ETH, TAO) con análisis técnico, integración con Gemini AI, y ejecución en Binance. Genera alertas con confluencia técnica múltiple (RSI, BB, EMA 200, Elliott Waves).

**⚠️ Deploy: Railway NO auto-deploya desde GitHub.** Push a `origin/main` solo mueve el repo. Deploy = `railway up` manual + verificar con `railway deployment list` (timestamp posterior al push). Nunca afirmar "ya está en prod" sin ese artefacto.

Archivos clave:
- `scalp_alert_bot.py` — lógica principal de alertas y loop principal (~1280 líneas)
- `telegram_commands.py` — dispatcher de comandos Telegram (extraído de scalp_alert_bot)
- `indicators.py` — cálculo de indicadores técnicos
- `gemini_analyzer.py` — análisis institucional con IA (Gemini + Claude)
- `trading_executor.py` — ejecución de órdenes en Binance
- `app.py` — servidor Flask / dashboard web
- `social_analyzer.py` — análisis de sentimiento social
- `ai_budget.py` — control de presupuesto de APIs de IA (máx $10/mes)
- `tracker.py` — base de datos SQLite de trades + tabla `intel_outcomes` (A/B framework Spec 022)
- `config.py` — thresholds y configuración centralizada
- `voice_compactor.py` — compacta output Cuadrilla Zenith para Telegram (Sentinel compact + `intel_compact_line`)
- `strategies.py` — todas las strategies V1/V2/V3/V4/SWING con gates, boosts, intel injection
- `docs/STRATEGY_RULES.md` — reglas operativas del bot
- `docs/SPEC_WIRE_AUDIT.md` — estado de cada spec: wired/logged/dormant (actualizar cuando cambien wires)

**Módulos intel (Specs 009-023, sesión 2026-05-26):**
- `regime_hmm.py` — Spec 009 · HMM 3-state (STRONG_TREND/RANGE/VOLATILE_SQUEEZE). Gate V3 en STRONG_TREND. Cache TTL 15min. Requiere `hmmlearn`.
- `regime_transitions.py` — Spec 002.5 · state machine SP500 (VERDE_BULL/AMARILLA/NARANJA). Detecta EXPLOSIVE_CORRECTION + BARRIDA_OPPORTUNITY. Persiste en `data/macro_state.json`.
- `onchain.py` — Spec 010 · whale netflows Etherscan/BscScan. Inflow=BEARISH, outflow=BULLISH. Requiere `ETHERSCAN_API_KEY`.
- `cvd_segmented.py` — Spec 012 · CVD por bucket tamaño (retail/<$1k, mid, whale/>$100k). Divergencia whale vs retail predice tops/bottoms.
- `social_quant.py` — Spec 013 · sentimiento Reddit+Google Trends (VADER, cache 30min). Requiere `REDDIT_CLIENT_ID/SECRET/USER_AGENT`.
- `grounded_search.py` — Spec 014 · Gemini Flash 2.5 Grounding para contexto macro real (FOMC, geo). Cap `GROUNDED_SEARCH_DAILY_CAP=5` queries/día.
- `options_oi.py` — Spec 023.6 · OI call/put ratio via yfinance para stocks. Ratio ≥2.0 = CALL_HEAVY.
- `models/sentinel.py` — Pydantic v2 `SentinelResponse` para `get_sentinel_report_compact`.
- `models/panorama.py` — Pydantic v2 `PanoramaPersonaResponse` para `get_hourly_panorama`.

---

## Reglas de Tamaño de Archivos

**Límite recomendado: 600 líneas por archivo Python.**

Cuando un archivo supera ~800 líneas, extraer la sección más coherente a un nuevo módulo:

| Archivo grande | Qué extraer | Destino sugerido |
|----------------|-------------|-----------------|
| `scalp_alert_bot.py` > 1000L | Comandos Telegram | `telegram_commands.py` |
| `scalp_alert_bot.py` > 1000L | Lógica de estrategias | `strategies.py` |
| `gemini_analyzer.py` > 800L | Funciones de agentes | `agent_panel.py` |
| `indicators.py` > 800L | Indicadores avanzados | `indicators_advanced.py` |

**Reglas para extraer módulos sin romper funcionalidad:**
1. El módulo nuevo importa sus propias dependencias directamente (`tracker`, `gemini_analyzer`, etc.)
2. Si necesita funciones del módulo original, usar **lazy import dentro de la función** para evitar circularidad:
   ```python
   def mi_funcion():
       from scalp_alert_bot import send_telegram, safe_html  # lazy, no circular
       ...
   ```
3. El módulo original reemplaza la función por un delegado de 1 línea:
   ```python
   def check_user_queries(prices):
       import telegram_commands
       telegram_commands.check_user_queries(prices)
   ```
4. Verificar siempre con `python -m py_compile archivo.py` antes de reiniciar.

---

## Metodología PTS — Insights para el Algoritmo

Fuente: Análisis de Pro Trading Skills (PTS), 31 de marzo 2026.
Aplicar estos principios para mejorar filtros de señales y lógica de gestión de operaciones.

### 1. Jerarquía de Marcos Temporales (Timeframe Hierarchy)

> Los marcos temporales superiores tienen autoridad sobre los inferiores.

- El gráfico **mensual/semanal manda** sobre el gráfico de 4H o 1H.
- Un rebote que parece "suelo" en 1H puede ser simplemente ruido dentro de un canal bajista mensual.
- **Regla para el bot**: antes de emitir señal long en TF corto, verificar que el bias del TF superior no sea bajista fuerte.

### 2. Patrón MACRO PHY (Head & Shoulders Macro)

El patrón más relevante para detectar cambios de tendencia a gran escala:

- **PHY Bajista** (Head & Shoulders distribucion): señal de continuación bajista. Rebotes son re-entradas cortas.
- **PHY Alcista** (Head & Shoulders inverso): señal de reversión alcista.
- Cuando un MACRO PHY está activo, los rebotes a la zona del hombro derecho / neckline son oportunidades de entrada en la dirección del patrón.
- Un rango lateral prolongado (6+ meses) antes de la ruptura implica **mayor extensión** del movimiento posterior.

### 3. Niveles de Fibonacci como Confluencia

Niveles clave a monitorear para targets y soporte/resistencia:

| Nivel Fib | Rol |
|-----------|-----|
| 0.23 | Primera resistencia/soporte tras el impulso |
| 0.38 | Target intermedio (6160 en SP500 como ejemplo) |
| 0.78 | Nivel de suelo macro con alta confluencia (cierre de gaps + tendencia LP) |
| 1.27 | Target de extensión cuando no alcanza 1.61 |
| 1.61 | Target de extensión estándar |

### 4. Tipos de Operación

| Tipo | Descripción | Gestión |
|------|-------------|---------|
| **Operación Rápida** | Corto plazo, más volátil, menor confianza | Posición pequeña, BE agresivo |
| **Operación Swing** | Mediano plazo, mayor convicción | Posición normal, dejar correr |

- Degradar una operación de swing a rápida cuando las condiciones macro cambian o la confianza baja.
- En operaciones rápidas: máximo 1% de riesgo por operación, posición mínima.

### 5. Gestión de Operaciones Abiertas (Trade Management)

Reglas de gestión cuando el mercado intenta rebote contra posición:

1. **Opción A — BE (Breakeven)**: mover SL al punto de entrada. No se pierde nada, se espera continuación.
2. **Opción B — Tomar parciales**: cerrar 50-66% de la posición en ganancia, dejar el resto en BE.
3. **Regla del equilibrio**: con 3 operaciones abiertas → cerrar 2, dejar 1. Con 4 → cerrar 2, dejar 2.
4. Nadie se hace pobre por tomar ganancias parciales. Siempre habrá re-entradas.
5. El BE es válido si el trader prioriza buscar mayor extensión — pero debe asumir la posibilidad de que salte.

### 6. Correlaciones de Activos

- **DXY vs ORO**: correlación inversa. DXY sube → presión bajista en oro.
- **ORO vs GDX/GLD/SLV**: GDX (Gold Miners ETF) como proxy más económico para operar oro.
- Cuando DXY retrocede + oro rebota desde PHY alcista → setup alcista rápido en GDX.

### 7. Setup Ejemplo — GDX (31 marzo 2026)

Operación alcista rápida documentada como referencia de estructura:

```
Activo:  GDX (Gold Miners ETF)
Tipo:    Alcista Rápida (corto plazo, baja convicción macro)
Entrada: 92.78
Stop:    82.16
BE:      mover SL a entrada cuando precio alcance 97
Target:  102 - 109
Tamaño:  1 acción por cada $1,000 en cuenta
Riesgo:  -1% por $1,000 en cuenta
Options: Buy Call 17-Jul-2026 Strike 95
         Riesgo aprox: -$450 | Potencial: +$620 a +$1,100
Contexto: Rebote de corto plazo. DXY retrocede, oro rebota desde PHY.
          NO es operación de largo plazo. Posición pequeña siempre.
```

### 8. Macro Context (Abril 2026 — Post FOMC Mar 17-18)

Contexto actualizado con datos del FOMC Minutes de marzo 2026:

**Política Monetaria:**
- Tasa actual: **3.50%-3.75%** (mantenida, voto 11-1). Miran disintió queriendo recorte.
- No hay recortes esperados hasta diciembre 2026. **30% probabilidad de SUBIDA de tasas**.
- Balance sheet: QT terminado, ahora Reserve Management Purchases (RMPs).
- Próxima reunión FOMC: **April 28-29, 2026** (bot suprime señales 24h antes).

**Inflación:**
- Core PCE: **3.0-3.1%** (objetivo 2% — lejos).
- Petróleo +50% por conflicto Middle East → boost inflacionario near-term.
- Tariffs siguen empujando precios de bienes core al alza.
- Housing services desacelerando (presión bajista parcial).

**Empleo:**
- Unemployment: **4.4%**, estable pero vulnerable a shocks.
- Firmas retrasando contrataciones por incertidumbre + anticipación de AI.
- Riesgos a la baja elevados — labor market vulnerable en entorno de low hiring.

**Geopolítica:**
- Conflicto Middle East = principal driver de incertidumbre global.
- USD fortalecido como safe-haven (US = net energy exporter).
- ECB, BoC, SNB ahora esperados a SUBIR tasas.
- Private credit funds con redemptions (exposure a AI disruption en software).

**Equities:**
- SPY, DJI, NASDAQ, RSP, IWM: MACRO PHY bajista activo en mensual (sin cambios).
- Equities -5% en el periodo. Software sector golpeado por AI disruption concerns.
- Canal bajista activo en SP500. Suelo macro: 5650 y **5280** (0.78 fib + gaps).

**Riesgo Stagflation:**
- Inflación persistente + empleo debilitándose = riesgo stagflation implícito.
- Bot usa `RATE_BIAS = "HAWKISH_HOLD"` y `OIL_INFLATION_THRESHOLD = 85.0`.

### 8b. PTS Live Analysis (Abril 2026)

Insights del live stream de Pro Trading Skills (mentores del sistema):

**SP500 — Régimen Bear Market Rally:**
- Rebote actual (6300→6780) es short-covering, NO compra institucional.
- Patrón histórico: 2022 y 2008 — bounce vertical → colapso posterior.
- Resistencia: 6800 (rechazo actual), 6950 (invalidación mensual del bear case).
- Soporte/Targets: 6675 (trigger short), 6323 (swing low), 6000 (macro floor).

**Oil — Zona de Peligro Inflacionario:**
- Oil > $90 = inflación sticky, sin recortes de tasas posibles.
- Oil < $76 = riesgo inflacionario disminuye.
- CPI esperado Apr 10: consenso 3.4% vs previo 2.4% — salto masivo.
- Si CPI rompe 4.0% → trigger de SUBIDA de tasas (catalizador extremo bearish).

**Gold — Consolidación:**
- Soporte: $4,100 (aguantó). Resistencia: $5,000-5,200.
- Gold correlacionando con SP500 (inusual) → señal de liquidación risk-off.
- Fase lateral tipo 2021, no esperan nuevos máximos near-term.

**Bitcoin — Lateral:**
- Breakout trigger: romper $74,000 con convicción + DXY debilitándose.
- MACD semanal en territorio negativo = señal no confiable (falso positivo en 2022).
- Sin setup accionable, paciencia requerida.

**GDX Update:**
- En target (~100-102). Mover SL a breakeven o tomar parciales.
- Gold debilitándose = hold defensivo, no nueva entrada.

**Reglas PTS Reforzadas:**
- Nunca entrar short en el tope del bounce — esperar confirmación de rechazo.
- Timeframe mensual invalida señales diarias/4H.
- Bounces en bear market son re-entradas short, no reversiones.

### 8c. PTS Update — "Dos Operaciones a Trabajar" (9 Abril 2026)

Reporte de Daniel Marin publicado el 9 de abril de 2026 a las 11:22.

**SP500 — ZR confirmada, esperando rechazo o ruptura:**

| Nivel | Valor | Rol |
|-------|-------|-----|
| Resistencia superior ZR | 6,858.73 | Techo de la zona de resistencia |
| Resistencia inferior ZR | 6,741.79 | Base de la zona de resistencia (precio actual ~6,772) |
| Soporte 1 | 6,679.30 | Primera banda de soporte inferior |
| Soporte 2 | 6,608.37 | Segunda banda de soporte |
| Swing low reciente | 6,175.30 | Suelo tras la caída de marzo/abril |

- **Escenario bearish (más probable):** SP500 rechaza la ZR → operaciones SHORT en SPY. Nueva ola bajista inicia.
- **Escenario bullish (menos probable):** Rompe la ZR → longs en META, HOOD, ASTS, RKLB (sólo acciones explosivas que hayan corregido).
- Plazo de resolución: **2-6 días** de rango antes de ruptura o rechazo.
- Bot debe **suprimir señales agresivas** mientras SP500 está dentro de la ZR (6,741–6,858).

**Operación 1 — XOM (ExxonMobil) — DEFENSIVA SWING:**

```
Dirección:  LONG
Entrada:    162.49
Stop:       149.60
BE:         mover SL a entrada cuando precio alcance 176
Targets:    185 / 205 / 227
Riesgo:     -1% GR
Acciones:   1 por cada $1,000 en cuenta
Options:    BUY CALL 18 Sep 2026 Strike 165
            Riesgo aprox: -$580 por contrato
Tipo:       Defensiva (sector energía, correlación inversa al mercado tech)
```

**Operación 2 — MOO (VanEck Agribusiness ETF) — DEFENSIVA SWING:**

```
Dirección:  LONG
Entrada:    87.64
Stop:       83.39
BE:         mover SL a entrada cuando precio alcance 90
Targets:    95 / 98 / 109
Riesgo:     -1% GR
Acciones:   3 por cada $1,000 en cuenta
Options:    BUY CALL 21 Ago 2026 Strike 88
            Riesgo aprox: -$200 por contrato
Tipo:       Defensiva (sector agrícola, descorrelacionado de tech/equities)
```

**GDX — Cerrar parciales:**
- Target alcanzado ~96 (muy cerca). Gold debilitándose.
- Acción: tomar ganancias en 96, mover SL a BE, no nueva entrada.

**En monitoreo para operaciones bajistas:** SPY, IWM, TSLA, XLK.

**Implicación para el bot:**
- `DEFENSIVE_SECTORS = ["XOM", "MOO", "GDX"]` — no filtrar con bias bajista de equities.
- SP500 en ZR = zona de indecisión → reducir tamaño de posición en cripto si hay correlación con equities.
- Vigilar ruptura de 6,858 (bullish) o rechazo desde 6,741 (bearish trigger).

---

### 9. Psicología de Trading (Trading Psychology Rules)

- No sentirse mal por tomar ganancias si el precio continúa a favor.
- No sentirse mal si salta el BE y había ganancia potencial.
- La decisión de BE vs parciales es personal — ambas son válidas si hay plan.
- Siempre habrá re-entradas. El mercado da segundas oportunidades.
- Jamás entrar "fuerte" o "apalancado" en operaciones rápidas de baja confianza.

---

## Fuentes de Intel de Mercado

### PTS (Pro Trading Skills) — Contexto Macro/Institucional

Fuente: mentores de Pro Trading Skills. Análisis publicados en `protradingskills.com/analysis/`.

- **Metodología**: PHY patterns (Head & Shoulders macro), jerarquía de timeframes, FOMC, correlaciones DXY/Gold/Oil
- **Operaciones**: tienen entry, SL, BE y target definidos. Tipo SWING o RAPIDA.
- **Código**: `FOMC_CONTEXT` en `gemini_analyzer.py`, secciones 8–8c en este CLAUDE.md
- **Señales activas**: XOM, MOO, GDX, SPY (ver sección 8c)
- **Agente IA**: Cuadrilla Zenith (Genesis, Exodo, Salmos, Apocalipsis) en `get_ai_consensus()`

### BitLobo (@BitloboTrading) — Análisis por Zonas Técnicas

Fuente: YouTube @BitloboTrading. Lives periódicos con análisis de acciones NYSE/NASDAQ y crypto.

- **Metodología**: zonas de color. 🟢 ZONA VERDE = soporte/acumulación/entrada. 🔴 ZONA ROJA = resistencia/target.
  - Entry: cuando el precio toca o entra a la zona verde
  - Stop Loss: por debajo del piso de la zona verde
  - Target: zona roja (precio de salida)
  - Si el precio está entre zonas: no hay setup claro, esperar
- **Código**: `bitlobo_agent.py` — analiza imágenes de gráficas via Gemini Vision, mantiene memoria diaria
- **Señales activas**: CRCL (4H), NKE (semanal), WEN (semanal, largo plazo)
- **Feed de gráficas**: enviar foto por Telegram con caption `/bitlobo SYMBOL TF` → BitLobo analiza y responde
- **Consulta sin imagen**: `/bitlobo SYMBOL` → opinión basada en niveles del watchlist
- **Consenso**: BitLobo aparece como línea 🐺 al final de cada debate Zenith

### 8d. BitLobo Update — "Ideas del Live" (9 Abril 2026)

Señales presentadas por BitLobo en su live stream del 9 de abril de 2026.

**CRCL (Circle Internet Group) — 4H:**
```
Dirección:      LONG
Zona verde:     60.75 – 83.53  (entrada / soporte)
Zona roja:      145.67 – 174.51 (targets)
Precio actual:  ~88.26 (encima de zona verde, vigilar pullback)
Stop Loss:      por debajo de 60.75
Break Even:     ~105
Tipo:           Fintech/crypto-adjacent. Especulativo.
```

**NKE (Nike) — Semanal:**
```
Dirección:  LONG
Niveles:    PENDIENTE — confirmar en próximo live
Tipo:       Swing semanal largo plazo
```

**WEN (Wendy's Company) — Semanal (Largo Plazo):**
```
Dirección:      LONG
Zona verde:     4.30 – 7.06  (acumulación / entrada)
Precio actual:  ~7.09 (tocando el techo de la zona verde)
Stop Loss:      por debajo de 4.30
Target:         PENDIENTE — no definido en el live, largo plazo
Tipo:           Acumulación defensiva de largo plazo. Sector restaurantes.
Nota:           Precio YA en la zona. Candidato a entrada gradual.
```

**Implicación para el bot:**
- Señales BitLobo = no filtrar con bias macro bajista (son defensivas/largo plazo)
- Bot puede vigilar CRCL en `stock_watchdog()` — alerta si precio entra zona 60.75–83.53
- WEN: monitorear semanalmente, no intradía

---

### 8e. PTS Update — "Una operación rápida y una swing" (13 Abril 2026)

**Contexto SP500:**
- SP500 testeando parte alta de ZR en 0.78. VIX testeando mínimo del viernes.
- Escenario bajista (más probable): rechazo ZR → nueva oleada bajista
- Escenario alcista (menos probable): ruptura ZR → máximos 7,000 (MACRO PHY)
- **Si SP500 rompe ZR al alza → enviar operaciones alcistas en acciones explosivas**
- Operaciones bajistas anteriores cerradas en ganancia (SPY, petroleras, MAGS, XLC, XLF)

**Operación 1 — RKLB (Rocket Lab) — RÁPIDA:**
```
Dirección:  LONG
Entrada:    74.90
Stop:       63.35
BE:         83 (mover SL a entrada)
Targets:    91 / 100
Riesgo:     -1.1% GR
Acciones:   1 por $1,000
Options:    BUY CALL 17-Jul-2026 Strike 80 | Riesgo: -$560 | Pot: $900-$1,500
Tipo:       Operación rápida en sector aeroespacial/launch
```

**Operación 2 — TSLA — BAJISTA SWING-POSICIONAL:**
```
Dirección:  SHORT
Entrada:    335.65
Stop:       359.87
BE:         320 (mover SL a entrada)
Targets:    302 / 276 / 217
Riesgo:     -2.4% GR
Acciones:   1 por $2,000
Options:    BUY PUT 21-Ago-2026 Strike 330 | Riesgo: -$880 | Pot: $1,400-$8,100
Tipo:       La más débil de las 7 Magníficas. Activar SÓLO cuando alcance entrada.
```

---

### 8f. PTS Update — "Dos operaciones a corto plazo" (14 Abril 2026)

**Contexto SP500:**
- SP500 rompió la ZR al alza → avanzando hacia 7,000 y MACRO PHY.
- Mercado celebra promesas de Trump, ignora macroeconomía.
- Oil >$90 por semanas → Fed no puede bajar tasas. Rebote ≈ short-covering, no institucional.
- **GDX en ganancias ~100: mover stop a 96.** Gold debilitándose, no nueva entrada.
- SPY bajista y TSLA SHORT: en espera, no tocar hasta activación.
- Próximo posible: IREN, MSFT para rebotes rápidos si SP500 sigue arriba.

**Operación 1 — XBI (Biotech ETF) — DEFENSIVA SWING:**
```
Dirección:  LONG
Entrada:    133 – 136 (ENTRADA ACTIVA DESDE YA)
Stop:       119.09
BE:         143
Targets:    150 / 174
Riesgo:     -1.4% GR
Acciones:   1 por $1,000
Options:    BUY CALL 18-Sep-2026 Strike 135 | Riesgo: -$600 | Pot: $1,100-$3,000
Tipo:       Defensiva. No cayó con SP500. Alto potencial de crecimiento.
```

**Operación 2 — HOOD (Robinhood) — RÁPIDA:**
```
Dirección:  LONG
Entrada:    85.97
Stop:       65.35
BE:         97.84
Targets:    120 / 134
Riesgo:     -2% GR
Acciones:   1 por $1,000
Options:    BUY CALL 21-Ago-2026 Strike 90 | Riesgo: -$795 | Pot: $2,400-$3,200
Tipo:       HOOD cae desde Octubre, puede despertar. Potencial interesante.
```

---

### 8g. PTS Update — "Tres operaciones en sectores interesantes" (15 Abril 2026)

**Contexto SP500:**
- SP500 intenta romper MACRO PHY. Escenario más equilibrado (no hay probabilidades superiores bajistas).
- **Niveles de vigilancia:** SP500 pierde 6,832 → prepararse para short. SP500 pierde 6,728 → entrar SHORT (SPY ~673).
- Bot suprime señales agresivas mientras SP500 no pierda 6,832.
- Sectores cuánticos y nuclear despertando: si consolidan 2-3 días → enviar operaciones alcistas.

**Bitcoin:** Sigue en rango pre-caída SP500 y post-rebote. Breakout trigger: superar $74,000 con convicción + DXY débil. Si rompe: operación BTC + ETH + SOL.

**Operación 1 — COIN (Coinbase) — SWING ALCISTA:**
```
Dirección:  LONG
Entrada:    200.93
Stop:       160.32
BE:         254
Targets:    286 / 328 / 382
Riesgo:     -2% GR
Acciones:   1 por $2,000
Options:    BUY CALL 18-Sep-2026 Strike 220 | Riesgo: -$1,650 | Pot: $5,800-$14,000
Tipo:       Mejor proxy crypto. El activo con más ganancia en 2025.
```

**Operación 2 — MP (MP Materials) — SWING ALCISTA:**
```
Dirección:  LONG
Entrada:    63.28
Stop:       48.11
BE:         73
Targets:    79 / 89
Riesgo:     -1.5% GR
Acciones:   1 por $1,000
Options:    BUY CALL 18-Sep-2026 Strike 70 | Riesgo: -$590 | Pot: $950-$1,600
Tipo:       Rare earth materials. Enorme rango de consolidación.
```

**Operación 3 — SOFI (SoFi Technologies) — SWING ALCISTA:**
```
Dirección:  LONG
Entrada:    19.29
Stop:       15.60
BE:         21
Targets:    25 / 28
Riesgo:     -1.2% GR
Acciones:   3 por $1,000
Options:    BUY CALL 18-Sep-2026 Strike 22 | Riesgo: -$150 | Pot: $350-$550
Tipo:       Posible formación de suelo tras fuertes caídas. Sector fintech.
```

**Signals activas en bot (watchlist actualizada 15-Abr-2026):**
```
RKLB   LONG  74.90   | XBI  LONG 133.0  | HOOD  LONG  85.97
COIN   LONG 200.93   | MP   LONG  63.28  | SOFI  LONG  19.29
TSLA  SHORT 335.65   | GDX  LONG  92.78 (stop 96)
SPY   SHORT watch    | IREN  pendiente  | MSFT  pendiente
Cuánticos: pendiente 2-3 días consolidación
Nuclear:   pendiente próximo reporte
```

**Regla bot:** `DEFENSIVE_SECTORS = ["XOM", "MOO", "GDX", "XBI", "COIN", "RKLB", "HOOD", "MP", "SOFI"]` — no filtrar con bias bajista de equities. Monitorear SP500 en 6,832 y 6,728 para activar short SPY.

---

### 8h. PTS Update — Ruptura MACRO PHY + crypto breakout (21-23 Abril 2026)

Reportes consecutivos de Daniel Marin que actualizan régimen post-ruptura del MACRO PHY al alza en SP500.

**Régimen SP500 (zonas activas — usar como gate macro en bot):**

| Zona | Rango | Régimen | Acción bot |
|------|-------|---------|-----------|
| 🟢 VERDE | >7,000 (consolidando 7,100-7,181) | Toros gobiernan, post-ruptura MACRO PHY | NO suprimir longs. Habilitar señales long en watchlist |
| 🟡 AMARILLA | 6,800-7,000 | Reingreso a MACRO PHY → zona de decisión / posible falsa ruptura | Reducir tamaño 50%, requiere confluencia extra para long |
| 🟠 NARANJA-ROJA | <6,800 | Falsa ruptura confirmada → escenario bajista activo (paralelo a 2025/2008) | Activar SHORT SPY + buscar shorts en watchlist débil |

Resistencia clave: **7,181** (techo consolidación). Niveles trigger: pierde **7,000** = empieza alarma. Pierde **6,728** = SHORT activado.

**Catalizadores macro Apr 21-23:**
- Tregua Trump-Irán vence Mié 22 PM. Si "botas en tierra" Iran → catalizador bajista fuerte. Si solo retórica → TACO (Trump Always Chickens Out) bullish.
- Kevin Warsh confirmó al Congreso que NO será títere de Trump. Sin recortes 2026 salvo recesión. Si inflación >3% → SUBIDA tasas posible.
- Volatilidad intradía SP500 = 60-80 puntos por sesión. Bot debe usar posiciones pequeñas + paciencia.

**Reporte 21 Abr — UUUU + IREN (sectores nuclear/data centers):**

```
UUUU (Energy Fuels — Uranium) — SWING ALCISTA
  Entry: 22.77 | Stop: 19.60 | BE: 25
  Targets: 28 / 31 / 35 | GR: -1% (3 acciones / $1,000)
  Options: BUY CALL 16-Oct-2026 Strike 22 (ITM) | Riesgo: -$200 | Pot: $400-$950
  Sector: Nuclear / uranium
```

```
IREN (Iris Energy — Bitcoin mining + data centers) — SWING ALCISTA
  Entry: 52.38 | Stop: 42.74 | BE: 59
  Targets: 67 / 77 / 89 | GR: -1% (1 acción / $1,000)
  Options: BUY CALL 18-Sep-2026 Strike 55 | Riesgo: -$530 | Pot: $950-$2,600
  Sector: Crypto mining / energy data centers
```

**GDX cerrado** ~$96 con ganancias (entrada $92.78). Mover SL del watchlist a CLOSED.

**Reporte 22 Abr — BTC + ETH (crypto breakout activado):**

BTC formando 2do máximo más alto sobre rango 60k-76k. USDT.D al borde de ruptura bajista. Setup difiere de falsa ruptura previa (este sostuvo $73,800). Probabilidad ahora favorece ruptura real al alza.

```
BTC (Bitcoin) — SWING ALCISTA
  Entry: 79,917 | Stop: 69,919 | BE: 85,000
  Targets: 93,000 / 101,000 | GR: -2.4%
  Exposición: 20% spot equivalente del capital total
  Trigger: ruptura sostenida >$79.9k con USDT.D rompiendo rango bajista
```

```
ETH (Ethereum) — SWING ALCISTA
  Entry: 2,520 | Stop: 2,024 | BE: 2,967
  Targets: 3,367 / 3,751 / 4,277 | GR: -2%
  Exposición: 10% spot equivalente del capital total
```

**Pipeline post-activación BTC/ETH:** BNB, SOL, IBIT (options), ETHA (options). RIOT como crypto-stock.

**Reporte 23 Abr — XLE (sector energía descorrelacionado):**

XLE (Energy Select Sector SPDR) iniciando potencial alcista con phy alcista + ruptura 0.38 fib. Petroleras van a su propio ritmo en 2026 — no correlacionan con dirección del SP500.

```
XLE (Energy ETF) — SWING ALCISTA
  Entry: 58.31 | Stop: 53.06 | BE: 61
  Targets: 63 / 66 / 69 | GR: -1% (2 acciones / $1,000)
  Options: BUY CALL 30-Sep-2026 Strike 60 | Riesgo: -$220 | Pot: $300-$700
  Característica: descorrelacionado del SP500 → operable en cualquier zona
```

**Sectores en monitoreo** (esperando consolidación para entry):
- IONQ — buscar entry zona 36-38 (PHY alcista). NO chase de subida vertical 25→50.
- OKLO — esperar lateralización ~$76. Target potencial $200-250. Sector nuclear / SMRs.
- SMR — alternativa a UUUU dentro de QF (UUUU no está en QF list).
- RDDT — esperar earnings próxima semana antes de entrada.
- BABA — posible suelo en formación, monitorear próximos días.

**Estado consolidado watchlist activa (23 Abr):**

| Símbolo | Status | Observación |
|---------|--------|-------------|
| SOFI | LONG abierto | Sobre zona entrada, lateral |
| MP | LONG abierto | Positivo, una de las más fuertes |
| COIN | LONG abierto | Volátil. +6% el 22, monitorear |
| HOOD | LONG abierto | Resistente, en positivo |
| XBI | LONG abierto | Ligeramente positivo |
| RKLB | LONG abierto | T1 alcanzado, mover SL a BE |
| GDX | CERRADO | +ganancias en $96 (entry $92.78) |
| ASTS | Pending | No activado aún |
| UUUU | Pending | Entry 22.77 |
| IREN | Pending | Entry 52.38 |
| XLE | Pending | Entry 58.31 |
| BTC | Pending | Entry 79,917 (crypto breakout pending) |
| ETH | Pending | Entry 2,520 |
| TSLA | SHORT pending | Entry 335.65 (pendiente desde 13 Abr — solo activar si SP500 cae a naranja) |
| SPY | SHORT watch | Trigger si SP500 pierde 6,728 |

**Implicaciones para bot:**

1. **Expandir DEFENSIVE_SECTORS:** `["XOM", "MOO", "GDX", "XBI", "COIN", "RKLB", "HOOD", "MP", "SOFI", "UUUU", "IREN", "XLE", "OKLO", "SMR", "IONQ", "RDDT"]`
2. **Crypto LONG triggers nuevos en `config.py`:**
   ```python
   BTC_LONG_TRIGGER = 79917  # Entry PTS Apr 22
   BTC_STOP = 69919
   BTC_BE = 85000
   ETH_LONG_TRIGGER = 2520
   ETH_STOP = 2024
   ETH_BE = 2967
   ```
3. **Macro gate dinámico** — leer SP500 actual y aplicar régimen:
   - SP500 >7,000 → `MACRO_REGIME = "VERDE_BULL"` → no filtrar longs
   - SP500 6,800-7,000 → `MACRO_REGIME = "AMARILLA_INDECISA"` → reducir tamaño 50%
   - SP500 <6,800 → `MACRO_REGIME = "NARANJA_BEAR"` → activar SHORT SPY + filtrar longs débiles
4. **Volatilidad intradía elevada** — bot debe respetar trailing stops más amplios (60-80 pts SP500 por sesión = ~1% intradía noise).
5. **Cuadrilla Zenith** — actualizar `FOMC_CONTEXT` en `gemini_analyzer.py` para reflejar régimen post-ruptura MACRO PHY (aún hawkish hold, pero gráficamente alcista en zona verde).

---

### 8i. PTS Update — Post-Earnings Terremoto + Reajuste Watchlist (8 Mayo 2026)

Mensaje de Daniel Marin post-earnings season (semana del 5-8 mayo 2026). Mercado se rehace, coberturas funcionaron bien. RKLB +30% (+72% en options), llegó T1. Siguiente semana reentradas para MP e IREN.

**Resumen de resultados earnings:**
- **RKLB**: +26-30% 🚀 T1 alcanzado, sin reentrada aún
- **COIN**: cobertura pasó de $1,100 → $1,700 (+$500), se recupera — válida reentrar
- **CRWV**: cobertura funcionó, volvió a zona BE — nuevo PHY alcista
- **UUUU**: subió fuerte post-earnings, llegó a BE y se devolvió — nueva entrada
- **SOFI**: muy débil post-earnings, barrida — reentrada en 16.99
- **IONQ**: quienes salieron pre-earnings ganaron — nueva entrada 50.05 (alza post-earnings)
- **IREN**: quienes vendieron en QF ganaron, options siguen en ganancia — stop ganancia 57, no reentrada externa aún
- **MP**: subió y se devolvió con fuerza — pueden tomar en 68, esperar análisis

**Watchlist actualizado (08-May-2026):**

| Símbolo | Status | Entry | Stop | BE | Target 1 | Target 2 |
|---------|--------|-------|------|----|----------|----------|
| HOOD | ✅ válida | 70-85 | 65.35 | 97.84 | 120 | 134 |
| SOFI | 🔄 reentrada | 16.99 | 12.94 | 21 | 25 | 28 |
| COIN | ✅ reentrar YA | 178-200 | 160.32 | 254 | 286 | 328 |
| UUUU | 🔄 nueva | 22.72 | 18.50 | 25 | 28 | 31 |
| IONQ | 🔄 nueva | 50.05 | 35.44 | 62 | 72 | 85 |
| XLE | ✅ válida | 58.31 | 53.06 | 61 | 63 | 69 |
| CRWV | 🆕 nueva | 121.82 | 91.79 | 140 | 160 | 187 |
| OKLO | ⚠️ earnings mar | 73.91 | 50.26 | 84 | 101 | 137 |
| SMR | 🆕 nueva | 12.67 | 9.54 | 15 | 17 | 22 |
| RKLB | 🎯 T1 pasado | 74.90 | 91.0 (stop ganancia) | — | 100 | — |
| IREN | ⏳ esperar | — | 57 (stop ganancia interno) | — | — | — |
| MP | ⏳ esperar | — | — | — | — | — |

**Nuevas operaciones detalladas:**

```
CRWV (CoreWeave) — SWING ALCISTA
  Entry: 121.82 | Stop: 91.79 | BE: 140
  Targets: 160 / 187 | GR: -3% (1 acción/$1k)
  Options: BUY CALL 16-Oct-2026 Strike 125 | Riesgo: -$1,200 | Pot: $2,600-5,000
  Empresa sólida, PHY alcista activo post-barrida earnings
```

```
OKLO (nuclear SMR) — SWING ALCISTA
  Entry: 73.91 | Stop: 50.26 | BE: 84
  Targets: 101 / 137 / 161 | GR: -2.3% (1 acción/$1k)
  Options: BUY CALL 20-Nov-2026 Strike 75 | Riesgo: -$1,250 | Pot: $1,800-6,500
  ⚠️ EARNINGS MARTES: QF vender lun/mar, options reciben cobertura martes
```

```
SMR (small modular reactor) — SWING ALCISTA
  Entry: 12.67 | Stop: 9.54 | BE: 15
  Targets: 17 / 19 / 22 | GR: -1.2% (4 acciones/$1k)
  Options: BUY CALL 20-Nov-2026 Strike 13 | Riesgo: -$200 | Pot: $220-800
  Pasó earnings. Sector nuclear despertando (junto con UUUU, OKLO)
```

**Implicaciones para el bot:**
- `DEFENSIVE_SECTORS` expandir: `["CRWV", "OKLO", "SMR", "UUUU", "IONQ"]` — no filtrar con bias bajista
- OKLO: ⚠️ tiene earnings martes — bot debe suprimir señales 24h antes/después (igual que FOMC logic)
- Sector nuclear theme: UUUU + OKLO + SMR convergiendo — correlación alta, no acumular los 3 en misma sesión
- SOFI débil — si bot detecta precio en 16.99 zona, alert válido para reentrada

---

### 8j. PTS Updates — Volatilidad de Barridas + Recuperación (19-22 Mayo 2026)

Dos reportes de Daniel Marin durante semana post-NVDA earnings. Mercado tuvo barridas excesivas en sectores nuclear/quantum/AI-infra (martes 19-May), suelo establecido, recuperación en curso.

**Régimen SP500 confirmado VERDE_BULL:**

- SP500 lateral a 2% de máximos (~7100-7200). Muy arriba de soporte 7000.
- VIX bajo, rompiendo a la baja, target $13. **VIX < 22 + SP500 > 7000 = barridas son OPORTUNIDAD de entrada, no panic.**
- IWM testeó parte baja de su rango — clave para estabilidad de small caps. Si sostiene rango → reanudación alcista.
- Acciones de calidad: ruta a máximos históricos confirmada.

**Sector Nuclear bajo barrida (suelo May 20):**

- OKLO + SMR + UUUU formaron PHY con ZR. Sostuvieron mínimos del martes → recuperación inminente.
- Daniel: "el camino con estas acciones es tortuoso pero es porque tienen potencial gigantesco". OKLO licencia NRC para reactor en Eilson AFB Alaska = catalizador estructural. Valoración "madura" estimada: $250-350.
- **Implicación bot:** sector nuclear correlacionado → no acumular UUUU+OKLO+SMR misma sesión. Usar `SECTOR_CLUSTERS["nuclear"]` con `MAX_PER_CLUSTER = 2`.

**Sector AI-Infraestructura (ex-mineras BTC):**

- CRWV + IREN + CORZ + CIFR + CLSK convergiendo en mismo tema.
- **CLSK destaca:** +9% sesión 19-May, OM alcista formándose, ruptura 0.38 fib → target $23 luego $32. NO operativa formal aún, monitoreo.
- **Implicación bot:** `SECTOR_CLUSTERS["ai_infra"]` con MAX 2 por sesión.

**Sector Quantum despertando:**

- IONQ: entry $50.05 activó fuerte, "potencial súper trade".
- **RGTI nueva:** entry $19 dio "enormes ganancias", PTS dice "de los trades más grandes del año".
- Cluster correlacionado: `SECTOR_CLUSTERS["quantum"] = ["IONQ", "RGTI"]`.

**Defensivos activados o entrando:**

- JNJ: activó May-22, "defensiva con fuerza alcista de semiconductores".
- KO + CL: zona de entrada, válidos sector defensivo.
- MO: arriba entry, va muy bien.
- CVX: petrolera sólida, sigue subiendo. XOM tocó BE → reentrada próxima.
- VAL: retrocedió, potencial alcista intacto.

**Próximamente PTS (esperando entry formal):**

- USAR: phy alcista en zona atractiva, potencial triplicar precio.
- ARM, ALAB: cerca de área de descubrimiento de precio.
- HOOD: cambio de contratos antes fin de mes (options rollover).

**Estado watchlist consolidado (22-May-2026):**

| Status | Símbolos |
|--------|----------|
| ✅ Ganancia / progreso | IONQ, RGTI, CORZ, ASTS, MO, JNJ, XLE, CVX |
| ⏳ En zona / lateral | COIN, SOFI, HOOD, XBI |
| 🔄 Suelo establecido (recovery) | OKLO, SMR, UUUU, IREN, CRWV |
| ⏰ Entry pendiente próximo reporte | UUUU reentrada, XOM reentrada, MP reentrada, CIFR, KO, CL |
| 👀 Monitoreo (no operativa formal) | CLSK, USAR, ARM, ALAB |

**Implicaciones código bot:**

1. **VIX gate dorment activo** (`config.py` agregado):
   ```python
   VIX_DORMANT_THRESHOLD = 22.0  # VIX < 22 + SP500 > 7000 → barridas = oportunidad
   ```
   En `is_macro_bullish_for_long()` usar: `if VIX < 22 and SP500 > 7000: regime = "VERDE_BULL_DORMANT"` → no filtrar longs en barridas.

2. **DEFENSIVE_SECTORS expandido** (`config.py`):
   ```python
   DEFENSIVE_SECTORS = [..., "RGTI", "CORZ", "CIFR", "JNJ", "KO", "CL", "MO", "CVX", "VAL", "ASTS"]
   ```
   No filtrar con bias bajista de equities.

3. **SECTOR_CLUSTERS nuevo** (`config.py`):
   ```python
   SECTOR_CLUSTERS = {
       "nuclear":   ["UUUU", "OKLO", "SMR"],
       "ai_infra":  ["CRWV", "IREN", "CORZ", "CIFR", "CLSK"],
       "quantum":   ["IONQ", "RGTI"],
       "crypto_proxy": ["COIN", "MSTR", "IREN", "CORZ", "CIFR", "CLSK"],
       "petroleras": ["XOM", "CVX", "XLE", "VAL"],
       "defensivos": ["JNJ", "KO", "CL", "MO", "MOO"],
   }
   MAX_PER_CLUSTER = 2
   ```
   Bot debe consultar antes de abrir 3ra posición en mismo cluster — limita riesgo de colapso sectorial.

4. **Macro regime gate** (constantes nuevas):
   ```python
   SP500_VERDE_THRESHOLD = 7000.0    # > 7000 = BULL, no suprimir longs
   SP500_NARANJA_THRESHOLD = 6800.0  # < 6800 = BEAR risk, filtrar longs débiles
   SP500_NARANJA_TRIGGER_SHORT = 6728.0  # SHORT SPY activado
   ```

5. **NVDA earnings supresión** — patrón confirmado: bot debe extender lógica FOMC para earnings críticos (NVDA, OKLO próx martes). Lista propuesta: `EARNINGS_SUPPRESS_24H = ["NVDA", "OKLO", "TSLA", "MSFT"]`.

---

### 8k. PTS Update — Análisis Rápido Semana 26-30 May 2026 (Daniel Marin, 25-May 23:00)

Apertura de semana. SP500 sube en futuros Asia/Europa el lunes, gap alcista probable. Mensaje corto pero con dirección clara para esta semana.

**Régimen SP500 confirmado VERDE_BULL (sin cambios):**

- SP500 muy arriba de 7000 (soporte clave). Mientras se mantenga >7000 = entorno alcista.
- Mínimos semana pasada = piso defendible. Si sostiene → camino al alza con paciencia.
- Barridas SIEMPRE pueden ocurrir → son oportunidades de entrada, no panic.

**Plan semanal PTS — sectores a vigilar lunes-viernes:**

| Sector | Símbolos | Status | Acción bot |
|--------|----------|--------|-----------|
| Crypto proxy | COIN | Vigilar movimientos | Alertas long activas, entry $178-200 sigue válido |
| Nuclear | UUUU, OKLO, SMR | Aún en zona entrada | Alertas long válidas, NO sobreextender (max 2/cluster) |
| AI Infra | CRWV, CORZ, CIFR | Próximos movimientos alcistas | **Prioridad alta esta semana** — alertas long aggressive |
| Petroleras | XOM, CVX, XLE, VAL | Estables, suben despacio | Alertas long defensivas, no urgentes |
| Defensivas | JNJ, KO, CL, MO, MOO | Estables, suben despacio | Alertas long válidas, baja prioridad |
| Cuánticas | IONQ, RGTI | **SOBREEXTENDIDAS** | ⛔ NO emitir reentry signals hasta corrección |
| Aeroespacial | ASTS | Ya tuvo movimiento la semana pasada | Hold ganadores, no nueva entrada |

**Catalizadores macro:**
- Bonos 20Y: posible máximo en rendimiento → retrocesos = beneficio para equities. Vigilar TLT/TBT.
- Jueves: 2da clase Taller Psicología Trading (no afecta bot).
- Junio: SEC levanta restricción day trading options → Taller Day Trading PTS próximamente.

**Implicaciones inmediatas para el bot esta semana:**

1. **`QUANTUM_SUPPRESSED_UNTIL = "2026-06-01"`** — IONQ + RGTI sobreextendidas. Bot debe suprimir reentry signals hasta corrección. Solo alertar si precio retrocede ≥10% desde máximo.

2. **Prioridad alta AI Infra** — agregar `PRIORITY_BOOST_CLUSTER = "ai_infra"` para esta semana. Bot debe:
   - Reducir threshold confluencia para CRWV/CORZ/CIFR (alertar antes que default)
   - Permitir hasta 3 posiciones en cluster ai_infra (vs 2 default) si SP500 > 7000

3. **Barridas = oportunidad** — bot NO debe filtrar longs en spikes bajistas intraday mientras SP500 > 7000 y VIX < 22. Patrón ya implementado (8j) — confirmar que está activo.

4. **Petroleras como rebalance** — XOM en BE, CVX subiendo. Si bot detecta entry zone reentry XOM o pullback CVX → alertar como "DEFENSIVA_ESTABLE" tag (no agresiva).

5. **Watchlist priorizada esta semana (orden de monitoreo bot):**
   ```python
   WEEK_PRIORITY_25MAY = [
       # ALTA — vigilancia activa Daniel Marin
       "COIN", "CRWV", "CORZ", "CIFR",
       # MEDIA — nucleares zona entrada
       "UUUU", "OKLO", "SMR",
       # BAJA — defensivas estables
       "XOM", "CVX", "XLE", "VAL", "JNJ", "KO", "CL", "MO",
       # SUPRIMIDAS
       # "IONQ", "RGTI" — sobreextendidas, esperar corrección
   ]
   ```

6. **Sin nuevos entries formales** — reporte fue "análisis rápido", PTS repasa instrucciones existentes esta semana. Bot mantiene watchlist 8i+8j vigente, prioridad según tabla arriba.

**Plan operativo bot 26-30 May:**
- Lunes apertura: confirmar SP500 > 7000 y gap alcista. Si confirma → habilitar todas alertas long del cluster ai_infra + crypto_proxy + nuclear.
- Si SP500 pierde mínimos semana pasada (vigilar nivel exacto) → reducir tamaño 50% en todos los longs.
- Si SP500 pierde 7000 → MACRO_REGIME = "AMARILLA_INDECISA" → suprimir nuevas longs.

---

### 8l. Análisis Lobo + PTS Context (27 Mayo 2026)

**Fuente:** YouTube Live LoboCrypto + contexto PTS semana 26-30 May (sección 8k)

**BTC setup activo (Lobo):**
- Weekly: bajista, bulltrap fase 26-27. Flip bullish solo con cierre daily > $79k.
- Key support: $73,800 (100MA + canal + zona onchain). Si pierde → $71k → $69k → $64k.
- Sospecha short squeeze: volumen bajando en caída + todo el mundo tiene el canal bajista → market maker puede limpiar cortos primero.
- Opciones viernes: $7B, max pain $75k, put $70k, call $80k.
- Dos largos activos: entry $74,692, stop $73k, TP $78,500.

**ETH:** Tom Lee (Bitmine) acumulando $5.4M ETH. Target superciclo $9k-12k en 2029-30.

**USDT.D:** Cayendo → favorece altcoins. "Acumular spot cuando llegue a zona clave inferior."

**SP500:** Doble techo ("McDonald's") en máximos históricos + Nasdaq pullback → riesgo correlación con BTC.

**Implicaciones para ZEC / TAO / TON (monitor manual):**

| Escenario | ZEC/TAO/TON |
|-----------|-------------|
| BTC sostiene $73,800 + USDT.D sigue cayendo | ✅ Long válido — alts rebotan |
| Short squeeze BTC hacia $78-79k | ✅ Acelera alts |
| SP500 corrige + BTC pierde $73k | 🔴 Invalidación — esperar $68-64k |
| USDT.D rebota desde zona clave | ⚠️ Pausa en alts — reducir exposición |

**Niveles de invalidación del setup LONG ZEC:**
- SL: ZEC pierde $520 (correlado con BTC perdiendo $73k)
- Si BTC cierra daily > $79k → señal de confirmación adicional para ZEC

**PTS article** (protradingskills.com/analysis/analisis-de-mercado-riesgos-y-oportunidades/) — requiere auth, no accesible. Ver sección 8k para el plan semanal vigente (COIN, CRWV, CORZ, nucleares prioritarios esta semana).

---

---

### 8m. PTS Update — "Análisis de Mercado: Riesgos y Oportunidades" (Daniel Marin, 27-May-2026 15:49)

**Macro SP500:**
- SP500 lateral sobre 7500. Soporte corto plazo: **7300** (lejos aún).
- RSP en máximos (amplitud positiva). Volatilidad intradiaria históricamente alta (acciones mueven 6%+ intraday).
- **Regla operativa**: posiciones pequeñas, paciencia, tolerancia a volatilidad extrema.

**Bitcoin — CRÍTICO:**
- Estuvo en $82k, perdiendo soporte **$76k** → borde de ruptura bajista.
- Confirmación bajista: pérdida del mínimo del sábado (mínimo: ~$73,800).
- **Recuperación requiere**: cierre daily > $76k en miércoles o jueves.
- **USDT.D al borde de ruptura alcista** → "últimas horas previas a decisión de mercado".
- SP500/NASDAQ/DOW/RUSSELL en máximos pero BTC no rebota → "debilidad extrema del crypto".

**Watchlist actualizado (27-May-2026) — por prioridad:**

| Prioridad | Sector | Símbolos | Status PTS |
|-----------|--------|----------|-----------|
| 🔥 Más alcista | AI Infra | IREN ($61), CORZ, CIFR, CRWV (>$94) | CORZ target $100 fin 2026 · IREN target $250+ LP |
| 🔥 Muy alcista | Cuántico | IONQ, RGTI | En BE, continúan a targets. No nueva entrada (esperar barrida) |
| ✅ Alcista | Nuclear | OKLO, SMR | Post-barrida, consolidando. OKLO: acuerdo META (catalizador) |
| ✅ Alcista | Tierras raras | MP | Activó entrada. USAR: pasó oportunidad — esperar barrida |
| 🔄 Suelo | Fintech | SOFI (>$17), HOOD (>$78) | Formando suelo. Trigger: romper esos niveles |
| 🔄 Barrida CP | Petroleras | CVX, VAL, OXY | Barrida a corto plazo, tendencia alcista intacta. XLE/XOM en BE |
| 🐢 Lento | Defensivos | JNJ, MO, CL, KO | Baja volatilidad, zona entrada. "Tortugas fuertes" |
| 🚀 Escapada | AI Infra | CLSK | No para de subir. No operar ahora — esperar retroceso. Target $30+ 2026, $60 2027 |
| ⚠️ Riesgo | Crypto stock | COIN | ZR última barrera. Stop/tolerancia: **$169-172**. Si pierde → reduce exposición crypto |
| 🔴 Débil | Crypto | BTC, alts | Peor sector. USDT.D puede romper al alza = presión en alts |

**Catalizadores destacados:**
- OKLO: acuerdo comercial META + sector nuclear muy fuerte
- CLSK: AI infra + minería BTC, "cohete que va a niveles muy altos"
- **SEC Junio 2026**: levanta restricción day trading options → habilitado comprar/vender contratos el mismo día

**Implicaciones para el bot (ZEC/TAO/TON):**
1. USDT.D en borde de ruptura alcista → si rompe: presión bajista en altcoins
2. BTC pierde $76k → confirma bajista → ZEC/TON/TAO invalidación
3. BTC vuelve > $76k (cierre daily) → setup long alts válido otra vez
4. Crypto es "el peor sector" según PTS → keep ZEC monitor conservador, no agresivo
5. COIN stop $172 → si COIN cae es indicador de crypto debilidad sistémica

**Updates config.py necesarios:**
```python
BTC_CRITICAL_SUPPORT = 76000   # 8m: pérdida = confirmación bajista
COIN_STOP_TOLERANCE  = 172     # 8m: última barrera COIN
USDT_D_RUPTURA_THRESHOLD = 4.0 # 8m: ruptura alcista USDT.D = presión alts
QUANTUM_SUPPRESSED_UNTIL = "2026-06-15"  # 8m: IONQ/RGTI en BE, esperar barrida para nueva entrada
WEEK_PRIORITY_HIGH = ["IREN", "CORZ", "CIFR", "CRWV"]  # 8m: AI infra es la prioridad
```

---

### 8n. Snapshot Web — Semana 20-24 Jul 2026 (verificado 21-Jul)

**Fuente:** búsqueda web 21-Jul-2026 (Yahoo Finance, Bloomberg, Fortune, CoinDesk). No es reporte PTS — snapshot de estado real del mercado.

**Crypto — bajista confirmado, capitulación en curso:**
- **BTC ~$64,900.** El escenario bajista de 8m se CUMPLIÓ: perdió $76k, $73.8k y el stop PTS de $69.9k. -$53k vs hace un año. Compradores de $75k-126k realizando pérdidas = no hay optimismo near-term. Contrarian: Standard Chartered mantiene target $100k fin de 2026.
- **ETH ~$1,826-1,937** (rango lateral). Muy debajo del entry PTS $2,520 y del stop $2,024 — operación stopeada hace tiempo.
- **SOL ~$78.** XRP debajo de $1.10 hacia $1.00. Estructura técnica de alts débil.
- **Flujos ETF:** BTC +$75.7M, ETH +$105.4M semana pasada — institucionales rotando a blue-chips, no a alts.

**Equities — VERDE_BULL intacto, semana de earnings:**
- **SP500 ~7,470** (BofA target 7,100 = -5%). Muy arriba de 7,000 → régimen VERDE_BULL sigue activo.
- **10Y Treasury 4.52%**, bajando tras datos de inflación más fríos. Import prices +0.3% Jun = inflación de bienes aún empuja.
- **⚠️ Earnings Mag7 arrancan MAÑANA:** TSLA + GOOGL reportan Mié 22-Jul after the bell (primeros Mag7 del ciclo). INTC, IBM, GM, AMD también esta semana. Consenso: EPS Mag7 +28% YoY — expectativa alta = riesgo de volatilidad si decepcionan.
- Asia subió liderada por chips; el mercado apuesta a que los megacaps sostienen el rally AI.

**Implicaciones para el bot (días siguientes):**
1. **Crypto proxies gate FUNCIONA:** BTC $64.9k < gate $74k (`CRYPTO_PROXY_BTC_GATE`) → COIN/IREN/CORZ/CIFR/CLSK correctamente filtrados. No abrir longs crypto hasta reclaim de $74k.
2. **$76k ya no es soporte, es resistencia** — actualizado comment en `config.py`. Reclaim de $69.9k → primera señal de vida; cierre daily >$74k → reactivar pipeline alts.
3. **TSLA/GOOGL earnings 22-Jul** agregados a `EARNINGS_CALENDAR` → supresión 24h antes/después activa. TSLA holdea 11,509 BTC con pérdidas no realizadas — su earnings puede mover crypto sentiment.
4. **FOMC actualizado:** próxima reunión **Jul 28-29** (`FOMC_NEXT_MEETING = "2026-07-28"`) → supresión de señales desde el lunes 27.
5. **Equities long OK, crypto long NO:** régimen divergente — SP500 VERDE_BULL pero crypto es el peor sector. `SHORT_BLOCKED_IN_VERDE_BULL` sigue aplicando para no shortear alts en squeeze; longs de alts requieren el reclaim de BTC.
6. **Semana de alta volatilidad esperada** (earnings + FOMC la que sigue) → tamaño reducido, no perseguir breakouts intraday.

---

## Cómo Aplicar Estos Insights al Algoritmo

### Filtros a Implementar

1. **Filtro de Bias Macro**: antes de emitir señal, verificar tendencia en TF 1D/1W. Si hay PHY bajista activo, suprimir señales long agresivas.
2. **Detección de PHY**: agregar lógica en `indicators.py` para identificar formaciones de Head & Shoulders en TF altos.
3. **Niveles Fibonacci automáticos**: calcular y marcar 0.23, 0.38, 0.78 desde últimos swing high/low significativos.
4. **Clasificación de operación**: etiquetar alertas como `RAPIDA` o `SWING` según confianza del contexto macro.
5. **Gestión dinámica de BE**: implementar lógica de mover SL a BE automáticamente cuando precio alcanza primer target parcial.
6. **Correlación DXY**: integrar feed de DXY para filtrar señales de oro/commodities.

### Reglas de Tamaño de Posición

- Operación normal: 1 unidad por $1,000 en cuenta
- Operación rápida (baja confianza): 0.5 unidades por $1,000 — máximo 1 contrato en options
- Nunca escalar en operaciones de baja convicción macro

---

## Reglas Operativas Existentes del Bot

Ver `docs/STRATEGY_RULES.md` para reglas completas. Resumen:

1. Filtro de Confluencia Extrema: RSI < 30 (Long) o > 70 (Short) + Bias Semanal de V2-AI
2. Validación de Sesión: entradas fuertes solo tras apertura de Londres (LND) o Nueva York (NY)
3. Análisis de Fallo: revisar 15m para detectar Stop Hunt en cada SL
4. Post-Mortem: Flash Report por cada alerta con probabilidad 1-10 basada en macro-tendencia

<!-- SKILLS:START (auto — editar en venom/registry/skills-by-project.yaml) -->
## Skills de este proyecto
> Auto-sync desde `venom/registry/skills-by-project.yaml` (venom = master). NO editar a mano.
> **Regla: antes de generar/ejecutar una tarea con skill aquí, proponerlo y preguntar '¿uso [skill]?' — no improvisar.**

### DEFAULT — skills propios de este repo (propón apenas la tarea aplica)
| Tarea | Skill |
|---|---|
| auditar el bot / revisar logs / algo falló | `@agent cortex-debugger` |
| snapshot del estado del bot | `@agent cortex-debugger` |
| watchlist | `@agent cortex-debugger` |
| intel macro de mercado | `@agent cortex-debugger` |
| operar / comandos del bot de Telegram | `tradebot-tg` |

### SUGERIDO — familias cross-proyecto (aplican en CUALQUIER repo según la tarea)
- **🧠 venom — analiza/juzga:** `venom-design` scorea calidad visual de un post/imagen (gate >=9 + pre-check objetivo) · `venom-leveling` nivel L1-L7 de un skill o L1-L5 de una marca + leaderboard · `venom-playbook` que sabe hacer el ecosistema con data real (capabilities) · `venom-priority` ordena prioridad de la colmena + sync _NEXT<->focus · `venom-image-advisor` que API de imagen usar (Flux/Ideogram/DALL-E) · `venom-freud` analisis psyche/arte (me veo en X, autoanalisis) · `venom-social` compara redes cross-marca FB+IG (entre marcas + entre redes) con data real, surface que funciona · `venom-meeting` analiza recap+transcript de una llamada (read.ai), extrae pendientes, separa dev (task board) vs negocio/cliente (venom)
- **🔪 carnage — rompe/QA/repara:** `carnage-kill` red-team: rompe un bot/feature/parser, emite break-list · `carnage-repair` arregla el break-list con fix minimo + test de regresion · `carnage-qa` QA visual rapido de un post/imagen (sin gate-block) · `carnage-ux-polish` audita + aplica fixes UX/visual de una landing web
- **🛠️ build — genera/cablea:** `build-post-templates` imagen de post brand-correct (16 plantillas, selector por tema) · `build-cc-post` imagen/post de marca Contreras Code · `build-sl-promo` contenido social de campania promo Studio Link (stories+feed+hero) · `build-help` copy de ayuda al usuario final (modal/tooltip/empty state, cero tecnico) · `build-components` biblioteca + estandarizacion de componentes UI de un repo · `build-tooltip` cablea tooltip Stimulus en formularios Studio Link · `build-chat` envia mensaje tono venom por WhatsApp o Telegram · `brand-batch` orquesta un batch de contenido social de una marca (discovery->generar->gate->preview), HASTA preview, no publica. Destilado del content-pipeline
- **🎯 focus — productividad:** `focus` gestor diario de prioridades (today.json) · `focus-hyper` bloquea en UNA tarea, guard anti-drift · `focus-tdah` modo comunicacion TDAH (corto, A/B/C, 1 pregunta) · `focus-supernova` retro + cierre de sesion (bien/mal/patron) + commit
- **🦇 batman/hydra — orquesta:** `batman` orquesta varias sesiones sobre UN repo (modo crunch/evento) · `hydra` derrame multi-modelo (Opus->Sonnet->Haiku) para abarcar mas
<!-- SKILLS:END -->
