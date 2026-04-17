# Zenith Trading Suite — Strategy v4.2

Bot personal de trading algorítmico para Binance. Opera BTC, ZEC, SOL + commodities (GOLD, OIL).
Análisis técnico híbrido + IA (Gemini) + filtros de calidad basados en datos reales.

**Estado:** Activo | **Iteración:** `v4.2` | **WR target:** 62% | **Símbolos activos:** ZEC, BTC, SOL, GOLD, OIL

---

## Estado del sistema (Apr 2026)

| Símbolo | Estado | Razón |
|---------|--------|-------|
| BTC | Activo | Filtros SIM D2 activos |
| ZEC | Pausado (consecutive-loss guard) | 4 pérdidas SWING consecutivas |
| SOL | Activo | — |
| TAO | Kill switch OFF | 0% WR en 28 trades históricos |
| GOLD | Activo | Commodity strategy |
| OIL | Activo | Commodity strategy |
| V1-SHORT | Kill switch OFF | 0% WR en 16 trades históricos |

---

## Win Rate — Historial de mejoras

Análisis sobre 77 trades reales (Mar-Abr 2026):

| Iteración | Filtros | WR | Commit |
|-----------|---------|-----|--------|
| Baseline | ninguno | 18.2% | — |
| v4.0 | Mighty Snail (ADX, BB, RVOL, RSI) | — | `98ff7cd` |
| v4.1 | Kill switches + SIM D2 hour filter | 50.0% | `8c19d5e` |
| **v4.2** | + EMA50 trend + consecutive-loss guard | **~62% proyectado** | `307d225` |

**Target real:** 60-65% WR con R:R 1.5 = break-even en 40%, edge real en +20pp.
**80% WR = overfitting** en muestras <200 trades.

---

## Cómo arrancar

```bash
cd /Documents/ideas/scalp_bot
./venv/bin/python main.py
```

## Filtros activos (v4.2)

### Horas bloqueadas (UTC) — 0% WR histórico
`01, 04, 06, 10, 11, 14, 15, 16, 17, 20`

### Entry guards por ciclo
1. **Hour filter** — bloquea entradas en horas con 0% WR histórico
2. **EMA50 trend** — LONG solo si precio > EMA50 en 4H (swing_bot)
3. **Consecutive-loss guard** — pausa símbolo tras 2 pérdidas SWING seguidas
4. **Time exit** — cierra trades a las 36h si no llegaron a TP/SL
5. **Circuit breaker** — pausa global tras X pérdidas consecutivas
6. **FOMC filter** — reduce señales en ventana FOMC
7. **Funding rate** — bloquea si funding extremo (crowded trade)

---

## Documentación

- [CHANGELOG.md](CHANGELOG.md) — Historial de iteraciones con simulaciones
- [docs/STRATEGY_RULES.md](docs/STRATEGY_RULES.md) — Reglas de la estrategia
- [docs/ZENITH_MANIFESTO_V10.md](docs/ZENITH_MANIFESTO_V10.md) — Filosofía y evolución V1-V10
- [docs/COMMAND_REFERENCE.md](docs/COMMAND_REFERENCE.md) — Comandos Telegram
- [docs/SIMULATION_GUIDE.md](docs/SIMULATION_GUIDE.md) — Cómo correr simulaciones
