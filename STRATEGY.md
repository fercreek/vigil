# Trading Strategy Log: Versión 1 (V1)

Este documento registra la evolución del algoritmo para mantener un versionado claro y científico de los cambios.

## Especificaciones de V1 (Vigente desde: 28 Marzo 2026)

### 1. Indicadores de Confirmación
- **RSI 1H**: Define la tendencia macro (Sobreventa < 30 / Sobrecompra > 70).
- **RSI 15M**: Actúa como gatillo de entrada (Cruce arriba de 30 para Long / Abajo de 70 para Short).
- **USDT Dominance**: Filtro macro (> 8.10% para Short / < 8.00% para Long).

### 2. Niveles de Precio (Dinámicos)
- **Soportes/Resistencias**: Basados en **Pivot Points Diarios** (High, Low, Close de ayer).
- **Entrada Short**: Precio >= Resistencia 1 (R1).
- **Entrada Long**: Precio <= Soporte 1 (S1).
- **Take Profit 1**: Punto Pivote (P) + Stop Loss a Break Even.
- **Take Profit 2**: Soporte/Resistencia opuesta (S1/R1).

### 3. Gestión de Riesgo
- **Riesgo por trade**: 2% del balance inicial ($1,000).
- **Stop Loss**: 1% de distancia desde la entrada o ATR-based.

---

## Resultados del Backtesting (V1)
- **Periodo**: Últimas 48 horas.
- **Resultado**: 0 Operaciones encontradas.
- **Análisis**: El mercado estuvo muy lateral. El RSI nunca llegó a los extremos 70/30 mientras el precio tocaba los niveles de R1/S1. El filtro fue demasiado estricto para la volatilidad de ayer.

## Próximos Experimentos (V2)
- [ ] Relajar umbrales de RSI a 60/40.
- [ ] Implementar **Bollinger Bands** para detectar explosiones de volatilidad.
- [ ] Auto-ajustar niveles de RSI basados en el Percentil de las últimas 24h.
