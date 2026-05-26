# Plan 023 — Intel a Stocks

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Decisiones técnicas

### 1. Solo Social Sentiment este spec (Spec 023.5 hará HMM)

HMM regime requiere yfinance adapter en `regime_hmm.detect_regime` (hoy fetch via ccxt binance_spot, no NYSE). Refactor scope > 1 día. Defer.

Social funciona inmediato porque `_SUBREDDITS_BY_SYMBOL` mapping permite cualquier ticker; solo agregar entradas para stock tickers.

### 2. Tag visual solo, no gate/boost

Stock alerts NO usan `conf_score` system (vienen de BitLobo manual signals). Boost no aplica. Gate (skip alert si EUPHORIA) sería demasiado agresivo para alerts manuales que Fernando ya curó.

Spec 023.5 backlog: si métricas validan que EUPHORIA stocks → top probable, considerar gate.

### 3. Subreddits sector-específicos

Cada ticker en `_SUBREDDITS_BY_SYMBOL` mapped a:
- `wallstreetbets` (always — captura retail euphoria/fear general)
- Sector sub: ej `nuclear` para OKLO/SMR/UUUU, `biotech_stocks` para XBI, `RocketLab` para RKLB
- Cuando aplica: ticker-específico sub (ej `PLTR`, `sofi_stock`, `teslainvestorsclub`)

### 4. Tag EUPHORIA vs FEAR distinta semántica

```python
EUPHORIA → 🔥 fade crowd, top probable
FEAR     → 💀 capitulación, opportunity
```

Fernando lee el tag y decide. NotebookLM 4 Prompt 1 #3 sugirió ambos signals son accionables (no solo EUPHORIA bearish).

### 5. Tag prepended después de _priority_tag, antes de header

Order en msg:
```
🔥 PRIORIDAD ALTA (Spec 003)
💀 Social: FEAR ... (Spec 023)
🚨 ALERTA DE ENTRADA: NVDA
```

Prioridad PTS primero (decisión Fernando-curated), social después (data context).

### 6. NO tag en ZONE_ALERT (BitLobo)

ZONE_ALERT ya tiene context BitLobo con su propia metodología (zonas verdes/rojas). Agregar social ruidoso. Solo ENTRY_ALERT (más actionable, mayor convicción).

## Verificación

- ✅ py_compile stock_analyzer.py + social_quant.py
- ✅ 16+ stocks tickers en `_SUBREDDITS_BY_SYMBOL`
- ✅ try/except envuelve social call
- Producción pendiente: próxima alerta NVDA/TSLA/OKLO con social tag visible

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(stocks): spec-023 social sentiment tag en stock entry alerts` |

## Backlog Spec 023.5

- HMM regime stocks: extender `regime_hmm.detect_regime` con yfinance adapter
  * Option A: `detect_regime(symbol, ..., df=None)` accept pre-fetched DataFrame
  * Option B: `detect_regime_stock(ticker, lookback_days=90)` separate function
  * Option C: refactor `_build_features` to be exchange-agnostic
- Gate stocks alerts por EUPHORIA (si métricas validan top probabilidad)
- Boost stocks "confluence" (necesita scoring system stocks-specific)
- Twitter/X sentiment via API (cuando esté disponible)
- Insider trading data Form 4 SEC
- ZONE_ALERT social tag (si validamos no es ruidoso)
