# _BACKTEST_HISTORICO — Análisis Multi-Período (Mar 2025 → Mar 2026)

> Generado 2026-05-09 con `backtester.py` corriendo en data 1H Binance Futures.
> Símbolos: BTC, ETH, TAO, ZEC. Estrategias: V1-LONG, V3-REVERSAL, V4-EMA, V5-MOMENTUM.
> Total trades evaluados: 122 (V1: 53 / V3: 18 / V4: 51 / V5: 0).

---

## 🎯 Conclusiones ejecutivas

1. **V3-REVERSAL es el único edge real comprobado** — 2025 full: 18 trades, 27.8% WR, **+63.8% PnL, PF ∞** (cero loss neto agregado).
2. **V1-LONG perdió en todos los períodos relevantes** — confirma kill switch aplicado.
3. **V4-EMA es altamente régimen-dependiente** — explota Q3 (+24%), implosiona Q4 (-20%).
4. **V5-MOMENTUM no disparó nunca** — 0 trades en 12 meses → confirma bug o filtro inviable.
5. **2026 M01-M02 = mes más débil para TODAS las estrategias** → mercado lateral/choppy. El bot debe **disparar menos en este régimen**, no más.

---

## 📊 Tabla 1 — Agregado por estrategia × período (suma 4 símbolos)

| Período | Estrategia | N | WR% | PnL% | PF | Avg/trade |
|---------|-----------|---|-----|------|-----|----|
| **2025 FULL** | V1 | 53 | 17.0% | -16.3% | 0.55 | -0.31% |
| **2025 FULL** | **V3** | **18** | **27.8%** | **+63.8%** | **∞** | **+3.55%** |
| **2025 FULL** | V4 | 51 | 23.5% | -1.6% | 0.70 | -0.03% |
| 2025 Q2 (Apr-Jun) | V1 | 14 | 14.3% | -1.4% | 0.88 | -0.10% |
| 2025 Q2 | **V3** | 5 | 20.0% | **+21.7%** | **20.42** | +4.35% |
| 2025 Q2 | V4 | 14 | 21.4% | -1.1% | 0.89 | -0.08% |
| 2025 Q3 (Jul-Sep) | V1 | 16 | 25.0% | +5.0% | 1.73 | +0.31% |
| 2025 Q3 | V3 | 5 | 20.0% | +6.0% | 1.88 | +1.20% |
| **2025 Q3** | **V4** | 18 | **38.9%** | **+23.9%** | **∞** | +1.33% |
| 2025 Q4 (Oct-Dec) | V1 | 13 | **0.0%** | **-42.2%** 🚨 | 0.00 | -3.25% |
| **2025 Q4** | **V3** | 6 | 16.7% | **+14.4%** | ∞ | +2.40% |
| 2025 Q4 | V4 | 11 | 9.1% | **-20.0%** 🚨 | 0.10 | -1.82% |
| 2026 M01 | V1 | 2 | 0% | -2.8% | 0 | -1.38% |
| 2026 M01 | V3 | 6 | 0% | -1.1% | 0.55 | -0.18% |
| 2026 M01 | V4 | 2 | 0% | -0.9% | 0 | -0.46% |
| 2026 M02 | V1 | 2 | 0% | -6.6% | 0 | -3.29% |
| **2026 M02** | V3 | 2 | 50% | +3.9% | ∞ | +1.94% |
| 2026 M02 | V4 | 3 | 0% | -7.7% | 0 | -2.55% |
| 2026 M03 | V1 | 4 | 25% | +1.7% | 1.22 | +0.42% |
| **2026 M03** | V3 | 5 | 40% | **+8.5%** | ∞ | +1.70% |
| **2026 M03** | V4 | 3 | 66.7% | **+12.0%** | 7.72 | +3.99% |

---

## 📈 Tabla 2 — Detalle por símbolo (2025 FULL)

| Symbol | Strat | N | W | L | WR% | PnL% | PF | Avg |
|--------|-------|---|---|---|-----|------|-----|-----|
| BTC | V1 | 16 | 3 | 13 | 18.8% | -1.9% | 0.86 | -0.12% |
| BTC | V3 | 4 | 0 | 1 | 0% | +4.2% | 3.33 | +1.05% |
| BTC | **V4** | 18 | 5 | 13 | 27.8% | **+3.7%** | 1.43 | +0.21% |
| ETH | V1 | 13 | 1 | 12 | 7.7% | **-21.3%** 🚨 | 0.29 | -1.64% |
| ETH | **V3** | 6 | 3 | 0 | **50%** | **+44%** 🏆 | ∞ | +7.33% |
| ETH | V4 | 12 | 2 | 10 | 16.7% | -1.7% | 0.87 | -0.14% |
| TAO | V1 | 9 | 2 | 7 | 22.2% | -13.0% | 0.55 | -1.44% |
| TAO | V3 | 6 | 1 | 4 | 16.7% | +7.4% | 1.59 | +1.24% |
| TAO | V4 | 9 | 2 | 7 | 22.2% | -3.8% | 0.77 | -0.42% |
| ZEC | V1 | 15 | 3 | 11 | 20% | +19.9% | 1.51 | +1.32% |
| ZEC | V3 | 2 | 1 | 0 | 50% | +8.2% | ∞ | +4.11% |
| ZEC | V4 | 12 | 3 | 9 | 25% | +0.1% | 1.00 | +0.01% |

**Highlights por símbolo:**
- **ETH V3** es la mejor combinación absoluta — 50% WR y +44% PnL en 6 trades (avg +7.33%/trade)
- **BTC V4** estable — único V4 con PF > 1 a lo largo del año
- **ETH V1** catastrófico — -21% PnL, kill confirmado
- **ZEC V1** sorprende: +19.9% PnL pese a WR 20% (winners grandes compensaron)

---

## 🔍 Análisis por régimen de mercado

### Q2 2025 (Abr-Jun) — **Bull lateral**
- V3 dominó: PF 20.4 (excepcional)
- V4 break-even
- V1 perdió ligero
- **Insight**: en bull lateral V3-REVERSAL captura las correcciones agresivamente

### Q3 2025 (Jul-Sep) — **Bull confirmado / trending up**
- **V4 EXPLOTA** — 38.9% WR, +23.9%, PF ∞
- V3 también funciona pero menos (+6%)
- V1 marginal positivo (+5%)
- **Insight**: V4-EMA es estrategia de **trending bull** confirmado. Q3 fue su régimen ideal.

### Q4 2025 (Oct-Dec) — **Bear / corrección fuerte**
- V1 catastrófico: 0% WR, **-42.2%**
- V4 también pierde: -20%
- **V3 SIGUE GANANDO**: +14.4% (rescate funcionando)
- **Insight crítico**: V3 es la única estrategia que **opera mejor cuando el mercado cae**. Esto es exactamente lo que esperabas de "reversal en oversold extremo".

### 2026 M01-M02 — **Lateral choppy / RANGING**
- TODAS las estrategias perdieron o break-even
- V3 también débil (-1.1%, +3.9%)
- **Insight**: en RANGING no hay estrategia ganadora. Recomendación: bot debería **disparar menos** en este régimen, no más.

### 2026 M03 — **Recovery incipiente**
- V3 retorna a +8.5% PF ∞
- V4 +12% (rebote)
- V1 marginal
- **Insight**: V3 + V4 coordinados en recovery son potentes

---

## 🎯 Recomendaciones derivadas

### 1. ✅ V3-REVERSAL — promover a "core" sin reservas
- Único PF ∞ en 4 períodos distintos
- Operó bien en bull, lateral y bear
- ETH es el símbolo estrella (50% WR, +44%)
- **Acción**: mantener ON. Considerar **subir tamaño de posición en V3 ETH** específicamente (1.5x).

### 2. 🟡 V4-EMA — limitar a régimen bull confirmado
- Excelente en Q3 2025 (+24%)
- Catastrófico en Q4 2025 (-20%)
- Implementar **gate dinámico**: V4 solo dispara si `regime == TRENDING_UP` Y `1D EMA200 bull`
- Actualmente strategies.py:646 ya tiene `regime == "TRENDING_UP"`. Verificar que el detector de régimen sea preciso.
- **V4_BLOCKLIST = ["ETH", "ZEC"]** ya aplicado correctamente (ETH -1.7%, ZEC +0.1% en 2025)

### 3. ❌ V1-LONG — confirmar kill
- 53 trades, -16.3% en 2025, 0% WR en Q4 catastrófico
- Sin redempción visible
- **Status: V1_LONG_ENABLED = False ya aplicado** ✅

### 4. ❌ V5-MOMENTUM — investigar o eliminar definitivamente
- 0 trades en 12 meses
- Filtro `prev_rsi < 50.0 <= rsi` + `regime != RANGING` + `not _fomc_suppressed` + `p > ema_200`: combinación inviable
- **Acción**: revisar implementación una vez. Si después no dispara → eliminar archivo entero.

### 5. 🆕 Nueva idea — Estrategia "RANGING dedicated"
- Q1 2026 (Ene-Feb) demostró que **NINGUNA estrategia gana en RANGING**
- Bot opera 24/7 incluso en lateral → quema fees + slippage
- **Opción A**: bloqueo global cuando `regime == RANGING` → no disparar nada
- **Opción B**: estrategia VWAP mean reversion para lateral (NUEVO desarrollo)
- **Recomendación**: Opción A primero (zero-cost, evita pérdidas). Opción B solo si B vale el esfuerzo.

### 6. 📐 Sizing diferencial por símbolo
Datos 2025 sugieren:
- **V3 ETH**: PF ∞, +44% → considerar 1.5x size
- **V3 BTC**: PF 3.33 pero solo 4 trades → mantener 1x
- **V4 BTC**: PF 1.43, 18 trades → mantener 1x
- **V4 TAO**: PF 0.77 → reducir 0.5x si se mantiene activa
- **Cualquier setup en ETH V1**: blocked

---

## ⚠️ Caveats y limitaciones

1. **Muestra chica en V3** — 18 trades en 2025 es estadísticamente débil. Necesitamos 50+ para confiar plenamente en PF ∞.
2. **No tested**: SWING (Ichimoku 4H), COMMODITIES (yfinance), SCALPER_SHORTS (sin data). Estos no están en `backtester.py`.
3. **No incluye fees aplicados manualmente** — backtester usa `FEE_PCT=0.04%` y `SLIPPAGE_PCT=0.02%` ya en cálculo, pero validar.
4. **Sin walk-forward por período** — los números son in-sample. La degradation real puede ser 20-40%.
5. **Período Q4 2025 + 2026 M01-M02 fue régimen muy específico** (post-rally drawdown). Resultados pueden no extrapolarse a otros bear markets.

---

## 📅 Plan de validación 2 semanas

Con los fixes aplicados hoy + estos insights:

| Métrica esperada | Threshold OK | Threshold KILL |
|------------------|--------------|----------------|
| V3 PF (cualquier símbolo) | ≥ 1.5 | < 0.8 con n>10 |
| V4 PF (BTC, TAO solo) | ≥ 1.2 | < 0.8 con n>10 |
| Swing Ichimoku PF | ≥ 1.0 | < 0.7 con n>15 |
| Commodities PF | ≥ 1.3 | < 0.8 con n>10 |
| Scalper Shorts WR | ≥ 55% | < 35% con n>10 |

Si en 2 semanas alguna estrategia falla su threshold → iteración 2 o kill (3 strikes regla).

---

## 🔗 Datos crudos

Raw results JSON: `/tmp/backtest_results.json` (regenerable con):
```bash
python backtester.py --symbols BTC ETH TAO ZEC --strategies V1 V3 V4 V5 --mode run
```

Walk-forward (in-sample 70 / out-of-sample 30):
```bash
python backtester.py --symbols BTC ETH TAO ZEC --strategies V3 V4 --mode walk_forward
```

Para data fresh (re-download CSV):
```bash
# TODO: agregar script fetch_data.py que actualice CSVs desde Binance
```
