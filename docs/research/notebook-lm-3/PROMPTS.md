# NotebookLM Prompts — Bot Performance Audit

> **Objetivo:** validar empíricamente las constantes y kill switches del bot scalp_bot/Zenith analizando 91 trades + 39 signal_episodes del periodo Mar-Apr 2026.
>
> **Setup NotebookLM:**
> 1. https://notebooklm.google.com → New notebook → "Bot Performance Audit"
> 2. Upload source: `performance-audit-corpus.md` (este folder)
> 3. **Opcional** — subir como source extra: `RESULTS.md` del Notebook 1 (PTS watchlist) para cross-reference signal episodes con la watchlist PTS recomendada.
> 4. Correr los prompts en orden, pegar outputs en `RESULTS.md`.

---

## Prompt 1 — Auditoría de kill switches actuales

```
El bot tiene varios kill switches activos en config.py:
- TAO_TRADING_ENABLED = False (TAO LONG bloqueado)
- TAO_SHORT_ENABLED = False (TAO SHORT bloqueado)
- V1_LONG_ENABLED = False
- V1_SHORT_ENABLED = False
- V5_ENABLED = False
- SWING_BLOCKLIST = ["TAO", "ZEC"]
- V4_BLOCKLIST = ["ETH", "ZEC"]
- SHORT_BLOCKED_IN_VERDE_BULL = True

Valida cada kill switch contra los datos del corpus:

| Kill switch | Trades afectados | WR antes del kill | Justificado? | Hipótesis adicional |

Reglas:
- Si el WR es <20% (significativamente abajo del breakeven incluyendo costos), el kill switch ESTÁ justificado.
- Si el WR es >35%, podría ser candidato a reactivar con condiciones.
- Para TAO LONG, validar el 3.1% WR (1/32 trades) — confirma o sugiere si fue ruido del periodo.
- Para SHORT en general (no solo cripto), validar el 8.3% WR (2/24 trades).

Termina con una recomendación: ¿algún kill switch debe REMOVERSE? ¿algún sin kill switch DEBE matarse?
```

---

## Prompt 2 — Paradoja conf_score

```
En el corpus se ve un patrón contra-intuitivo en conf_score:

| Score | Trades | WR% |
|-------|--------|-----|
| 0 | 2 | 50% |
| 3 | 1 | 0% |
| 4 | 81 | 19.8% |
| 5 | 7 | 0% |

El score 5 (MAYOR confluencia, supuestamente más conviction) tiene 0% WR.
El score 0 (menor confluencia) tiene 50% (muestra pequeña).

Hipótesis a investigar:
1. ¿El score 5 es exclusivamente SHORT en mercado bull? (correlación direction + score)
2. ¿El score 5 son trades de TAO/ZEC durante ventana de manipulación?
3. ¿Existe un sesgo de overfitting — el conf_score se sobre-pondera con indicadores correlacionados que no aportan edge real?

Diagnóstico:
- Identifica las 7 operaciones con score=5 — ¿qué tienen en común (símbolo, dirección, hora, RSI, macro_bias)?
- Identifica las 2 con score=0 — ¿anomalías?
- Sugiere si MIN_CONFLUENCE_SCORE = 5 debería REDUCIRSE (más alertas) o eliminarse, o cambiar la fórmula.
```

---

## Prompt 3 — Análisis de huérfanas (signal_episodes outcome=None)

```
De 39 signal_episodes, 31 (79.5%) tienen outcome = None. Spec 002 implementó yfinance fallback en check_pending_outcomes pero no llenó las pre-existentes.

Para las 31 huérfanas:
1. Agrupar por source (STOCK / BITLOBO / CRYPTO).
2. Estimar cuántas se cerrarán como WIN/LOSS si se ejecuta el yfinance fallback en producción.
3. ¿Hay alguna fila huérfana con entry_price NULL? Esas son irrecuperables — sugerir limpiar.
4. ¿Cuál sería el impacto en el WR overall si se llenan?

Termina con un script SQL conceptual que:
- Marca STALE las huérfanas >14 días sin outcome
- Sugiere fórmula para auto-fill outcome usando precios yfinance vs tp1_price / sl_price

NOTA: el bot YA tiene este código (Spec 002), solo necesita correr sobre las pre-existentes. Verificar.
```

---

## Prompt 4 — Direction bias (LONG vs SHORT en bull market)

```
| Tipo | Trades | WON | LOST | WR% |
|------|--------|-----|------|-----|
| LONG | 67 | 15 | 52 | 22.4% |
| SHORT | 24 | 2 | 22 | 8.3% |

El bot tiene SHORT_BLOCKED_IN_VERDE_BULL = True (Spec 001).
Periodo de los trades: Mar 30 - Apr 22, 2026. Macro: post-FOMC Mar 17-18, MACRO PHY bajista activo en mensual.

Pregunta investigativa:
- ¿Cuándo se abrieron los SHORTS? ¿Antes o después de los ganadores de PTS (XLC/XLF/MAGS/SPY) reportados en sección 8e del corpus PTS?
- ¿Cuáles son los 24 SHORTS por símbolo + RSI entry? ¿Eran SHORTS de TAO/ZEC en pico falso, o de algún índice/equity?
- LONG 22.4% WR en periodo con macro bajista — ¿bot apostó against trend?

Recomendación:
- ¿Mantener SHORT_BLOCKED_IN_VERDE_BULL o relajarlo cuando entremos a NARANJA_BEAR?
- ¿Hay símbolos donde SHORT funciona y otros donde no?
```

---

## Prompt 5 — Cross-reference con PTS watchlist

> **Opcional:** subir RESULTS.md del Notebook 1 como source adicional.

```
Considerando ambos corpus (Bot Performance + PTS Watchlist):

1. Símbolos donde el bot OPERÓ y PTS recomienda ACTIVE/PENDING: ¿el bot tuvo ganancias?
2. Símbolos donde PTS recomienda SUPPRESSED (IONQ, RGTI) — ¿el bot los operó alguna vez en el periodo? Si sí, ¿qué WR?
3. Símbolos donde PTS recomienda LONG defensivos (XOM, MOO, GDX, XLE, etc.) — ¿el bot los operó?
4. Símbolos donde el bot tuvo loops de pérdidas (TAO, ZEC) — ¿PTS los menciona alguna vez?

Termina con: ¿el bot está alineado con el universo PTS o opera símbolos huérfanos? Sugerir ajustes a STOCK_WATCHLIST.
```

---

## Prompt 6 — Plan de acción consolidado

```
Basado en los 5 prompts anteriores, construye un plan de acción priorizado para mejorar el WR del bot de 18.7% hacia >30%:

| Prioridad | Acción | Constante config.py / función afectada | Impacto esperado WR | Riesgo |

Reglas:
- P0: cambios reversibles + low risk (kill switches, thresholds).
- P1: cambios de lógica (cambiar fórmula confluence, agregar filtros).
- P2: cambios estructurales (refactor strategies.py).

Tope: 5 acciones P0, 3 P1, 2 P2.

Termina con un "dry-run mental": si TODAS las acciones P0 se aplican, ¿cuál sería el WR estimado de los 91 trades?
```

---

## Después de correr los prompts

Pegar outputs en `RESULTS.md` (template en el folder). Avisar a Claude: "listo Notebook 3, pegué resultados". Yo integro findings a:
- `config.py` — ajustar kill switches / thresholds según prompts 1+2
- Spec 005 — si hay filtros sugeridos por prompts 4+5
- `_LEARNING_LOG.md` — capturar aprendizajes del análisis
