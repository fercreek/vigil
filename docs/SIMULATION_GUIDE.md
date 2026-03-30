# 🏛️ GUÍA DEL TRADER SIMULADO ZENITH (V5.0)

Este documento define la "Verdad Terrenal" (Ground Truth) de nuestro sistema de trading. Como Senior Developer y Trader, este es nuestro marco de control para el experimento de 24 horas y la mejora continua del Win Rate.

---

## 🎯 Filosofía de Ejecución: Calidad > Cantidad

El objetivo no es operar mucho, sino operar **bien**. Cada alerta que el bot genera se registra como una "Ejecución Simulada en Vivo" (Live Simulation).

### 1. El Filtro Institucional (H4 Bias)
-   **Regla de Oro**: Ningún trade intradía (15m) debe ir en contra de la tendencia macro de 4 horas (H4).
-   **BULL Bias**: Solo se permiten LONGs. Los SHORTS se ignoran o se marcan como "Contra-tendencia".
-   **BEAR Bias**: Solo se permiten SHORTS. Los LONGs se ignoran.
-   **ACCUMULATION**: Se permiten ambos, operando de extremo a extremo de las Bandas de Bollinger.

### 2. El Escudo Macro (USDT.D)
La dominancia de USDT es el termómetro del miedo:
-   **USDT.D > 8.08%**: Pánico. Solo buscar suelos extremos para rebotes rápidos.
-   **USDT.D < 8.044%**: Euforia/Bullish. Mantener los LONGs hasta TP2.

---

## 📊 Registro y Auditoría de Datos

Para encontrar nuevos patrones, cada trade en `trades.db` ahora guarda:
1.  **Razonamiento AI**: El texto completo de por qué la IA tomó la decisión (Elliott, RSI, Psicología).
2.  **Contexto Macro**: El valor exacto de la dominancia y el sesgo semanal al momento de entrar.
3.  **Confluencia**: Un score de 0 a 5 que determina la "Confiabilidad" de la señal.

---

## 🛠️ Ciclo de Mejora (Feedback Loop)

Al final de cada sesión de 24 horas, realizaremos un **Deep Audit**:
1.  **Análisis de Fallas**: Revisaremos los trades con estado `LOST` y compararemos el `ai_analysis` con lo que realmente hizo el precio.
2.  **Detección de Contradicciones**: Si la técnica (RSI) decía una cosa y la macro otra, ajustaremos los *weights* de prioridad en el código.
3.  **Optimización**: Si un patrón (ej: Onda 3 de Elliott + USDT.D bajando) tiene un 90% Win Rate, lo haremos una "Regla de Oro" con ejecución agresiva.

---

**ESTADO ACTUAL**: Motor de Simulación V5.0 ACTIVO. 🏛️📈🛡️
