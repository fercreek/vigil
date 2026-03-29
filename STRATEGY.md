# Trading Strategy Log: Versión 1 (V1)

Este documento registra la evolución del algoritmo para mantener un versionado claro y científico de los cambios.

## Especificaciones de V1 (Vigente desde: 28 Marzo 2026)

### 1. Indicadores de Confirmación
- **RSI 1H**: Define la tendencia macro (Sobreventa < 30 / Sobrecompra > 70).
- **RSI 15M**: Gatillo de entrada (V1: 30/70).
- **USDT Dominance**: Filtro macro (> 8.10% para Short / < 8.00% para Long).

---

## Especificaciones de V1.5.0 (Vigente desde: 29 Marzo 2026) 💎

Esta versión introduce el **Sistema de Confluencia Total**, unificando indicadores estáticos y dinámicos bajo una puntuación de convicción.

### 1. Sistema de Puntuación (Score 0-5)
- **RSI (15m/1h)**: Extremas < 30 / > 70 (+2), Sensibles < 40 / > 60 (+1).
- **EMA 200 (Tendencia)**: Precio en el lado correcto del trend (+1).
- **Bollinger (Volatilidad)**: Precio en zona Near Bands (+1).
- **Dominancia USDT (Macro)**: Dirección macro favorable (+1).

### 2. Tiers de Señales
- `💎 DIAMANTE`: 4-5 Puntos. Máxima probabilidad estadística.
- `🔥 ALTA CONVICCIÓN`: 3 Puntos. Señales operables con tendencia.
- `⚡ ESTÁNDAR`: < 3 Puntos. Solo avisos secundarios.

### 3. Consenso Híbrido (AI Master)
- Cada señal técnica es validada por **Gemini**, quien recibe el score técnico para decidir (CONFIRM/REJECT).
- El sistema lanza la alerta definitiva como `🔹💎🔹 CONSENSU MASTER`.

---

## Resultados del Backtesting (V1.5.0)
- **Enero (Seguridad)**: Protegido por filtro EMA 200 (PnL Neutro).
- **Febrero/Marzo (Rentabilidad)**: Win Rate > 60% en señales de 4+ puntos.

## Próximos Experimentos (V1.6)
- [ ] Implementar **Filtro de Apertura (Volatility Spikes)** basado en ATR intradía.
- [ ] Refinar los niveles de Dominancia de USDT según la estacionalidad semanal.
