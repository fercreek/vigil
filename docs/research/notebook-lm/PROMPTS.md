# NotebookLM Prompts — PTS Watchlist Deep Dive

> **Objetivo:** producir análisis consolidado de los reportes PTS de Daniel Marin (Apr–May 2026) para alinear el bot scalp_bot/Zenith con la semana del 26-30 May 2026.
>
> **Setup en NotebookLM:**
> 1. Ir a https://notebooklm.google.com
> 2. Crear notebook nuevo "PTS Watchlist Deep Dive"
> 3. Subir como source: `pts-watchlist-corpus.md` (ubicado en este mismo folder)
> 4. Opcional: agregar como fuentes extras los emails originales de Daniel Marin si los tienes (forward a tu inbox o screenshots)
> 5. Correr los prompts en orden. Pegar output de cada uno en `RESULTS.md` (template abajo).

---

## Prompt 1 — Tabla consolidada por símbolo

```
Construye una tabla por símbolo de TODA la watchlist PTS (cada acción/activo mencionado al menos una vez en los reportes 8c a 8k). Para cada símbolo incluye:

| Símbolo | Sector | Dirección (LONG/SHORT) | Entry vigente | Stop | BE | Target 1 | Target 2 | Última mención (sección) | Status actual (ACTIVE/CLOSED/PENDING/SUPPRESSED) | Notas relevantes (1 línea) |

Reglas:
- Si Daniel actualiza niveles en reporte posterior, usa los más recientes.
- Si el reporte explícitamente dice "cerrado" o "T1 alcanzado", marca CLOSED.
- Si dice "sobreextendido" o "esperar corrección", marca SUPPRESSED.
- Si nunca activó pero sigue válido, PENDING.
- Si está abierto y en progreso, ACTIVE.
- Si hay contradicción entre reportes, usa el más reciente y nota la contradicción en columna "Notas".

Ordena por: ACTIVE → PENDING → SUPPRESSED → CLOSED.
```

---

## Prompt 2 — Contradicciones y cambios de tono

```
Identifica TODAS las contradicciones o cambios de tono significativos entre reportes consecutivos de Daniel Marin. Por ejemplo:

- Símbolo X marcado como "bullish" en reporte A, después "esperar corrección" en reporte B.
- Régimen SP500 cambia de VERDE a AMARILLA y vuelve a VERDE.
- Stop loss movido hacia arriba sin explicación clara.
- Reentry sugerida después de barrida sin nuevos niveles.

Para cada contradicción:
1. Cita las dos secciones (ej: "8g vs 8i")
2. Resume qué dijo en cada una (1 línea cada)
3. Hipótesis: ¿qué cambió en el mercado para justificar el cambio?
4. Implicación para el bot: ¿debe ajustar algún flag o threshold?
```

---

## Prompt 3 — Sectores: convergencia y correlación

```
Agrupa todos los símbolos mencionados por sector / tema:

- Nuclear (UUUU, OKLO, SMR, etc.)
- AI Infrastructure (CRWV, IREN, CORZ, CIFR, CLSK)
- Quantum (IONQ, RGTI)
- Crypto proxy (COIN, MSTR, mining stocks)
- Petroleras (XOM, CVX, XLE, VAL)
- Defensivos (JNJ, KO, CL, MO, MOO)
- Otros sectores únicos (RKLB aeroespacial, HOOD fintech, SOFI fintech, etc.)

Por cada sector responde:
1. ¿Cuántas posiciones activas/pending hay simultáneamente?
2. ¿Daniel los recomienda con timing similar (correlación alta) o separados?
3. ¿Cuál es la posición LIDER del sector (la que Daniel menciona más, da más detalle, o cita como referencia)?
4. Para el bot: ¿es seguro abrir 2+ posiciones del mismo sector la misma semana, o hay riesgo de colapso correlacionado?

Termina con una recomendación: cuál `MAX_PER_CLUSTER` debería tener cada sector.
```

---

## Prompt 4 — Régimen macro: línea de tiempo

```
Construye una línea de tiempo del régimen SP500 según los reportes:

| Fecha | Sección | SP500 nivel | Régimen reportado | VIX | Trigger relevante |

Reglas:
- Una fila por reporte (8c, 8d, 8e, ... 8k).
- "Régimen reportado" = lo que Daniel dice cualitativamente (bull, bear, lateral, ZR, indeciso, etc.) traducido al régimen del bot (VERDE_BULL / AMARILLA_INDECISA / NARANJA_BEAR).
- "Trigger relevante" = qué nivel debe perder/romper para cambiar el régimen.

Después de la tabla:
1. Identifica los 2-3 puntos de inflexión más importantes (cambios de régimen confirmados).
2. ¿Cuál es el patrón visible? ¿Estamos en bear rally, recuperación, lateral?
3. Para la semana 26-30 May (reporte 8k): ¿qué señales debemos vigilar para detectar cambio de régimen antes que Daniel lo escriba?
```

---

## Prompt 5 — Operaciones cerradas: análisis de éxito

```
Lista todas las operaciones que se cerraron con ganancia según los reportes (T1 alcanzado, stop ganancia activado, "cerramos en X"):

| Símbolo | Entry | Exit aprox | % ganancia | Días en posición | Sector | Tipo (Rápida/Swing) |

Después responde:
1. ¿Cuál sector tuvo mayor % de ganadores?
2. ¿Cuál tipo (Rápida vs Swing) cerró más rápido en ganancia?
3. ¿Hay un patrón en los ganadores (entrada después de barrida, sector defensivo, etc.)?
4. Para el bot: ¿hay alguna característica común que pudiéramos usar como FILTRO para subir prioridad a alertas similares?
```

---

## Prompt 6 — Plan accionable semana 26-30 May

```
Basado en TODO el corpus, pero priorizando el reporte más reciente (8k del 25 May), construye un plan accionable día-por-día para la semana 26-30 May 2026:

| Día | Símbolos a vigilar | Niveles clave (entry/SL/TP) | Catalizadores macro | Acción del bot recomendada |

Reglas:
- Lunes 26: apertura. Confirmar SP500 > 7000 + gap alcista.
- Día con catalizador macro (FOMC, CPI, earnings de NVDA/OKLO/MSFT/TSLA) → marca como "🚨 SUPPRESS 24H".
- Si un símbolo es de WEEK_PRIORITY_HIGH (COIN, CRWV, CORZ, CIFR) → marca "🔥 ALTA".
- Si es nuclear o defensiva → marca prioridad media o baja según contexto.

Termina con:
1. Top 3 oportunidades de la semana (mayor probabilidad de activación).
2. Top 3 riesgos a vigilar (qué puede invalidar el plan).
3. Triggers de cambio de régimen (qué nivel perdido = cambio AMARILLA o NARANJA).
```

---

## Prompt 7 — Audio Overview (opcional)

> NotebookLM puede generar un audio podcast de los reportes (dos voces conversando ~10-15 min).

```
Genera un Audio Overview en español enfocado en:
1. Estado actual del mercado según PTS (mayo 2026).
2. Top oportunidades para la semana 26-30 May.
3. Riesgos macro (FOMC, CPI, oil, geopolítica).
4. Errores que evitar (sobreextensión, FOMO en cuánticas, ignorar contradicciones).

Tono: como dos traders experimentados platicando antes de la apertura del lunes.
```

> Útil para escuchar mientras Fernando hace ejercicio / commute domingo en la noche.

---

## Después de correr los prompts

Pegar los outputs en `RESULTS.md` (siguiente archivo) usando este template:

```markdown
# PTS Watchlist Deep Dive — Results

> Fecha de ejecución: YYYY-MM-DD
> NotebookLM URL: [pegar URL del notebook]

## Prompt 1 — Tabla consolidada
[pegar output]

## Prompt 2 — Contradicciones
[pegar output]

...
```

Luego avísame ("Listo, pegué resultados") y yo integro:
- Símbolos `ACTIVE/PENDING` no en `STOCK_WATCHLIST` → agregar.
- Símbolos `CLOSED` con stop ganancia → marcar CLOSED en watchlist.
- Símbolos `SUPPRESSED` → agregar a `QUANTUM_SUPPRESSED` o crear `SUPPRESSED_LIST`.
- Régimen actual → verificar `SP500_VERDE_THRESHOLD` y constantes macro.
- Plan accionable → seed para nuevas alertas + ajustes `WEEK_PRIORITY_*`.
