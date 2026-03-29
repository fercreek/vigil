# Trading Scalp Bot 🤖📈

Este es un bot de trading de alta precisión diseñado para monitorear activos como **ETH, BTC y TAO**, enviando alertas directas a Telegram cuando encuentra oportunidades de "Scalping" (operaciones rápidas).

## ¿Qué hicimos recientemente? (Estrategia V1.6)

Anteriormente, el bot tomaba decisiones demasiado deprisa basándose solo en gráficas de 15 minutos, lo que a veces causaba que compráramos cuando el mercado general estaba cayendo.

Para solucionar esto, implementamos el **Bloqueo Direccional (Filtro Macro)**:
1. Ahora el bot primero "mira desde arriba": Revisa la tendencia general del mercado en gráficas grandes (1 Hora y 4 Horas).
2. Si la tendencia general de 4 horas está **BAJISTA**, el bot se bloquea inteligentemente y **solo buscará operaciones de venta (SHORT)** en gráficas de 15 minutos, ignorando cualquier rebote engañoso.
3. Si la tendencia es **ALCISTA**, **solo buscará operaciones de compra (LONG)**.

*Resultado*: Ya no operamos "LONG y SHORT" a la vez. Operamos **100% a favor de la corriente del mercado**, subiendo enormemente nuestra tasa de acierto y protegiendo el dinero.

## ¿Qué significan las Alertas en Telegram?

Cuando el bot encuentra una oportunidad alineada con el mercado, envía un mensaje como este:

- 💎 **DIAMANTE (Score 4/5)**: Es una calificación de calidad. Significa que múltiples indicadores (RSI, Volatilidad, Tendencia) están perfectamente alineados.
- 🌍 **MACRO ALCISTA / BAJISTA**: Te confirma que la operación está respaldada por la temporalidad de 4 horas y 1 hora.
- 🎯 **TP1 y SL**: Te da exactamente dónde tomar la ganancia inicial y dónde poner el límite de pérdida para proteger tu cuenta automáticamente.
- 🤖 **CONSENSUS IA**: Si ves este ícono, significa que además de los cálculos matemáticos, la Inteligencia Artificial de Gemini aprobó la operación analizando el sentimiento del mercado.

## Cómo encender el bot

1. Activa el entorno virtual: `source venv/bin/activate`
2. Ejecuta el bot de alertas: `python scalp_alert_bot.py`
3. Ejecuta el Dashboard web (si deseas ver el historial): `python app.py`

¡Déjalo correr y espera las notificaciones en tu Telegram!
