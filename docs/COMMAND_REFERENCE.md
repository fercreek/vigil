# Zenith — Referencia de Comandos Telegram

> Estado: **v1.3.1** · Actualizado 2026-04-29

---

## Estado y análisis

| Comando | Descripción |
|---------|-------------|
| `/status` | Reporte de sentimiento global + Cuadrilla Zenith bias |
| `/scan` | Escanea BTC/TAO/ZEC para el mejor setup técnico |
| `/params` | Muestra thresholds activos (RSI, confluence, regime, SENTINEL) |
| `/macro` | Reporte macro: SPY / DXY / VIX / Oil / BTC.D / USDT.D |
| `/intel` | Inteligencia social (sentimiento Twitter/Reddit por símbolo) |
| `/regime` | Régimen de mercado actual por símbolo (TRENDING/RANGING/VOLATILE) |
| `/funding` | Funding rates actuales en Binance Futures |
| `/flow` | Flujo de liquidaciones (CoinGlass) |
| `/agents` | Panel de personas Cuadrilla Zenith |
| `/commodities` | Estado del bot de commodities (GOLD + OIL) |
| `/gold` | Alias de /commodities |
| `/oil` | Alias de /commodities |

---

## Trading (bot automático)

| Comando | Descripción |
|---------|-------------|
| `/positions` | Posiciones abiertas del bot con PnL flotante |
| `/portfolio` | Resumen portfolio + balance |
| `/balance` | Balance USDT en Binance Futures |
| `/stocks` | Watchlist PTS acciones US con precio live |
| `/stocks add TICKER` | Agregar ticker a watchlist |
| `/stocks rm TICKER` | Remover ticker de watchlist |
| `/winrate` | Win rate actual por símbolo y estrategia |
| `/audit` | Métricas de rendimiento (WR, trades, P&L) |
| `/metrics` | Métricas detalladas del sistema |
| `/leverage` | Leverage activo y límites de riesgo |
| `/risk` | Estado del circuit breaker y drawdown diario |

---

## Posiciones manuales (v1.3.0+)

| Comando | Descripción |
|---------|-------------|
| `/manual` | P&L actual + recomendación de todas las posiciones manuales |
| `/manual_tp SYM` | Marcar TP completo (cierra posición en monitor) |
| `/manual_tp SYM 50` | Tomar 50% de ganancias (partial) |
| `/manual_sl SYM` | Marcar SL hit |
| `/manual_be SYM` | Anotar que SL fue movido a break even |
| `/manual_off SYM` | Desactivar monitoreo (posición sigue abierta) |
| `/manual_add SYM ENTRY` | Agregar nueva posición al monitor |

---

## Control y configuración

| Comando | Descripción |
|---------|-------------|
| `/pause` | Pausar ejecución de alertas (análisis sigue corriendo) |
| `/resume` | Reanudar ejecución |
| `/mode paper` | Cambiar a modo paper trading |
| `/mode live` | Cambiar a modo live |
| `/verbose on` | Activar output Cuadrilla full (revierte SENTINEL compact) |
| `/verbose off` | Desactivar verbose — vuelve a compact |
| `/circuit` | Ver estado circuit breaker |
| `/circuit_reset` | Reset manual del circuit breaker |
| `/health` | Estado de los threads (heartbeats) |

---

## Correcciones de trades

| Comando | Descripción |
|---------|-------------|
| `/correct SYM` | Marcar trade como WON manualmente |
| `/wrong SYM` | Marcar trade como LOST manualmente |
| `/setsl SYM PCT` | Ajustar SL de trade abierto (PCT = % desde entry) |
| `/settp SYM PCT` | Ajustar TP de trade abierto |
| `/close SYM` | Cerrar trade abierto manualmente |
| `CERRAR SYM` | Alias en español de /close |

---

## Análisis avanzado

| Comando | Descripción |
|---------|-------------|
| `/scan` | Multi-signal scan — mejor setup en BTC/TAO/ZEC |
| `/bitlobo SYM` | Opinión BitLobo basada en niveles del watchlist |
| `/bitlobo SYM TF` + foto | Análisis BitLobo de gráfica enviada |
| `/add_chart SYM TF` + foto | Guardar niveles de gráfica en watchlist |

---

## Diagnóstico

| Comando | Descripción |
|---------|-------------|
| `/logs` | Últimas 20 líneas del log del bot |
| `/logs N` | Últimas N líneas |
| `/budget` | Consumo de API de IA (target ≤ $10/mes) |

---

## Estrategias activas

| Estrategia | Estado | Descripción |
|-----------|--------|-------------|
| V1-TECH LONG | ✅ Activa | RSI + BB + EMA200, confluencia ≥ 4 |
| V1-SHORT | ❌ Kill switch | `V1_SHORT_ENABLED = False` — 4.3% WR |
| V2-AI | ✅ Activa | Gemini bias institucional |
| V4-EMA | ✅ Activa | Mean reversion bounce en EMA200 |
| V5-MOMENTUM | ✅ Activa | RSI midline cross + RVOL |
| TAO trading | ❌ Kill switch | `TAO_TRADING_ENABLED = False` — 3.1% WR |
| GOLD SHORT | ❌ Suprimido | Gold bull lock activo (precio > $2,500) |
| OIL SHORT | ❌ Suprimido | Bloqueado en régimen VERDE (SP500 > 7,000) |

Ver `docs/AGENTS_AND_KILLS.md` para historial completo de kills.
