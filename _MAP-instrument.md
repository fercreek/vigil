# MAPA — Instrumento de medición de señales (Zenith)
> FOCUS-<pendiente> · caduca: **2026-09-20** · repo: `fercreek/vigil`
> Trazado 2026-08-21 con el skill `wayfinder`.

## Destino

Un instrumento que, ante cualquier regla de señal, responde en minutos y con denominador
explícito si tiene ventaja — y que emite ≤3 alertas/semana accionables a mano.

## Notas

- **Dominio:** señales de trading para operar a mano. El bot NO ejecuta.
- **Skills a consultar cada sesión:** `spec-forge` §Fase 2 (para los `grilling`), `nova`
  (medir antes de construir), `carnage-kill` antes de dar por buena una regla.
- **Preferencia fija:** ninguna cifra se publica sin su denominador pegado en la misma frase.
- ⚠️ **El repo es PÚBLICO.** Lo que se escriba en las resoluciones queda a la vista.

## Decisiones hasta ahora

- **Qué cuenta como acierto**: llegó a +1R antes de tocar −1R. Objetivo, medido sobre velas
  cerradas, sin depender de si Fernando la tomó.
- **Quién emite**: la regla determinista dispara; el LLM anota al lado y **no vetea** — así el
  A/B sale gratis.
- **Sobre qué base se construye**: instrumento nuevo (~1,600 L), no poda en sitio. Replay y vivo
  comparten `rules.py`, `geometry.py` y `resolver.py`.
- **Corpus del periodo operado** (`task`, cerrado 08-21): descargado, 1,056 velas × 5 símbolos,
  2026-03-29 → 05-12. Los CSV que ya había terminan el 03-29 y el vivo empezó el 03-30 — el
  corpus de tuning y el periodo operado **no compartían una sola vela**.
- **Resolver consciente del lado** (`task`, cerrado 08-21): hecho y blindado con 6 escenarios
  espejados LONG/SHORT. La rutina de la que salió (`backtest_sim.py:106-155`) era LONG-only.
- **Línea base real** (derivada, no era ticket): 59 trades resueltos contra velas reales.
  Expectancy negativa en **todos** los horizontes (−0.11R a 12h … −0.42R a 336h). La etiqueta
  vieja coincide con lo que hizo el precio en **29 de 59** casos. Con una semana completa, solo
  **7 de 59** tocaron TP1 y 38 pegaron el stop; MFE mediana **+0.67R** contra objetivos que
  promediaban **1.27R**.

## Frontera — abierta (3 HITL, presupuesto lleno)

### 🎫 Cuánto vive una señal antes de declararse TIMEOUT
- tipo: `grilling` · estado: abierto · bloqueado por: —
- **default si no se contesta:** 72h
- Evidencia ya medida: a 36h el **63%** queda sin resolver (37 de 59 timeout); a 72h son 29;
  a 168h solo 14, pero aguantar una señal una semana deja de parecerse a lo que operas.
  Define el deadline del resolver y, con él, el denominador.

### 🎫 A qué número se retira un ruleset
- tipo: `grilling` · estado: abierto · bloqueado por: —
- **default si no se contesta:** se retira si tras 100 señales resueltas el borde superior del
  intervalo de confianza de la expectancy sigue por debajo de 0.
- Se escribe **antes** de la primera señal. Escrito después, se renegocia — que es exactamente
  como TAO llegó a 32 trades con 3% de aciertos.

### 🎫 Qué símbolos, fijos, para toda la ventana
- tipo: `grilling` · estado: abierto · bloqueado por: —
- **default si no se contesta:** solo ZEC (el estado actual)
- Cada símbolo agregado **divide** el denominador: es el mecanismo por el que el 83% de los
  trades quedó en 2 símbolos y ninguno juntó n suficiente. Pero con 1 símbolo y ≤3 alertas/semana,
  llegar a n=30 en vivo toma ~10 semanas.

### 🎫 Postgres persistente + respaldo fuera del proveedor
- tipo: `task` · modo: AFK · estado: abierto · bloqueado por: —
- No cuesta presupuesto de preguntas. Sin esto se repite el incidente de la DB efímera que borró
  5 meses de telemetría.

## Todavía sin precisar

- **La primera `rules.py`** (`prototype`). Formulable, pero **no se abre**: el presupuesto de 3
  tickets HITL está lleno. Entra cuando cierre uno de los de arriba. Ya tiene insumo: la MFE
  mediana (+0.67R) dice dónde vivía el precio, contra objetivos de 1.27R que casi nunca se
  tocaron — el objetivo se pone donde está la distribución, no en un múltiplo de ATR elegido a mano.
- **¿El veredicto del LLM correlaciona con el resultado?** (`research`). Depende de que existan
  señales vivas con `llm_verdict` guardado. Hoy no hay ninguna.
- Umbral de ambigüedad intrabar: hoy salió **0%** en 59 resoluciones a 1h, así que la pregunta
  de bajar a 5m ni siquiera se abre.

## Fuera de alcance

- **Encender LIVE / ejecución automática.** Fernando opera a mano; `trading_executor.py` se borra.
  Cierra de paso la pregunta del bracket-antes-del-Activar en vez de obligar a contestarla.
- **Recuperar el P&L histórico en dinero.** No existe columna de PnL y no hay `exit_price`; lo
  reconstruible es R, y ya se reconstruyó.
- **Podar el bot viejo en sitio.** Se evaluó y se descartó: deja dos caminos de código que ya
  divergieron una vez.
