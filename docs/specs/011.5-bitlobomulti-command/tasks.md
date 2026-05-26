# Tasks 011.5 — /bitlobomulti

> **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
> **Status:** CODE COMPLETE 2026-05-26

## Esta sesión

- [x] Comando `/bitlobomulti SYM` en `telegram_commands.py:_handle_updates`
- [x] `import time` agregado a imports top
- [x] glob `chart_ideas/assets/image_{sym.lower()}_*.png`
- [x] Filter mtime <1800s (30min window)
- [x] Sort desc por mtime, top 5
- [x] Labels inferidos del filename (parts_fn[2] → TF)
- [x] Mensaje "no encontré" si 0 imágenes
- [x] Mensaje "analizando N imágenes" + analyze_chart_multi call
- [x] Posición en if-elif ANTES de `/bitlobo` (startswith priority)
- [x] py_compile telegram_commands.py OK
- [ ] Commit `feat(telegram): spec-011.5 /bitlobomulti command`
- [ ] Push origin/main

## Verificación post-deploy

Test manual Fernando:
- [ ] /add_chart NVDA 4H + foto → guarda image_nvda_4h.png
- [ ] /add_chart NVDA 1D + foto → guarda image_nvda_1d.png
- [ ] /bitlobomulti NVDA → bot responde "analizando 2 imágenes: NVDA 4H, NVDA 1D"
- [ ] BitLobo respuesta cross-TF coherente
- [ ] /bitlobomulti BTC (sin imágenes recientes) → mensaje de error claro

## Backlog Spec 011.6

- [ ] media_group_id detection (multi-photo single update)
- [ ] Cleanup auto imágenes >7d
- [ ] /bitlobomulti SYM TF1 TF2 TF3 explícito
- [ ] Multi-symbol cross-asset
- [ ] Capture auto sin /add_chart
