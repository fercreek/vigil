# Spec 011.5 — Telegram `/bitlobomulti` Comando (BitLobo Multi-image)

> **Status:** CODE COMPLETE 2026-05-26
> **Owner:** Fernando
> **Severity:** P1 — activate Spec 011 feature
> **Origen:** Spec 011 backlog (analyze_chart_multi existía sin caller)

## Contexto

Spec 011 agregó `bitlobo_agent.analyze_chart_multi(image_paths, ...)` para análisis multimodal cross-asset (precio + sectorial + VIX en 1 prompt). Pero ningún handler Telegram lo invoca.

Spec 011.5 agrega comando `/bitlobomulti SYM` que toma las imágenes recientes (mtime <30min) guardadas en `chart_ideas/assets/image_sym_*.png` y las pasa al `analyze_chart_multi`.

Workflow Fernando:
1. Envía foto precio con caption `/add_chart NVDA 4H` → guarda `image_nvda_4h.png`
2. Envía foto sectorial con caption `/add_chart NVDA SECTOR` → guarda `image_nvda_sector.png`
3. Envía texto `/bitlobomulti NVDA` → bot analiza ambas en 1 call multimodal

## Goals

1. Comando `/bitlobomulti SYM` en `telegram_commands.py`
2. Busca archivos `chart_ideas/assets/image_{sym}_*.png` con mtime <1800s
3. Top 5 más recientes (sort desc por mtime)
4. Si 0 imágenes → mensaje "no encontré imágenes recientes, manda con /add_chart"
5. Si N imágenes → labels inferidos del filename (image_nvda_4h.png → "NVDA 4H")
6. Llamada `bitlobo_agent.analyze_chart_multi(paths, sym, tf, context, labels)`
7. Send result al chat

## Non-goals

- Detectar `media_group_id` Telegram (multi-photo single update) — Spec 011.6 candidato (requiere buffer state)
- Caption "/bitlobo multi" directo con N fotos en un solo update — fuera de scope
- Limpiar imágenes viejas auto — out of scope
- Comando `/bitlobomulti SYM TF1 TF2 TF3` con TFs explícitos — auto-detect via filename suficiente

## Dependencias

- `bitlobo_agent.analyze_chart_multi` ✅ (Spec 011)
- `telegram_commands.py:_handle_updates` loop ✅
- `chart_ideas/assets/` directory existence
- `/add_chart SYM TF` handler ya guarda en este path ✅

## Riesgos + mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| `glob` lento si /assets tiene miles de files | Filter por mtime <30min limita resultado |
| Imágenes truncated o mime incorrect | bitlobo_agent.analyze_chart_multi auto-detect mime + validation |
| Fernando manda /bitlobomulti sin imágenes guardadas | Mensaje claro "no encontré, manda con /add_chart" |
| Costo Gemini con 5 images = 5× tokens | max_output_tokens=600 controla output. Input cost ~258 tok/img × 5 = 1290 tokens. Aceptable |
| Si timeframe path mal nombrado en filename | labels usa "TF" fallback genérico |

## Criterio de aceptación

1. `python3 -m py_compile telegram_commands.py` → OK
2. Comando `/bitlobomulti SYM` parseado correctamente (`text.startswith`)
3. Detección de archivos image_sym_*.png funciona (test con dummy files)
4. Sort por mtime descending
5. Cap 5 imágenes max
6. Labels inferidos del filename
7. Producción: Fernando envía 2 fotos con /add_chart, luego /bitlobomulti SYM → bot analiza
