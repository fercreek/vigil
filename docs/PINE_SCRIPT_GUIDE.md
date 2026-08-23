# Indicador de TradingView — Zenith V19

> Actualizado 2026-08-23. Antes esta guía apuntaba a `Zenith_Suite_V6.pine` y describía
> etiquetas BUY/SELL de "Gordon y Aiden" — trece versiones y un instrumento de medición
> atrás. Lo que sigue es lo que el bot decide **hoy**.

**Archivo:** [`scripts/tradingview/Zenith_Suite_V19.pine`](../scripts/tradingview/Zenith_Suite_V19.pine)
**Guardado en TradingView como:** `Zenith V19 | Instrument` (compila limpio en Pine v6).

## Qué es

Un espejo 1:1 de lo que corre en producción: `instrument/rules.py` + `instrument/geometry.py`
+ el enfriamiento de `instrument/main.py`. La vela que ves marcada en el chart es la misma
vela que el bot marca — los indicadores están portados con la misma recursión de Wilder
(arranque en 0, no sembrada con SMA) en vez de usar `ta.rsi` / `ta.atr` / `ta.adx` nativos,
que derivan unas decimas y harían que chart y bot discreparan.

## La regla, entera

| Paso | Qué pide |
|---|---|
| Sesgo | `close > EMA200` → LONG · `close < EMA200` → SHORT · empate → SUPRIMIDA |
| Evento | FOMC ±24h → SUPRIMIDA (en el bot sale del cache de conocimiento; en el chart es un input) |
| `rsi_extreme` | RSI ≤ 30 en LONG · ≥ 70 en SHORT |
| `bb_confluence` | %B ≤ 0.2 en LONG · ≥ 0.8 en SHORT |
| `adx_trending` | ADX ≥ 25 |
| `atr_min` | ATR/close ≥ 0.4% |
| Enfriamiento | un aviso por símbolo y lado cada 72 velas |

Geometría: **SL = 1.5 × ATR (= 1R) · TP1 = 0.7R · TP2 = 1.3R**, mitad fuera en TP1 y el
resto corre con el stop en entrada.

Los umbrales son valores de libro de texto **a propósito**. Una búsqueda de 1,296
configuraciones ajustadas al corpus pasó de +0.382R en calibración a −0.341R fuera de
muestra: el signo se invirtió. No se afinan a ojo.

## Qué NO trae, y por qué

- **V1-SHORT, V3-REV, V4-EMA** (las de V18): ninguna se midió nunca contra velas reales.
- **La ruptura Donchian + expansión**: retirada el 2026-08-21. Dio +0.014R contra su propio
  baseline **sin filtro** de +0.026R, a 16 alertas/semana — el filtro quitaba valor.
- **SL 2.0×ATR / TP1 2R / TP2 3.5R / TP3 7R** (la geometría de V18): de 59 trades medidos
  solo 7 tocaron TP1 y la MFE mediana fue +0.67R. El objetivo estaba puesto más allá de
  donde el precio llega.

## Lo que está medido, con su denominador

| | Resultado |
|---|---|
| Pullback 1h | **+0.146R** · n=107 · IC [−0.008, +0.301] · ~1.0 alerta/semana |
| Baseline sin filtro | −0.006R |
| El mismo pullback en 4h | **−0.039R** · n=32 |
| El mismo pullback en 1D | n=1 en dos años |
| Universo medido | 2 años × 6 símbolos: ZEC, TAO, BTC, ETH, SOL, BNB |

**Es un candidato, no un resultado.** El IC en 1h cruza cero y la ventaja se evapora en 4h;
una ventaja real suele sobrevivir en un marco vecino. El bot lo trata así y el panel del
indicador lo dice en pantalla.

## Cómo leerlo en el chart

- **Triángulo** — señal ENVIADA (la que el bot mandaría por Telegram).
- **X naranja arriba** — pasó los gates pero cayó en enfriamiento: mismo episodio, ya avisó.
- **Círculo gris abajo** — RSI y BB alineados pero falta ADX o ATR. Es lo que el bot vio y
  dejó pasar; el bot viejo solo dibujaba lo que disparaba y por eso nunca supo decir cuántas
  veces miró.
- **Panel superior derecho** — estado, motivo exacto, geometría, y el track record de arriba.
- **Panel inferior derecho** — los 4 gates con su valor actual contra lo que piden.

El panel se pinta **rojo** cuando el símbolo o el marco temporal están fuera de lo medido.

## Mover el panel

Los dos paneles eligen esquina desde **Entradas de datos → Visual**: seis posiciones cada
uno. Y **"Incluir el historial medido"** pliega el bloque de +0.146R / IC / 4h — el panel
pasa de 13 filas a 8 cuando solo quieres estado y geometria.

Hace falta porque TradingView dibuja las velas **encima** de las tablas de Pine: el fondo
opaco no evita que el precio cruce las filas. La salida es mover el panel a una esquina
tranquila o plegarle el historial, no pelearse con el color.

## Instalar

1. Copiar `scripts/tradingview/Zenith_Suite_V19.pine`.
2. Pine Editor → nombre del script → **Crear nuevo → Indicador** → pegar → **Añadir al gráfico**.
   Guardar el script **no** actualiza una copia ya aplicada al gráfico: hay que quitarla y
   volverla a añadir, o recargar la página, para que tome la version nueva.
3. Usar **1h**. En 4h la estrategia midió negativo.

> ⚠️ El plan Basic de TradingView permite **2 indicadores por gráfico**. Hay que liberar un
> slot antes de añadir V19.

## Alertas

Condición `V19 LONG pullback` / `V19 SHORT pullback`, o el `alert()` genérico, que emite un
JSON con los mismos nombres de campo que la tabla `signals` del instrumento — incluye
`in_corpus` para que se note en el payload cuando el símbolo está fuera de lo medido.

**El bot no ejecuta.** Es un aviso para operar a mano.
