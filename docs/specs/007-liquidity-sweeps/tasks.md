# Tasks 007 — Liquidity Sweeps

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26

## Esta sesión

- [x] `indicators.detect_liquidity_sweep(symbol, timeframe, lookback)` añadida
  - Detecta swept_high/swept_low contra swing high/low de N velas previas
  - Retorna dict con niveles + flags + current candle
- [x] Wire en `strategies.py:V3-REVERSAL` → tag `🌊 SWEEP LOW activo` en msg
- [x] Try/except envuelve detection → fallback silent si falla
- [x] py_compile indicators.py + strategies.py → OK
- [x] AST verification: función definida + wired
- [ ] Commit `feat(indicators): spec-007 liquidity sweeps detection + V3 tag`
- [ ] Push origin/main

## Verificación post-deploy (próximas alertas V3)

- [ ] Log NO error `[LiquiditySweep ERROR]` en Railway
- [ ] Si V3 alert dispara con swept_low → Telegram msg inicia con línea 🌊
- [ ] Si V3 alert dispara sin sweep → Telegram msg normal (sin línea 🌊)
- [ ] Conteo de V3 alerts con/sin tag — usar para tuning lookback

## Tuning post-7d

- [ ] Si tag aparece <20% V3 alerts → bueno, captura excepción
- [ ] Si tag aparece >80% V3 alerts → subir lookback a 40
- [ ] Si V3 alerts con tag tienen WR >5pp mejor → considerar boost en `calculate_confluence_score`
- [ ] Si performance igual → mantener tag solo informativo

## Próximos specs roadmap

- [ ] **Spec 008** — Fair Value Gaps (FVG) detection
- [ ] **Spec 009** — HMM Regime Classifier (Salmos semáforo maestro)
- [ ] **Spec 010** — Whale Netflows on-chain Etherscan
- [ ] **Spec 011** — Multi-image BitLobo Gemini

## Backlog Spec 007.5

- [ ] Wire sweep detection a V2-AI swing entries (post-validación V3)
- [ ] Multi-TF sweep (1h + 4h confirmation)
- [ ] Boost en `calculate_confluence_score` cuando swept_low + RSI extremo
- [ ] Cuadrilla Zenith voz Salmos: incluir sweep context en prompt
