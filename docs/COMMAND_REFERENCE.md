# ⌨️ GUÍA DE COMANDOS TELEGRAM (Zenith V10.2)

Interactúa con el bot institucional de Zenith directamente desde tu móvil. Todos los comandos son procesados por el motor de **Sanitización V1.6** para evitar errores.

## 📊 Comandos de Estado

- `/status`: 🔄 Genera el reporte de sentimiento global con Bias (BULL/BEAR) y mini-opiniones de Gordon y Aiden.
- `/analyze [SOL/BTC/TAO]`: 🧠 Solicita un análisis profundo de 15m/1h a la IA experto. Incluye lecturas de RSI, BB y ATR.
- `/audit`: 🏛️ Consulta las métricas de rendimiento actuales (Win Rate, Profit Factor, Total Trades).

## 🚀 Comandos de Trading Manual (Smart Control)

Ahora puedes operar con el respaldo técnico del bot:
- `/SOL LONG` o `/sol long`: 📈 Abre una posición larga en Solana con targets dinámicos (TP1, TP2, SL). 
- `/BTC SHORT` o `/btc short`: 📉 Abre una posición corta en Bitcoin con targets dinámicos.
- `/TAO LONG` o `/tao long`: 🤖 Abre una posición en Bittensor.

> [!IMPORTANT]
> **Lógica de Toggle**: Solo se permite una posición activa por símbolo. Si envías un comando manual sobre un símbolo abierto, el bot cerrará automáticamente el trade anterior antes de abrir el nuevo.

## 🏁 Gestión de Posiciones

- `/CERRAR TAO`: 🚫 Cierra manualmente cualquier posición abierta en TAO (o BTC/SOL) y calcula el PnL final.
- `CLOSE TAO`: Equivalente a /CERRAR.

## ⚙️ Menú Interactivo
Si el bot detecta un mensaje desconocido, te presentará el **Menú Principal de Botones** para que navegues rápidamente entre las opciones de análisis y estado.

¡Opera con inteligencia, no con la emoción! 🛰️🛡️🎭🚀
