# 📊 ZENITH PINE SCRIPT V6 SETUP

El indicador nativo para **TradingView** es la extensión visual de tu bot (V10.0). Está diseñado específicamente para funcionar en cuentas básicas (gratuitas), integrando todos los indicadores críticos en un solo "slot".

## 🛠️ Cómo Instalar

1.  Abre el archivo [Zenith_Suite_V6.pine](file:///Users/fernandocastaneda/Documents/ideas/scalp_bot/Zenith_Suite_V6.pine) en tu editor local.
2.  Copia todo el código.
3.  En TradingView, ve al panel inferior y abre el **Pine Editor**.
4.  Pega el código (sustituye cualquier cosa que haya).
5.  Haz clic en **"Add to Chart"**.

## 🎨 Componentes Visuales

- **EMA 200 (Tendencia Macro)**: Color dinámico (Rojo/Verde según la tendencia).
- **Bollinger Bands (Volatilidad)**: Zona azul para detectar sobre-extensiones.
- **BUY/SELL ZENITH**: Etiquetas automáticas en el gráfico que coinciden con las alertas del bot.
- **TP1/TP2/SL**: Líneas proyectadas dinámicamente según el ATR en el momento de la entrada.

## 📱 Alertas Nativas

Para sincronizar tu móvil con el algoritmo:
1.  En TradingView, haz clic en el reloj de **Alertas (Alt+A)**.
2.  En **Condition**, selecciona `Zenith Trading Suite V6`.
3.  Elige la opción `Zenith BUY Alert` o `Zenith SELL Alert`.
4.  Marca **"Notify on app"** y **"Show popup"**.

> [!TIP]
> Si el precio toca el **Suelo BB** y el **RSI es < 30**, mantente atento a la confirmación de la etiqueta de **BUY ZENITH**. ¡Coincidirá con el Análisis de Gordon y Aiden! 🚀📊🛡️
