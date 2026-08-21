# MAPA — Instrumento de medición de señales (Zenith)
> FOCUS-<pendiente — ⚠️ incumple la regla 6 del propio skill> · caduca: **2026-09-20** · repo: `fercreek/vigil`
> Trazado 2026-08-21 con el skill `wayfinder`.

## Destino

Un instrumento que, ante cualquier regla de señal, responde en minutos y con denominador
explícito si tiene ventaja — y que emite un puñado de alertas accionables al día.

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

## Cadencia — revisada 2026-08-21

El tope de **≤3 alertas/semana** se fijó cuando había **1 estrategia sobre 1 símbolo**. Hoy son
**2 estrategias × 6 símbolos = 12 flujos**, y 3 por semana entre doce vuelve a ser silencio.

**Nueva cadencia: ~17 alertas/semana (2-3 al día).** Es el ritmo natural del sistema, no un
número elegido: sale de dejar correr las dos reglas con el enfriamiento puesto. Medido sobre 30
días y 6 símbolos: 228 disparos crudos → **74 tras enfriamiento**.

**El enfriamiento se queda** (`main.py:_in_cooldown`): una ruptura sigue rompiendo, y el 19-ago
la regla disparó **5 veces sobre la misma subida de ETH**. Eso es un trade contado cinco veces —
la misma autocorrelación serial que hizo parecer real una ventaja de +0.110R hasta que se
espaciaron las entradas. La ventana es `MAX_HOLD_BARS`, no un número afinado: mientras la primera
señal sigue abierta, una segunda sobre el mismo movimiento no es información nueva.

**Lo que NO se hizo:** apretar umbrales para que la cadencia cuadre. Eso es ajustar a ojo, y ya
falló tres veces en este repo.

## Decisiones cerradas por default (2026-08-21)

Los tres tickets HITL de la frontera se cerraron **aplicando su default**, no contestándolos.
Es la regla 3 del skill funcionando: *un ticket con default no bloquea — envejece y se aplica*.
Fernando puede revertir cualquiera y se recalibra.

- **Cuánto vive una señal** → **72h**. A 36h el 63% quedaba sin resolver (37 de 59); a 168h solo
  14, pero aguantar una señal una semana deja de parecerse a lo que se opera.
- **A qué número se retira un ruleset** → se retira si tras **100 señales resueltas** el borde
  superior del IC de la expectancy sigue < 0. Escrito antes de la primera señal, a propósito.
- **Qué símbolos** → **solo ZEC**. Cada símbolo agregado divide el denominador.

**Efecto sobre el presupuesto:** cerrar tres HITL liberó el cupo, así que `regla-v1` graduó de
niebla a ticket vivo en la misma pasada. Esa es la mecánica, no una excepción a ella.

## Frontera — abierta

### ✅ La primera `rules.py` — CERRADO 2026-08-21: no hay ventaja

Resuelto con evidencia, no con opinión. Tres intentos, tres veredictos de NO EDGE:

1. **Búsqueda de umbrales** (1,296 configuraciones, partición temporal): la mejor pasó de
   +0.382R a **−0.341R** fuera de muestra, y perdió contra comprar sin filtro.
2. **5 hipótesis de ENTRADA pre-registradas** con su mecanismo económico, sobre 6 símbolos ×
   4 tramos × 2 años: ninguna pasó sus propios criterios. H4 (fadear capitulación) salió
   **significativa al revés** — la vela extrema continúa, no revierte.
3. **5 hipótesis de SALIDA pre-registradas**: dos parecieron tener ventaja consistente entre
   regímenes (+0.110R el trailing). **Era autocorrelación**: entradas cada hora aguantando 240
   velas cuentan el mismo movimiento ~72 veces. Re-medido sin solape → **−0.005R**, IC cruzando
   cero, celdas saltando de +1.13R a −0.59R. Reproducible: `instrument/scripts/test_independence.py`.

**Decisión de Fernando:** el bot queda **midiendo sin emitir**. `rules.py` conserva umbrales
estándar que disparan cero veces, marcado NOT LIVE-READY, y G1 bloquea el merge con N=0.

**Para reabrir este ticket hace falta una hipótesis con mecanismo**, no otra búsqueda. Lo que
sí quedó apuntando a algo: H4 en reversa, y el timeframe diario —donde 2 años sí dan trades
independientes suficientes— que no se ha probado.

### 🎫 (retirado) La primera `rules.py`
- tipo: `prototype` · estado: **en curso** (cabeza Sonnet, hydra 08-21) · bloqueado por: —
- Graduó de la niebla al cerrarse los tres de arriba.
- Insumo medido: MFE mediana **+0.67R** contra objetivos que promediaban **1.27R** — el objetivo
  se pone donde vive la distribución de excursión, no en un múltiplo de ATR elegido a mano.
- Criterio: cadencia revisada el 2026-08-21 (ver abajo). Si ningún umbral da expectancy
  positiva, ése es el resultado y se reporta — no se maquilla.

### 🎫 Postgres persistente + respaldo fuera del proveedor
- tipo: `task` · modo: AFK · estado: abierto · bloqueado por: —
- Sin esto se repite el incidente de la DB efímera que borró 5 meses de telemetría.

### 🎫 Cablear `main.py`
- tipo: `task` · modo: AFK · estado: abierto · bloqueado por: los módulos en curso
- 🔴 **El destino dice "responde en minutos" y hoy no lo cumple**: sin cableado central hay
  módulos aislados que funcionan, no un instrumento que le responda algo a alguien.

## Todavía sin precisar

- **Cómo se valida contra datos VIVOS**, y cuándo. Es el cierre de "¿qué tan bueno es esto de
  verdad?" y hoy no está ni en la frontera ni fuera de alcance — solo se ha validado contra
  histórico. Se precisa después de que `rules.py` cierre.
- **¿El veredicto del LLM correlaciona con el resultado?** (`research`). Depende de que existan
  señales vivas con `llm_verdict` guardado. Hoy no hay ninguna.
- Umbral de ambigüedad intrabar: salió **0%** en 59 resoluciones a 1h, así que la pregunta de
  bajar a 5m ni se abre.

## Fuera de alcance

- **Encender LIVE / ejecución automática.** Fernando opera a mano; `trading_executor.py` se borra.
  Cierra de paso la pregunta del bracket-antes-del-Activar en vez de obligar a contestarla.
- **Recuperar el P&L histórico en dinero.** No existe columna de PnL y no hay `exit_price`; lo
  reconstruible es R, y ya se reconstruyó.
- **Podar el bot viejo en sitio.** Se evaluó y se descartó: deja dos caminos de código que ya
  divergieron una vez.
