# CLAUDE.md — Scalp Bot / Zenith Trading Suite

## Contexto del Proyecto

Bot de alertas de trading (Python/Flask) enfocado en cripto (BTC, ETH, TAO) con análisis técnico, integración con Gemini AI, y ejecución en Binance. Genera alertas con confluencia técnica múltiple (RSI, BB, EMA 200, Elliott Waves).

Archivos clave:
- `scalp_alert_bot.py` — lógica principal de alertas y loop principal (~1280 líneas)
- `telegram_commands.py` — dispatcher de comandos Telegram (extraído de scalp_alert_bot)
- `indicators.py` — cálculo de indicadores técnicos
- `gemini_analyzer.py` — análisis institucional con IA (Gemini + Claude)
- `trading_executor.py` — ejecución de órdenes en Binance
- `app.py` — servidor Flask / dashboard web
- `social_analyzer.py` — análisis de sentimiento social
- `ai_budget.py` — control de presupuesto de APIs de IA (máx $10/mes)
- `tracker.py` — base de datos SQLite de trades
- `config.py` — thresholds y configuración centralizada
- `docs/STRATEGY_RULES.md` — reglas operativas del bot

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
