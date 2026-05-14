# Cost Baseline — Railway scalp_bot

Tracking de uso real de Railway para validar optimizaciones de costo.

## Snapshot pre-optimización (2026-05-13 / pre commit 8f485b5)

**Ciclo:** Apr 21 → May 21 (parcial, ~22 días)

| Recurso | Uso | $ | % del total |
|---------|-----|----|----|
| Memory | 26,696.83 GB-min | $6.18 | 97% |
| CPU | 234.38 vCPU-min | $0.11 | 2% |
| Egress | 1.10 GB | $0.055 | 1% |
| Volume | 2,900.92 GB-min | $0.01 | <1% |
| **Subtotal** | | **$6.35** | 100% |
| Hobby plan fee | | +$5.00 | |
| Hobby included | | -$5.00 | |
| Credits | | -$70.00 | |
| **Bill final** | | **$0.00** | |
| Estimado fin ciclo | | $7.61 | |

**RAM promedio:** 26,696 GB-min / 31,680 min = **~0.84 GB** (cuando solo 0.62 GB peak — discrepancia? ciclo parcial)

**Resource limits configurados:** 8 GB RAM / 6 vCPU (sobreasignado)

**Plan:** Hobby — Usage-based subscription

## Threads activos pre-optimización (8 threads)

- `scalp_bot` — main crypto loop (BTC/ETH/SOL/ZEC/TAO/DOGE/TON/HBAR)
- `swing` — Zenith 4H
- `telegram` — worker
- `stock` — Centinela (30+ stocks cada 15min)
- `commodities` — GOLD/OIL/NG/SLV/HG cada 15min ⚠️ stuck
- `manual_monitor` — posiciones manuales cada 30min ⚠️ idle
- `scalper_shorts` — DOGE/FIL/TAO futures cada 90s ⚠️ score=1/5
- `daily_report` — reporte diario

## Optimizaciones aplicadas

### Round 1 — commit 8f485b5 (2026-05-13)

Desactivados 3 threads muertos:
- `commodities_bot` (loopea sin disparar)
- `manual_positions_monitor` (sin posiciones)
- `scalper_shorts_bot` (score 1/5 nunca dispara, tenía ccxt futures propio)

Fix Telegram HTML: removido `<i>` wrapper en mensaje AI análisis.

**Ahorro estimado:** ~130-170 MB RAM (~$1.30-1.70/mes)

### Round 2 — commit eb6b2a1 (2026-05-13)

- `_alert_cache` fix leak en `stock_analyzer.py`: pop entries en TP/SL + safety cap >100
- `TTL_INDICATORS` 300s → 600s (Binance OHLCV calls -50%)
- Telegram worker `sleep(5)` → `sleep(15)` (17,280 → 5,760 calls/día -67%)

**Ahorro estimado:** memory steady-state vs growing, egress ~30-40% menos

## Targets a validar (revisar 2026-05-20 y 2026-06-13)

| Métrica | Pre | Target post | Status |
|---------|-----|-------------|--------|
| Memory minutely GB | 26,696 / 22d | ~17,000 / 22d (-35%) | ⏳ |
| Egress GB | 1.10 / 22d | <0.80 / 22d (-25%) | ⏳ |
| Threads activos | 8 | 5 | ✅ |
| RAM avg | ~0.84 GB | <0.55 GB | ⏳ |

## Cómo medir

```bash
# Ver uso actual
open https://railway.com/workspace/usage

# Logs después de deploy
railway logs --tail 100
```

## Otras palancas si hace falta más ahorro

| Acción | $ ahorro est | Riesgo |
|--------|-------------|--------|
| Subir TTL_INDICATORS a 1200s (20min) | ~$0.30/mes | Medio (señales más lentas) |
| Eliminar Flask app si dashboard no se usa | ~$0.50/mes | Bajo (perder webhook TradingView) |
| Subir Centinela poll 15min → 30min | ~$0.20/mes | Bajo (alertas stock más lentas) |
| Cambiar plan a Hobby downgrade si bill <$5 | $5/mes (fee) | Bajo (perdemos features Pro) |
| Mover region US East (mismo precio) | $0 | None |
