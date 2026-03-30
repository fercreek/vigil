# 📈 Lógica de Estrategia y Confluencia

El bot ha evolucionado a través de múltiples iteraciones para reducir el ruido y maximizar la precisión científica en las entradas.

## 📊 Sistema de Confluencia Total (Score 0-5)

Para cada activo, se calcula un **Confluence Score** basado en 5 pilares:

1.  **RSI (2 pts)**: 
    -   `LONG`: RSI ≤ 30 (+2), RSI ≤ 40 (+1).
    -   `SHORT`: RSI ≥ 70 (+2), RSI ≥ 60 (+1).
2.  **Trend EMA 200 (1 pt)**: Precio en el lado correcto del promedio móvil de 200 periodos.
3.  **Bollinger Bands (1 pt)**: Precio tocando o muy cerca de las bandas externas.
4.  **USDT Dominance (1 pt)**: Dirección favorable de la dominancia de Tether (Macro sentiment).
5.  **Elliott Wave (1 pt)**: Bonus si se detecta una "Onda 3" impulsiva.

## 🔄 Evolución de Versiones

### V1-TECH (Estrategia Clásica)
-   **Enfoque**: Indicadores estáticos (RSI, Bollinger, EMA).
-   **Gestión**: Stop Loss fijo basado en niveles históricos o Pivot Points diarios.

### V2-AI CONSENSUS (Estrategia Híbrida)
Añade una capa de inteligencia al score técnico.
-   **Lógica**: Si Score ≥ 3, se consulta a Gemini.
-   **Confirmación**: La IA puede otorgar un "+1" de confianza o rechazar la operación por razones fundamentales (ej. "USDT.D en resistencia crítica").

### V3 INTRADÍA REVERSAL (Agresiva)
Diseñada para capturar rebotes en condiciones extremas.
-   **Gatillo**: RSI < 28 (Oversold Extremo) mientras el precio está lejos de la EMA 200.
-   **Objetivo**: Retorno a la media.
-   **Gestión**: Stop Loss más amplio (2*ATR) para permitir "respirar" al precio.

## 🛑 Gestión de Riesgo (ATR Based)

El bot utiliza el **ATR (Average True Range)** para calcular niveles dinámicos:
-   **Stop Loss**: Generalmente `1.5 * ATR`.
-   **Take Profit 1**: `2:1 R:R` (Elimina riesgo moviendo a Break-Even).
-   **Take Profit 2**: `3:1 R:R` (Cierre total de la posición).

---

## 📉 Filtros Antivolatilidad

-   **Audit V1.6.1**: Se bloquean señales si Elliott detecta una "Fase Correctiva" (ABC), para evitar ser atrapado en rangos de indecisión.
-   **Filtro de Apertura (NYSE)**: El bot intensifica la vigilancia durante la apertura de Wall Street para capturar impulsos institucionales.

> [!TIP]
> El sistema de Pivot Points se actualiza cada 24 horas (`update_dynamic_levels`) basándose en la vela de ayer, asegurando que los soportes y resistencias sean siempre relevantes.
