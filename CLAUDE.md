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

### 8. Macro Context (Marzo 2026)

Contexto de mercado al momento del análisis — útil para calibrar bias:

- SPY, DJI, NASDAQ, RSP, IWM: todos con MACRO PHY bajista activo en mensual.
- Catalizador: aranceles Trump (tema Irán como disparador de ruptura multi-mensual).
- "Taco Trump": declaraciones de fin de mes para intentar rebotar el mercado → manipulación de vela mensual.
- Canal bajista activo en SP500. Resistencia corto plazo: 6457 → 6572 si perfora.
- Niveles de suelo macro SP500: 5650 y **5280** (confluencia 0.78 fib + cierre de gaps + tendencia LP).
- No distinguir aún si es corrección o bear market — operativamente igual en fase inicial.

### 9. Psicología de Trading (Trading Psychology Rules)

- No sentirse mal por tomar ganancias si el precio continúa a favor.
- No sentirse mal si salta el BE y había ganancia potencial.
- La decisión de BE vs parciales es personal — ambas son válidas si hay plan.
- Siempre habrá re-entradas. El mercado da segundas oportunidades.
- Jamás entrar "fuerte" o "apalancado" en operaciones rápidas de baja confianza.

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
