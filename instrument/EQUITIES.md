# El pullback en acciones — medido 2026-08-23

Se pregunto si la regla que el bot usa en cripto sirve tambien en acciones. La
respuesta corta: **en LONG si, en SHORT no**, y el motivo por el que se creia que
no iba a servir resulto ser falso.

Reproducible: `scratchpad/geom_lab.py` (el evaluador), `verify_fast.py` (la prueba
de que reproduce `rules.evaluate` vela por vela), `run_stocks.py`, `baseline.py`,
`long_only.py`, `crypto_sides.py`.

## Lo que se midio

Datos: 1h de yfinance, **730 dias, 29 tickers, 143,367 velas**. Los umbrales son los
mismos de `rules.py` — nada se ajusto. Enfriamiento de 72 velas por simbolo y lado,
igual que `main.py`. Resuelto con `resolver.py`: mitad fuera en TP1, el resto corre
con el stop en entrada.

| | n | expectancy | IC 95% | aciertos |
|---|---:|---:|---|---:|
| **Regla, solo LONG** | **138** | **+0.216R** | **[+0.071, +0.362]** | 68.1% |
| Regla LONG, 1a mitad | 63 | +0.135R | [−0.094, +0.363] | 61.9% |
| Regla LONG, 2a mitad | 75 | +0.285R | [+0.098, +0.472] | 73.3% |
| Baseline LONG, sin ningun gate | 1044 | +0.026R | [−0.029, +0.081] | 57.7% |
| **Regla, solo SHORT** | **130** | **−0.012R** | [−0.166, +0.143] | 56.9% |
| Regla, ambos lados | 268 | +0.106R | [−0.001, +0.212] | 62.7% |

**Los cuatro gates aportan.** Comprar sin filtro con la misma geometria y el mismo
espaciado dio +0.026R sobre 1,044 entradas; la regla dio +0.216R sobre 138. La
diferencia, +0.19R, es lo que hacen RSI, banda, ADX y ATR juntos — no es la deriva
del mercado, porque la deriva ya esta dentro del baseline.

**Aguanta la particion temporal.** Positivo en las dos mitades y sin cambio de signo.
Eso es exactamente lo que el pullback NO logro al subir a 4h en cripto (+0.146R en 1h
se volvio −0.039R en 4h), y es la razon por la que alla quedo marcado como candidato.

**El SHORT no aporta nada.** −0.012R con n=130 es indistinguible de no operar. Tiene
mecanismo: comprar retrocesos aprovecha la deriva alcista estructural de las acciones;
vender rebotes pelea contra ella.

## El diagnostico que estuvo mal, y por que

Una primera pasada sobre **60 dias** dio −0.331R con **n=13** y una MAE mediana de
−1.40R. De ahi salio una explicacion completa: los huecos de apertura rebasan el stop,
un stop de 1R cuesta 1.4R, la geometria esta rota. Se construyo hasta una variante que
ensanchaba el stop al percentil 90 del hueco.

Con **n=268** la MAE mediana es **−0.78R** — el stop aguanta — y la variante del hueco
salio **identica** a la original: el hueco tipico nunca supero 1.5xATR, asi que el
`max()` jamas se activo. El True Range ya contiene el hueco por definicion.

Trece trades no eran una muestra, eran una cola. Es el mismo defecto que este
instrumento existe para no repetir, cometido aqui por apurar una respuesta.

## Lo que NO se toco, y por que

`rules.py` sigue operando los dos lados. En cripto la muestra por lado es **n=26**
(12 LONG, 14 SHORT) sobre 500 dias: LONG apunta mas alto (+0.392R contra +0.100R) pero
con ICs que se solapan por completo. Recortar un lado del bot con esa evidencia seria
el ajuste a ojo que ya fallo tres veces en este repo.

El gate de lado vive **solo en el indicador** (`Zenith_Suite_V19.pine`), con
auto-deteccion por `syminfo.type`: restringe a LONG en acciones, no toca cripto.

## Criterio de retiro, escrito antes y CABLEADO

Los dos anios medidos son de mercado alcista. Si el LONG en acciones acumula
**100 senales resueltas en vivo** y el borde superior del IC de la expectancy sigue
por debajo de cero, se retira. Escrito antes de la primera senal, no despues de ver
el resultado.

Desde 2026-08-23 no es prosa: lo aplica `kill_rule.py` en cada ciclo, contra la tabla
`retirements`. Un universo retirado deja de emitir (`main.py::_evaluate_and_store`)
pero **sigue evaluando y guardando** -- sin esas filas no habria forma de comprobar
despues si retirarlo fue correcto. El aviso por Telegram sale una sola vez y trae las
cifras que lo decidieron.

Cripto y acciones se retiran **por separado**. Reactivar un universo es una decision
humana: borrar su fila de `retirements`. El codigo nunca la borra.
