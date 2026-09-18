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

## Metodología PTS e Intel de mercado — índice (detalle en `docs/CLAUDE-REFERENCE.md`)

> Movido textual a `docs/CLAUDE-REFERENCE.md` el 2026-09-18. Es contexto de investigación con fecha,
> no regla: antes de citar un nivel o una fecha, abrirlo y fecharlo. Buscar: `grep -n -i <tema> docs/CLAUDE-REFERENCE.md`.

| Sección | Tema | grep |
|---|---|---|
| §A 1-7 | Jerarquía de TF, MACRO PHY, Fibonacci, tipos de operación, trade management, correlaciones, setup GDX | `grep -n -i "PHY\|fibonacci\|breakeven"` |
| §A 8-8c | Macro abril 2026 (post FOMC mar), PTS live, "dos operaciones" (9-abr) | `grep -n -i "8b\|8c\|FOMC"` |
| §B 8d-8m | Updates BitLobo/PTS abril-mayo 2026 (ruptura PHY, earnings, barridas, Lobo) | `grep -n -i "8h\|8j\|bitlobo"` |
| §B 8n | Snapshot web 20-24 jul 2026 (BTC gate, earnings Mag7, FOMC **vencido**) | `grep -n -i "8n\|snapshot"` |

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
- **Código**: `FOMC_CONTEXT` en `gemini_analyzer.py`, secciones 8–8c en `docs/CLAUDE-REFERENCE.md` §A
- **Señales activas**: XOM, MOO, GDX, SPY (ver `docs/CLAUDE-REFERENCE.md` §A 8c)
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

> Skills de cualquier repo (familias venom/carnage/build y cross-proyecto): sección `## Skills de todos los repos` del CLAUDE.md global.
<!-- SKILLS:END -->

---

---

## Lecciones de este repo (movidas de `angels/focus/_PATTERNS.md`, 2026-08-10)

> Incidentes concretos que ocurrieron **aquí**. Vivían en un índice global de 206 filas
> que nadie relee; el patrón general que comparten ya está en `angels/focus/_MECANISMOS.md`.
> Esto es lo específico del repo — lo que solo muerde en este stack.

- **Verificación delegada a background task (`sleep N && check`) se pierde en teardown de sesión → notificación "stopped/no record" y el estado queda DESCONOCIDO; el riesgo es afirmar el resultado como si el check hubiera corrido** <sub>2026-07-21</sub>
