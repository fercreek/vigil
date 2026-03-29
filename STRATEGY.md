# Trading Strategy Log: Versión 1 (V1)

Este documento registra la evolución del algoritmo para mantener un versionado claro y científico de los cambios.

## Especificaciones de V1 (Vigente desde: 28 Marzo 2026)

### 1. Indicadores de Confirmación
- **RSI 1H**: Define la tendencia macro (Sobreventa < 30 / Sobrecompra > 70).
- **RSI 15M**: Gatillo de entrada (V1: 30/70).
- **USDT Dominance**: Filtro macro (> 8.10% para Short / < 8.00% para Long).

---

## Especificaciones de V2 (Vigente desde: 29 Marzo 2026) 🚀

Esta versión es el resultado del **Análisis Científico con Pandas** de las últimas 48h. Optimiza la entrada en mercados de baja volatilidad.

### 1. Indicadores (Optimización)
- **RSI 15M (Gatillo Dinámico)**: 
    - **Short**: RSI >= 60 (Antes 70).
    - **Long**: RSI <= 40 (Antes 30).
- **Bollinger Bands (20, 2)**: 
    - **Confirmación Short**: El precio debe estar por encima de la Banda Superior (`Upper Band`).
    - **Confirmación Long**: El precio debe estar por debajo de la Banda Inferior (`Lower Band`).

### 2. Lógica de Ejecución
El bot ahora requiere **Triple Validación**:
1. Precio en Nivel Dinámico (Pivot Point R1/S1).
2. RSI en Umbral V2 (60/40).
3. Precio rompiendo Bandas de Bollinger (Confirmación de volatilidad).

---

## Resultados del Backtesting (V2)
- **Análisis**: Los datos sugieren que con este ajuste se habrían capturado **3 entradas** en ETH ayer que la V1 ignoró, manteniendo un riesgo controlado.

## Próximos Experimentos (V3)
- [ ] Implementar **Trailing Stop Loss** basado en ATR (Average True Range).
- [ ] Integrar **Sentiment Analysis** de Twitter/X para filtrar pumps falsos.
