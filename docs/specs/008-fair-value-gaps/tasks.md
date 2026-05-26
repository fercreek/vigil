# Tasks 008 — Fair Value Gaps

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26

## Esta sesión

- [x] `indicators.detect_fair_value_gaps(symbol, timeframe, lookback, max_gaps)` añadida
  - Retorna `bullish_fvgs`, `bearish_fvgs`, `nearest_bullish_top`, `nearest_bearish_bot`, `current_price`
  - Filtrado de FVGs ya rellenados
  - Sort por age + max_gaps cap
- [x] Wire en `strategies.py:V3-Reversal` → tag `🎯 FVG imán @ $X.XX` si nearest_bullish_top entre TP1 y TP2
- [x] `_fvg_tag` agregado al `msg` después de `_sweep_tag`
- [x] py_compile + AST verification
- [ ] Commit `feat(indicators): spec-008 fair value gaps`
- [ ] Push origin/main

## Verificación post-deploy

- [ ] Log NO error `[FVG ERROR]` en Railway
- [ ] Si V3 alert dispara con FVG en rango → Telegram muestra línea 🎯
- [ ] Si V3 alert dispara sin FVG válido → Telegram normal (sin línea 🎯)
- [ ] Conteo V3 alerts con/sin FVG tag

## Tuning post-7d

- [ ] Si <10% alerts tienen FVG tag → bueno, raro pero útil
- [ ] Si >50% V3 alerts tienen FVG tag → lookback 30→40+
- [ ] Si V3+FVG WR >5pp mejor → Spec 008.5: override TP1 a `_fvg_target`
- [ ] Si performance igual → mantener informativo

## Próximos specs roadmap

- [ ] **Spec 009** — HMM Regime Classifier (Salmos semáforo maestro, 2-3 días)
- [ ] **Spec 010** — Whale Netflows on-chain Etherscan (2 días)
- [ ] **Spec 011** — Multi-image BitLobo Gemini (1 día)
- [ ] **Spec 012** — Spot CVD Segmentado (3-4 días, Mes 3)

## Backlog Spec 008.5

- [ ] Override TP1 a `_fvg_target` si validado en 7d
- [ ] FVG en 4H/1D timeframe para targets macro
- [ ] Cuadrilla Zenith voz Salmos: incluir FVG context en prompt
- [ ] Bearish FVG en V3 SHORT (cuando V3 SHORT regrese del kill switch)
