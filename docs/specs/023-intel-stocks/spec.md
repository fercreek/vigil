# Spec 023 — Intel Modules a Stocks (Social Sentiment)

> **Status:** CODE COMPLETE 2026-05-26
> **Owner:** Fernando
> **Severity:** P1 — cubre la mitad del bot (NYSE/NASDAQ)
> **Origen:** Roadmap Spec 023

## Contexto

Specs 013-021 wired intel modules a cripto V3-REVERSAL + Cuadrilla Zenith. `stock_analyzer.py:stock_watchdog` (Spec 002+003+004 alerts) NO ve estos signals — stocks alerts NVDA/TSLA/OKLO/etc operan solo con BitLobo zones + entry distance.

Spec 023 wire Social Sentiment para stocks (funciona por ticker symbol via Reddit subreddits stock-específicos).

HMM regime para stocks defer Spec 023.5 (requiere yfinance adapter en `regime_hmm.detect_regime`).

CVD y Whale on-chain NO aplican a stocks (Binance-only / Etherscan-only respectivamente).

## Goals

1. Extender `social_quant._SUBREDDITS_BY_SYMBOL` con stocks:
   - NVDA, TSLA, PLTR, SIL, HOOD, COIN, RKLB, XBI, OKLO, SMR, UUUU, IONQ, MP, SOFI, CRWV, IREN
   - Cada ticker mapped a `["wallstreetbets", ...sector-specific subs]`

2. En `stock_analyzer.py:stock_watchdog` ENTRY_ALERT msg:
   - Llamar `social_quant.get_social_sentiment(ticker.upper(), 24)`
   - Si signal == "EUPHORIA" → tag `🔥 Social: EUPHORIA — fade crowd`
   - Si signal == "FEAR" → tag `💀 Social: FEAR — capitulación retail, opportunity`
   - Si NEUTRAL/None → sin tag

3. Tag prepended después de `_priority_tag` (Spec 003), antes del header `🚨 ALERTA DE ENTRADA`

## Non-goals

- HMM regime stocks — Spec 023.5 (requires yfinance adapter en regime_hmm.py)
- CVD spot stocks — N/A (Binance no opera NYSE)
- Whale on-chain stocks — N/A (Etherscan no aplica)
- Gate stocks alerts por EUPHORIA — solo TAG visual, no kill alert
- Boost score stocks — stocks alerts no usan conf_score como cripto V3
- Spec 023 en ZONE_ALERT — solo ENTRY_ALERT (más accionable)

## Dependencias

- `social_quant.get_social_sentiment` ✅ (Spec 013)
- `stock_analyzer.py:stock_watchdog ENTRY_ALERT block` ✅
- `_SUBREDDITS_BY_SYMBOL` extension

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| REDDIT_CLIENT_ID missing → social_quant retorna {} | try/except + tag vacío. Alert sigue normal |
| Stock ticker no en _SUBREDDITS_BY_SYMBOL → fallback DEFAULT (crypto-focused) | DEFAULT incluye wallstreetbets que cubre stocks. Mention filter relaxado en _scan_reddit |
| Sentimiento ruidoso por wallstreetbets (memes) | Cache 30min reduce frecuencia. EUPHORIA threshold compound > 0.5 filtra ruido |
| Stocks fuera de market hours sentimiento no actionable | Spec 002 NYSE gate solo ejecuta stock_watchdog Mon-Fri 09:30-16:00 ET, así que social tag siempre dentro de horario |
| HMM stocks defer → coverage parcial | Documented Spec 023.5 backlog. Social solo es 1 de las 4 voices intel |

## Criterio de aceptación

1. `python3 -m py_compile stock_analyzer.py social_quant.py` → OK
2. `_SUBREDDITS_BY_SYMBOL` contiene 16+ stocks tickers
3. En ENTRY_ALERT, llamada a `social_quant.get_social_sentiment(t.upper(), 24)` envuelta en try/except
4. Si EUPHORIA → tag prepended con 🔥
5. Si FEAR → tag prepended con 💀
6. Sin REDDIT creds → tag vacío, alert sigue normal
7. Producción pendiente: próximo entry alert NVDA/TSLA → mensaje muestra social tag si signal accionable
