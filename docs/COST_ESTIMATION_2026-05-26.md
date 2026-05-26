# Cost Estimation API — Post Sprint 2026-05-26

> Estimación del gasto mensual de APIs tras 37+ specs implementados.
> Budget configurado bot: **$10/mes** (constante `MAX_MONTHLY_BUDGET_USD` en `ai_budget.py`).

## Resumen Ejecutivo

| Provider | Estimado mensual | % Budget |
|----------|------------------|----------|
| **Gemini Flash 2.5** | $0.40 - $1.50 | 4 - 15% |
| **Gemini Grounding** | $0.015 | <1% |
| **Anthropic Claude** | $0 | 0% (SDK no instalado prod) |
| **Externas (free tier)** | $0 | 0% |
| **TOTAL** | **~$0.50 - $1.50** | **5 - 15%** |
| **Margen libre** | $8.50 - $9.50 | 85 - 95% |

## Breakdown por endpoint

### 1. Cuadrilla Zenith Debate (`get_ai_consensus`)

Llamada por **cada alert** V3/V2-AI/V4/SWING. Spec 017+017.5 inyecta INTEL block.

| Métrica | Valor |
|---------|-------|
| Prompt input | ~800 tok base + 300 tok INTEL + 200 tok memoria = ~1300 |
| Output | ~500 tok |
| Frecuencia | 5-10 alerts/día post-gates Spec 016 |
| Tokens/día | 5 × (1300 + 500) = 9000 |
| Costo/día | (1300 × 5 × $0.075/1M) + (500 × 5 × $0.30/1M) = $0.00125 |
| **Costo/mes** | **~$0.04** |

### 2. Sentinel Compact (`get_sentinel_report_compact`)

Llamada por sentinel ZEC + otros cripto. Spec 005 Pydantic activo.

| Métrica | Valor |
|---------|-------|
| Prompt input | ~277 tok (medido) |
| Output | ~500 tok |
| Frecuencia | ~30 sentinels/día (cripto ciclo) |
| Tokens/día | 30 × 777 = 23,310 |
| Costo/día | input $0.0006 + output $0.0045 = $0.005 |
| **Costo/mes** | **~$0.15** |

### 3. Panorama Horario (`get_hourly_panorama`)

4 personas en paralelo. Spec 018 grounded search cache.

| Métrica | Valor |
|---------|-------|
| Prompt input | ~600 tok × 4 personas = 2400 |
| Output | ~200 tok × 4 = 800 |
| Frecuencia | 12 calls/día (c/2h) |
| Tokens/día | 12 × (2400 + 800) = 38,400 |
| Costo/día | input $0.002 + output $0.003 = $0.005 |
| **Costo/mes** | **~$0.15** |

### 4. BitLobo Vision (manual)

Análisis imagen gráficas via `/bitlobo` y `/bitlobomulti` (Spec 011+011.5).

| Métrica | Valor |
|---------|-------|
| Prompt input | ~558 tok + 258 tok/imagen |
| Output | ~400 tok |
| Frecuencia | 10 manual/día estimado |
| Tokens/día | 10 × (816 + 400) = 12,160 |
| Costo/día | input $0.0006 + output $0.0036 = $0.004 |
| **Costo/mes** | **~$0.12** |

### 5. Multi-symbol Event Detector (`get_top_setup`)

Ocasional, cuando se busca setup cross-asset.

| Métrica | Valor |
|---------|-------|
| Prompt input | ~400 tok |
| Output | ~300 tok |
| Frecuencia | 1-2/día |
| **Costo/mes** | **~$0.01** |

### 6. Grounded Search Panorama (Spec 018)

Cap 5/día, cache 1h. 1 query real/día (12 panoramas × 1h cache).

| Métrica | Valor |
|---------|-------|
| Queries reales | 1/día |
| Costo grounding | $0.50 / 1k queries |
| **Costo/mes** | **~$0.015** |

### 7. Multi-image BitLobo Spec 011.5

Manual via `/bitlobomulti`. Sin frecuencia high.

| Métrica | Valor |
|---------|-------|
| Prompt input | 600 tok + 258 × 5 imagenes max = ~1890 |
| Output | 600 tok max |
| Frecuencia | <5/día (Fernando manual) |
| **Costo/mes** | **~$0.05** |

## Total mensual

```
Cuadrilla Zenith:          $0.04
Sentinel Compact:          $0.15
Panorama Horario:          $0.15
BitLobo Vision (manual):   $0.12
Multi-symbol setup:        $0.01
Grounded Search:           $0.015
Multi-image BitLobo:       $0.05
                          ─────
Total estimado:            $0.53 / mes
```

## Escenarios

### Conservador (volúmenes actuales)

**$0.50 / mes** = **5% del budget**

### Realista (mid-volume cripto)

| Variable | Cambio |
|---------|--------|
| V3 alerts pasando gates | 5 → 15/día (3x) |
| Sentinel cycles | 30 → 60/día |
| Panorama | sin cambio (fijo c/2h) |

**$1.00 / mes** = **10% del budget**

### Pesimista (busy mode FOMC + cripto volátil)

| Variable | Cambio |
|---------|--------|
| V3 alerts | 30/día |
| Sentinels | 100/día (más símbolos activos) |
| Stocks alerts | 20/día (Spec 023.5 + 023.6 trigger más) |
| BitLobo manual | 30/día (Fernando debug) |

**$2.50 - $3.00 / mes** = **25-30% del budget**

## Drivers de costo

### Reducen costo

- **HMM cache Spec 009.6** TTL 15min → 1 fit/15min vs 4 calls/symbol/cycle
- **CVD cache 60s** → 1 fetch/min vs N por strategy
- **Social cache 30min** → 1 query/30min vs N por trigger
- **Whale cache 5min** → 1 Etherscan call/5min
- **Grounded cap 5/día** + cache 1h → max 5 queries
- **Gates Spec 016** filtran V3 alerts inútiles
- **Pydantic** elimina re-tries por parseo malformado

### Incrementan costo

- **Cuadrilla en TODAS strategies** (Spec 017.5) — 4x si todas las strategies disparan
- **BitLobo multi-image** (Spec 011.5) — 258 tok/imagen × 5 = 1290 input por call
- **Múltiples símbolos cripto activos** (BTC + ETH + SOL + ZEC + TAO)
- **Stocks watchlist** (~20 tickers × intel modules)
- **Stocks options OI** (Spec 023.6) — yfinance ratio + cache 30min

## Limites y alertas

- `ai_budget.MAX_MONTHLY_BUDGET_USD = 10.00`
- Cuando llega a 80% → log warning
- Cuando llega a 100% → bloquea nuevas llamadas IA (`can_use_ai()` returns False)
- Endpoint `/api/ai_budget` muestra status realtime

## APIs gratis

| API | Costo | Limit |
|-----|-------|-------|
| Binance Spot/Futures | $0 | 1200 weight/min |
| yfinance | $0 | rate-limited (best effort) |
| Etherscan | $0 | 5 calls/sec (con API key recomendado) |
| BscScan | $0 | igual Etherscan |
| Reddit (praw) | $0 | 60 requests/min |
| Google Trends (pytrends) | $0 | rate-limited |
| Glassnode Community | $0 | tier limited |

## Recomendaciones

1. **No habilitar Anthropic Claude** sin medir gain. Cuesta más, Gemini Flash 2.5 ya cubre 95% del bot.
2. **Monitorear `/api/ai_budget` semanal** primeras 4 semanas post-deploy.
3. **Si excede $5/mes** → reducir frecuencia Panorama de 2h a 4h (cut 50% panorama cost).
4. **NO bajar caches TTL** sin necesidad — cada cache absorbe llamadas redundantes.
5. **Considerar bumpear cap grounded** a 10/día solo si análisis ROI confirma valor.

## Validación

Tras 7 días en producción, comparar:

```bash
# Real spend via DB
sqlite3 trades.db "
SELECT
  DATE(ts) as date,
  call_type,
  SUM(cost_usd) as cost
FROM ai_calls
WHERE ts > date('now', '-7 days')
GROUP BY date, call_type
ORDER BY date DESC
"
```

Si real > 2x estimación → investigar:
- Cache miss ratios
- Frecuencia alerts no esperada
- Endpoint con tokens out > esperado
