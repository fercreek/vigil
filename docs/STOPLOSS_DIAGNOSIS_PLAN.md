# Diagnóstico "hay muchos stop loss" + plan de mejora

> 2026-08-20 · Analizado contra `trades.db` local, el código vivo y las variables reales de Railway.
> **No es asesoría financiera.** Todo lo de abajo es ingeniería del sistema: cómo mide, cómo etiqueta
> y cómo ejecuta. Las decisiones de qué operar y con cuánto capital son tuyas.

---

## 0. La caja de la evidencia (leer antes que los números)

| Qué | Alcance real |
|---|---|
| Trades analizados | **92** (`trades.db` local) — 91 cerrados, 1 abierto |
| Ventana | **2026-03-30 → 2026-05-27**, ~8 semanas |
| Desde el 27-may | **no hay registro** — ver causa #1 |
| PnL en R | **reconstruido** de los niveles guardados (entry/SL/TP), asumiendo fill exacto. Sin fees ni slippage → el real es peor |
| Cobertura del R | 89 de 92 filas tenían `atr` guardado; las otras 3 quedaron fuera del cálculo |

Todo lo que sigue sale de esas 92 filas y del código. **No hay data de junio, julio ni agosto** —
así que si la sensación de "muchos stop loss" viene de las últimas semanas, esto explica el
mecanismo, no esas corridas en particular.

---

## 1. El número que ves y el número que es

Los 91 trades cerrados:

| Estado guardado | N | % |
|---|---|---|
| `LOST` | 74 | 81% |
| `FULL_WON` | 14 | 15% |
| `PARTIAL_CLOSED` / `WON` | 3 | 3% |

81% rojo. Pero al abrir los 74 `LOST` y mirar dónde quedó el SL contra la entrada:

| Tipo de "pérdida" | N | Qué pasó de verdad |
|---|---|---|
| SL original (riesgo completo) | **62** | pérdida real de −1R |
| SL arrastrado **a zona de ganancia** | **10** | **cerró en verde** y se guardó como `LOST` |
| SL en breakeven | **2** | cerró en 0 y se guardó como `LOST` |

**12 de los 74 "stop loss" no fueron pérdidas.** El bot te mandó `🔴 SL HIT` por trades que
cerraron planos o en ganancia. La pérdida real es **62/91 = 68%**, no 81%.

Y el PnL reconstruido, que es lo que importa:

| Símbolo | N | Total R |
|---|---|---|
| **ZEC** | 44 | **+22.6** |
| OIL | 5 | +0.5 |
| BTC / ETH / SOL | 3 | −3.0 |
| GOLD | 7 | −2.0 |
| **TAO** | 30 | **−28.0** |
| **Neto** | 89 | **−9.9** |

ZEC ganó **+22.6R con 31 pérdidas de 44 trades**. El agujero completo es TAO. Esto ya lo
resolviste con la Poda A de Fénix (TAO fuera del auto-scan) — el dato solo confirma que fue
la decisión correcta.

**Conclusión #1: la tasa de pérdida no es el problema. El etiquetado sí, y el símbolo sí.**
Una estrategia de reversión con TP a 2.5 ATR y SL a 2.0 ATR *tiene* que perder ~70% de las
veces. Tu propio `_BACKTEST_HISTORICO.md` lo dice: V3 hizo +63.8% con 27.8% de aciertos.

---

## 2. Las cinco causas medidas

### Causa A — El bot no tiene un tercer resultado, solo verde o rojo

El backtester (`backtest_sim.py:135-155`) simula tres cosas que el bot vivo no hace:

```
PARTIAL_WON      → cierra 50% en TP1, SL a BE, el resto corre  → +0.62R, nunca −1R
TIMEOUT_PARTIAL  → 50% tomado + resto a mercado                → PnL real
TIMEOUT          → cierre a mercado por tiempo                 → PnL real
```

El bot vivo (`trade_monitor.py:86-94`) al tocar TP1 **no cierra nada**. Mueve el SL a BE y deja
el 100% puesto. Si el precio regresa, sale en 0 y se guarda `LOST`.

Cuánto pesa: en tu mejor corrida de tuning (400 trades, `data/tune_results.json`) el sim reporta
`LOST` 210 = **52%**. Si le sumas los estados que el bot vivo no puede producir —
`PARTIAL_WON` 57 + `TIMEOUT_PARTIAL` 24 + `TIMEOUT` 33 — el equivalente vivo es
**324/400 = 81%**.

**Es exactamente el 81% que ves.** No es que el bot esté perdiendo más que el backtest: es que
convierte en rojo el 28% de trades que el backtest cuenta como no-pérdida.

Corolario incómodo: **cada backtest positivo que tienes (V4 BTC +49R, BNB +85R, GOLD +35R)
está construido sobre una mecánica de parciales que no existe en producción.**

Prueba directa: `be_moved = 0` y `partial_pct = 0` en **las 92 filas**. Las columnas existen
desde `tracker.py:53-54`, `mark_be()` y `mark_partial()` están escritas (`tracker.py:445-458`)
y **solo las llama `manual_positions_monitor.py`**, nunca el flujo automático. El tag `[BE]` de
`telegram_commands.py:158` nunca se ha mostrado.

### Causa B — El trailing stop está calibrado en el timeframe equivocado

| Momento | Distancia del SL | Fuente |
|---|---|---|
| Al abrir un SWING | `2.0 × ATR(4h)` | `swing_bot.py:34,37,109` |
| Al llegar a 1:1 | `2.5 × ATR(15m)` | `risk_manager.py:385` + `scalp_alert_bot.py:872,907` |

`prices["{sym}_ATR"]` se llena con `get_indicators(sym, "15m")`. **Es ATR de 15 minutos.**
ATR(4h) ≈ 4× ATR(15m), así que el stop de entrada vale ~8 ATR(15m) y el trailing lo reemplaza
por 2.5 ATR(15m): **queda ~3× más apretado que la volatilidad para la que se diseñó el trade.**

Efecto: todo swing que llega a 1:1 pasa a colgar de un ruido de 15 minutos. Sale por un
retroceso menor, y como sale por `is_sl`, se anuncia `🔴 SL HIT` y se guarda `LOST` — aunque
cierre en verde. **Ahí están los 10 "stop loss" que fueron ganancia.**

### Causa C — El cierre por tiempo miente sobre su resultado

`trade_monitor.py:121,131`: a las 36h sin TP1, el SWING se cierra y se marca
`update_trade_status(t["id"], "LOST")` + `circuit_breaker.record_outcome(is_win=False)` —
**sin mirar el PnL**. El mensaje sí imprime el `pnl_pct` real; la base de datos no.
Un cierre por tiempo en +1.8% se archiva idéntico a un −1R.

52 de las 74 pérdidas duraron más de 24h. El time-exit entró el 2026-04-15 (`b23779e`), o sea
solo la última semana de la muestra — pero de aquí en adelante contamina todo.

### Causa D — El circuit breaker cuenta ganancias como pérdidas, y se le borra la memoria

Las causas B y C llaman `record_outcome(is_win=False)` en salidas planas o positivas. El breaker
entra en `CAUTIOUS` a 2 pérdidas seguidas y `HALTED` a 3 (`risk_manager.py:43-51`). Se está
frenando a sí mismo con trades que ganaron.

Y su estado vive en `risk_state.json`, ruta relativa (`risk_manager.py:36`) sobre disco efímero.
Con `restartPolicyType = "ALWAYS"` en `railway.toml`, **un bot en `HALTED` que se reinicia
vuelve en `NORMAL` y sigue operando.** Es el freno de un auto-ejecutor real: `strategies.py:936-951`
manda órdenes bracket a Binance con `conf_score >= 4`, y las llaves de Binance están puestas
en producción.

### Causa E — No hay evidencia porque el sistema borra la suya

Verificado en las variables reales del servicio `web` (proyecto `gentle-endurance`):

- **`TRACKER_DB` no está definida** → `tracker.py:5` cae al default `"trades.db"`, ruta relativa.
- **No aparece `RAILWAY_VOLUME_MOUNT_PATH`** → no hay volumen montado.

Cada `railway up` y cada reinicio **borra el historial de trades**. Por eso la data local se
detiene el 27-may. Esto ya está escrito como MUST en `_NEXT.md` bajo "🔒 Falta — DEPLOY Railway",
sin palomear. Es la causa #1 en importancia: sin esto, ninguna mejora se puede medir.

---

## 3. Plan

Orden por dependencia, no por antojo. Cada fase tiene su criterio de aceptación.

### P0 — Poder medir (sin esto lo demás es opinión)

| # | Qué | Dónde | Aceptación |
|---|---|---|---|
| P0.1 | Volumen Railway montado en `/data` + `TRACKER_DB=/data/trades.db` | Railway UI (lo haces tú) | Redeploy y `SELECT COUNT(*) FROM trades` no vuelve a 0 |
| P0.2 | `risk_state.json` al volumen: `RISK_STATE_FILE` con default `/data/risk_state.json` | `risk_manager.py:36` | Reiniciar en `HALTED` y seguir `HALTED` |
| P0.3 | Estado de salida honesto: `STOPPED` / `BE_STOP` / `TRAIL_WIN` / `TIME_EXIT` en vez de `LOST` para todo | `trade_monitor.py:69,121` + `tracker.update_trade_status` | Un trade que cierra en verde jamás vuelve a guardarse `LOST` |
| P0.4 | Guardar `exit_price` y `pnl_pct` reales en la fila al cerrar | `tracker.py:613` | Ya no hay que reconstruir el PnL de los niveles |
| P0.5 | `record_outcome(is_win=...)` decidido por el PnL real, no por la rama de código | `trade_monitor.py:76,131` | El breaker deja de contar ganancias como pérdidas |

P0.3 y P0.4 son los que apagan la sensación de "muchos stop loss" **sin tocar la estrategia**:
12 de 74 mensajes rojos dejan de salir rojos, y los que sí son pérdida quedan separados de los
cierres por tiempo.

### P1 — Cerrar la brecha sim ↔ vivo (aquí está el R)

| # | Qué | Dónde | Aceptación |
|---|---|---|---|
| P1.1 ✅ | **Parcial 50% en TP1** — hecho 08-20 — lo que el backtester ya asume | `trade_monitor.py:86-94` → llamar `tracker.mark_partial(id, 50)` + `mark_be(id)` | `partial_pct=50` y `be_moved=1` visibles en la fila; el tag `[BE]` por fin aparece en Telegram |
| P1.2 | Trailing en el ATR del timeframe del trade, no en 15m | `risk_manager.py:385` — pasar el ATR de entrada (columna `atr`) o el de 4h | La distancia del trailing nunca queda más apretada que la del SL de entrada |
| P1.3 | Time-exit cierra a mercado con su PnL real | `trade_monitor.py:121` | Cierre en +1.8% se guarda +1.8%, no `LOST` |
| P1.4 | TP3 monitoreado o quitado de la alerta | `swing_bot.py:150,154` manda TP3; `trades` no tiene columna | O se persigue o no se anuncia |
| P1.5 | `backtest_sim.py` importa de `config.py` en vez de duplicar constantes | ya está en `_NEXT.md` | Un cambio de `V3_SL_ATR` mueve sim y vivo a la vez |

**P1.1 es la de mayor palanca de todo el documento.** Es la diferencia entre `PARTIAL_WON`
(+0.62R) y `LOST` (0R) en ~20% de los trades, y es lo único que hace que tus backtests
describan al bot que está corriendo.

### P2 — Recalibrar, pero ya con datos propios

Nada de esto antes de que P0 lleve ≥30 trades resueltos con etiquetado honesto. Es la regla-gate
que ya escribiste en Fénix F3.

- Reevaluar `ATR_SL=2.0` / `ATR_TP1=2.5` (R:R 1.25). Tu tuning de junio dio `sl_atr: 1.5`
  como mejor en las 120 corridas, y `V3_SL_ATR_MULT` ya está en 1.5 — `swing_bot.py:37` sigue en 2.0.
- Correr el sim con la mecánica vivos-vs-sim ya alineada y ver si el edge sobrevive.
- Recién ahí, tocar filtros de entrada.

---

## 4. Lo que NO recomiendo

- **No subas el win rate apretando filtros.** El sistema está diseñado para perder 70% de las
  veces; ZEC ganó +22.6R perdiendo 31 de 44. Si persigues el porcentaje verde matas la cola
  de ganadores que paga todo.
- **No ensanches el stop "para que no salte".** Con `MAX_CONCURRENT_POSITIONS=3` y ejecución
  real en Binance, un stop más ancho es más riesgo por trade, no menos pérdidas.
- **No agregues símbolos ni specs nuevas** hasta que P0 esté midiendo. TAO costó 28R y se
  detectó tarde justamente por esto.

---

## 5. Nota de seguridad (aparte del tema)

`railway variables` imprime en claro las llaves de Binance, Gemini, Groq y el token de Telegram.
Si esa salida se pegó en algún chat o log, esas cuatro se rotan. La de Binance es la que mueve
dinero.


---

## 6. Bitácora

### 2026-08-20 — P1.1 implementado

`config.py` · `tracker.py` · `trade_monitor.py` · `tests/test_partial_tp1.py` (15 tests).

Lo que cambió al construirlo respecto a lo que decía el diagnóstico arriba: **en modo LIVE el
parcial ya existía en el exchange.** `trading_executor.py:130-134` deja una limit reduceOnly de
`amount * 0.5` en TP1 desde que se abre el bracket — Binance ya venía cerrando la mitad y la DB
no se enteraba. Así que P1.1 no manda ninguna orden nueva (hacerlo cerraría el runner dos veces):
pone la contabilidad de acuerdo con lo que ya pasa afuera. En PAPER y en los SWING manuales sí es
puramente contable.

Lo que ahora hace el bot al tocar TP1: `partial_pct=50`, `be_moved=1`, SL al BE con offset, y un
evento en `events_json`. Si después regresa al BE, el cierre es `PARTIAL_CLOSED` con el PnL
mezclado de las dos patas, no `LOST`.

**Todavía no se puede medir.** P0.1 sigue pendiente: mientras no haya volumen en Railway, estos
estados nuevos se borran en el siguiente deploy igual que los viejos.

Pendientes que salieron de aquí y no entraron al scope:
- **No existe `cancel_order` ni `edit_order` en todo el repo.** Cuando el bot mueve el SL (BE o
  trailing) solo cambia la DB; la orden `STOP_MARKET` en Binance se queda donde estaba. En LIVE
  eso es divergencia real entre lo que el bot cree y lo que el exchange tiene. Hoy no muerde
  porque `EXECUTION_MODE` no está seteada en Railway y el default es `PAPER`.
- `gemini_analyzer.log_result_to_context:451` calcula su PnL como `(close-entry)/entry` sin mirar
  el lado → el signo sale invertido en SHORT. Solo afecta el texto que se le guarda a las personas
  de la Cuadrilla, no la contabilidad.


### 2026-08-20 — Sincronización del stop con el exchange

`trading_executor.sync_stop_loss()` cancela la `STOP_MARKET` viva y crea la nueva con el precio
actualizado. Cableado en los dos puntos que movían el SL solo en la DB: TP1→BE y el trailing.
22 tests en `tests/test_stop_loss_sync.py`. Suite: 295 pasan, las mismas 9 fallas de siempre.

**Lo caro no fue mover el stop, fue no tocar lo que no es del bot.** Al cablearlo salió que la
fila de `trades` no tenía forma de saber si esa posición tenía órdenes del bot en Binance. Sin eso,
sincronizar a ciegas habría puesto órdenes sobre posiciones SWING o manuales — peor que el bug
original. Por eso el cambio incluye una **marca de propiedad**: columna `exchange_order_id`, que
viaja desde `execute_bracket_order` → `_store_pending` → `log_trade`, y solo se setea cuando el
status es `LIVE_EXECUTED`. Sin esa marca, `sync_exchange_stop` se salta la fila.

Además `sync_stop_loss` **nunca crea un stop donde no había**. Si la orden desapareció devuelve
`NOT_FOUND` y no toca nada. El único caso que grita es el peligroso: viejo cancelado + nuevo
rechazado → alerta `🚨 POSICION SIN STOP` a Telegram, porque ese estado no se puede quedar callado.

Nada de esto se activa hoy: `EXECUTION_MODE` no está en Railway y el default es `PAPER`. Verificado
otra vez el 08-20.

#### 🔴 Lo que salió al hacerlo, y es más grave que lo que se arregló

**El bracket se manda a Binance ANTES de que apruebes la señal.** `strategies.py:938` ejecuta
`execute_bracket_order` en cuanto `conf_score >= 4`, dentro del ciclo de scan. El botón *Activar*
de Telegram llega después y lo único que hace es crear la fila de tracking (`scalp_alert_bot.py`,
rama `activate`). O sea: en LIVE el dinero ya se movió cuando te llega la pregunta, y si le das
*Skip* la posición se queda abierta en Binance sin fila que la monitoree.

Hoy es inofensivo porque el modo es PAPER. **El día que enciendas LIVE, esto muerde antes que
cualquier otra cosa de este documento.** No lo toqué porque cambia el modelo de aprobación y esa
decisión es tuya: o el bracket espera al *Activar*, o el *Activar* deja de fingir que es una
aprobación.
