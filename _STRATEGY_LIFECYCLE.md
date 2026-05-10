# _STRATEGY_LIFECYCLE — Política de iteración + matriz régimen

> Filosofía: **calidad > cantidad**. No tenemos edge probado todavía. Step by step.
> Última actualización: 2026-05-09

---

## 🎯 Política — 3 strikes y muere

Cada estrategia tiene un máximo de **3 iteraciones** para demostrar edge. Si después de la 3ra no hay mejora medible → **kill switch**.

### Definición de "edge probado":

Una estrategia tiene edge cuando, con muestra ≥ 20 trades cerrados:
- **Profit Factor ≥ 1.3** (gross_profit / gross_loss)
- **Expectancy positiva** (>0% por trade)
- **WR mínima** según su perfil (ver matriz abajo)
- Resiste **walk-forward validation** con degradation < 30%

### Definición de "iteración":

Una iteración = cambio de parámetro o lógica + 14 días de data nueva o backtest 365d.

Cambios menores (tweaks de threshold) NO cuentan como iteración separada — agrupar en una sola.

---

## 📊 Matriz Estrategia × Régimen × Timeframe (auditoría 2026-05-09)

```
                    BULL_TREND  BEAR_TREND  RANGING  VOLATILE  TF natural
V3-REVERSAL         🟡 whipsaw  ❌ losses   ❌       ✅ ideal   15m-1H
V4-EMA              🟡 marginal ❌ bloqueado ❌      ❌ pierde  15m-1H
SWING (Ichimoku)    🟡 marginal ❌ falsas   ❌       ❌         4H
COMMODITIES         ✅ ideal    🟡 marginal ⚪       ❌ spikes  1H
SCALPER_SHORTS      ❌ pierde   ⚪ neutral  ✅ ideal ✅ funciona 1H
```

**Leyenda:** ✅ ideal · 🟡 marginal · ⚪ neutral · ❌ pierde

### Conflictos detectados

1. **V3-REVERSAL ↔ V4-EMA** en BULL: ambos LONG → riesgo doble posición. Position guard mitiga pero no elimina conflicto lógico.
2. **RANGING sin cobertura sólida**: solo SCALPER_SHORTS lo cubre, pero sin data aún (recién deployado).
3. **VOLATILE doble cobertura**: V3 y SCALPER_SHORTS ambos disparan — no es problema si direcciones opuestas (V3 LONG / scalper SHORT).

---

## 🗂️ Estado actual de cada estrategia

### V3-REVERSAL ✅ KEEP (validado walk-forward)
- **Iteración:** 1 (vigente)
- **Backtest 365d:** 39 trades, 25.6% WR, **+80.6% PnL**
- **Walk-forward (May-9, train 70/test 30):**
  - BTC: train WR 50% → test 36.4% (deg -27%, ✅ robust)
  - TAO: train WR 25% → test 66.7% (deg +167%, ⚠️ variable pero positivo)
  - ETH: train WR 100% → test 57% (deg -43%, ⚠️ overfit pero test rentable)
  - ZEC: train 100% → test 100% (muestra muy chica)
- **Status:** ✅ Core. Edge confirmado en BTC/TAO. ETH overfit pero aún profitable OOS.
- **Mejora pendiente:** Hyperopt para optimizar `RSI_LONG_TAO_EXTREME=28` y `RSI_LONG_ZEC_EXTREME=26`

### V4-EMA 🟡 ITER 2 (post-walk-forward)
- **Iteración:** 1 → 2 (recomendado expandir blocklist)
- **Backtest 365d:** 61 trades, 23% WR, -0.8% PnL (break-even)
- **Walk-forward (May-9):**
  - BTC: train 28% → test 33% (deg +20%, ✅ robust)
  - TAO: train 22% → test 50% (variable pero +6.7% PnL OOS)
  - ETH: train 18% → test 0% (deg -100%, ⚠️ overfit)
  - ZEC: train 25% → test 0% (deg -100%, ⚠️ overfit)
- **Iteración 1 (May-9):** Aplicado `V4_BLOCKLIST=["ETH"]`
- **Iteración 2 (recomendado):** ampliar `V4_BLOCKLIST=["ETH","ZEC"]` — ZEC también overfit en walk-forward
- **Iteración 3 (kill si no mejora):** retirar
- **Decisión esperada:** 2026-05-23

### SWING (Ichimoku 4H) ⚠️ EN OBSERVACIÓN
- **Iteración:** 1 (vigente, recién parchada)
- **DB histórico:** 76 trades, 17.1% WR (auto-log contaminó)
- **Iteración 1 (May-9):** keyboard Activar/Skip en lugar de auto-log → ahora cuenta solo decisiones reales
- **Iteración 2 (si no mejora):** filtro DXY (igual que commodities) + bloquear shorts en RANGING
- **Iteración 3 (kill si no mejora):** retirar — Ichimoku 4H es buen indicador pero el setup actual no captura
- **Decisión esperada:** 2026-05-23

### COMMODITIES ✅ KEEP CON FIXES
- **Iteración:** 2 (post-fix)
- **DB histórico:** 12 trades, 25% WR (1 GOLD LONG 0/6 fue causa del bleed)
- **Iteración 1 (May-7):** market hours guard
- **Iteración 2 (May-9):** post-LOST cooldown 8h + 1D EMA200 filter para GOLD/SLV LONG
- **Status esperado:** WR debería subir a 40-50% si los fixes son correctos
- **Decisión final:** 2026-05-23

### SCALPER_SHORTS 🆕 IT 1 (sin data)
- **Iteración:** 1 (vigente, recién deployado)
- **Sin trades aún** — necesita acumular ≥ 20
- **Decisión inicial:** 2026-06-09 (4 semanas — más data necesaria)

### V1-LONG ❌ KILLED
- **Backtest:** 65 trades, 15.4% WR, **-34.1% PnL**
- **Status:** `V1_LONG_ENABLED = False` desde 2026-05-09
- **Razón:** sin edge en 4/4 símbolos del backtest

### V1-SHORT ❌ KILLED
- **Histórico:** 16 trades, 0% WR (Apr 2026)
- **Status:** `V1_SHORT_ENABLED = False` desde Apr 2026

### V5-MOMENTUM ❌ DISABLED (por bug)
- **Backtest:** 0 trades en 365d → bug o filtro muy restrictivo
- **Status:** `V5_ENABLED = False` desde 2026-05-09
- **Pendiente:** investigar implementación. Si filter `prev_rsi < 50.0 <= rsi` está bien, el problema es que requiere `regime != RANGING` AND `not _fomc_suppressed` AND price > EMA200 — combinación rara.

---

## 🚀 Mejores prácticas a adoptar (de Freqtrade/NFI/Jesse)

Análisis externo identificó 6 mejoras de alto ROI. **Ordenadas por esfuerzo creciente:**

### 1. ⚡ Activar `walk_forward()` (30 min) — `backtester.py:429`
Función ya existe pero nunca se invoca. Correrla en cada estrategia:
```bash
python3 -c "from backtester import Backtester; bt=Backtester(); bt.load_data('TAO'); print(bt.walk_forward('V3'))"
```
Reporta degradation train→test. Si V3 degrada > 30% → curve-fit, no es edge real.

### 2. 🐛 Fix bug Sharpe (15 min) — `metrics.py:38`
`sqrt(min(len(returns), periods_per_year))` debe ser `sqrt(len(returns))`.
Causa Sharpe inflado para strategies con < 365 trades/año.

### 3. 🎯 Multi-TF filter (2-3 h) — `indicators.py`
NFI usa RSI/EMA en 1h + 4h + 1d. Nosotros solo 1h.
Agregar `get_multi_timeframe_context(symbol)` → dict con `{rsi_1h, rsi_4h, rsi_1d}`.
Aplicar en V3-REVERSAL: solo entra si `rsi_4h < 50` (TF mayor confirma).

### 4. 🎲 Monte Carlo shuffles (2 h) — `backtester.py`
Reordenar trades aleatoriamente y verificar que el max drawdown no depende del orden. Detecta si V3 +80% es suerte temporal.

### 5. 🔧 Hyperopt-light (4-6 h) — manual
No migrar a Freqtrade completo. Hacer grid search interno:
```python
for rsi_thresh in [25, 27, 28, 30, 32]:
    for atr_sl in [1.5, 2.0, 2.5]:
        run_backtest(V3, rsi_thresh, atr_sl)
```
Encontrar combos óptimos para V3.

### 6. 🧠 Confluence combinator (2-3 h) — `strategies.py`
NFI tiene 27 buy signals combinables. Nosotros 4 estrategias separadas.
Refactor `check_strategies()` para emitir `(symbol, score, signal_id)` y disparar cuando `score ≥ 4` sin importar source.

---

## 📅 Próximos checkpoints

| Fecha | Acción |
|-------|--------|
| **2026-05-09** (hoy) | Aplicado: kill V1, kill V5, V4 blocklist, swing keyboard, commodities cooldown, daily_report PnL/PF/Expectancy |
| **2026-05-23** | Auditoría automática (remote routine `trig_01QjZVU9531oqK9pvNUoWSzF`) → revisar WR/PF post-fix de cada estrategia |
| **2026-06-09** | Decisión SCALPER_SHORTS (4 semanas data) + Iteración 2 de V4 si necesario |

---

## ❌ Lo que NO vamos a hacer

- **No agregar más estrategias** hasta validar las actuales
- **No migrar a Freqtrade/Jesse completo** — perder agilidad de Telegram debug
- **No pagar TradingView** hasta confirmar profitability (PF > 1.3) por 2 semanas
- **No tocar V3-REVERSAL** sin Hyperopt — es el único edge que tenemos

---

## 🧠 Filosofía operativa

> "No somos rentables todavía. Step by step. Iterar máximo 3 veces. Lo que no funciona muere. Lo que funciona se profundiza."

Métricas de éxito en orden de importancia:
1. **Profit Factor ≥ 1.3** (lo único que importa al final)
2. **Expectancy > 0% por trade** (sostiene el #1)
3. **WR consistente con perfil** (alta para scalp, baja para reversal)
4. **Walk-forward degradation < 30%** (no curve-fit)
5. **Drawdown máximo < 15%** (sobrevive al peor caso)

WR alone es métrica vanity. PnL real es lo que paga las cuentas.
