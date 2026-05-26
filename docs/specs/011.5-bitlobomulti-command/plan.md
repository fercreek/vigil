# Plan 011.5 — Telegram /bitlobomulti

> **Spec:** [spec.md](spec.md)
> **Status:** CODE COMPLETE 2026-05-26

## Decisiones técnicas

### 1. Filesystem-based collection vs media_group_id buffer

Filesystem chosen. Razones:
- `media_group_id` Telegram requires buffer state across loop iterations + timeout logic. Complex.
- `/add_chart SYM TF` ya guarda imágenes deterministically en `chart_ideas/assets/`.
- Workflow simple para Fernando: manda fotos individualmente con /add_chart, luego /bitlobomulti.
- Stateless, sobrevive Railway restart.

Trade-off: requiere 2 steps (add_chart + bitlobomulti) en lugar de 1 (multi-foto upload).

### 2. mtime <30 min window

```python
recent = [p for p in candidates if now - os.path.getmtime(p) < 1800]
```

30 min suficiente para "Fernando saca screenshots seguidos y manda". Evita batch de imágenes viejas accidentales.

Tunable. Quick wins: si Fernando reporta missed images por timeout corto, subir a 60 min.

### 3. Cap 5 images max

```python
recent = recent[:5]
```

Razones:
- Gemini Flash 2.5 cost: 258 tok/img × 5 = 1290 tokens. $0.003 / call. Aceptable.
- 5 imágenes da contexto cross-TF (1h, 4h, 1d, semanal, mensual + sectorial)
- Más de 5 = ruido visual + costo creciente

### 4. Labels inferidos del filename

```python
base = os.path.basename(p).replace(".png", "")
parts_fn = base.split("_")
tf_part = parts_fn[2].upper() if len(parts_fn) >= 3 else "TF"
labels.append(f"{sym} {tf_part}")
```

Conventions:
- `image_nvda_4h.png` → label "NVDA 4H"
- `image_nvda_sector.png` → label "NVDA SECTOR"
- Falsies → "NVDA TF" fallback

Gemini usa los labels para entender qué representa cada imagen.

### 5. Sort desc por mtime

Imágenes más recientes primero. Si solo 5 caben, son las 5 más recientes — match con la intención del usuario.

### 6. Comando antes de `/bitlobo` en if-elif chain

Order importa: `text.startswith("/bitlobomulti")` ANTES de `text.startswith("/bitlobo")` porque `/bitlobomulti` también startswith `/bitlobo`.

## Verificación

- ✅ py_compile telegram_commands.py
- ✅ `import time` agregado top
- ✅ Comando handler en if-elif posición correcta
- Producción pendiente: Fernando test manual

## Commits planeados

| # | Scope |
|---|-------|
| 1 | `feat(telegram): spec-011.5 /bitlobomulti command — batch últimas imágenes BitLobo` |

## Backlog Spec 011.6

- Detectar `media_group_id` para multi-photo single update (buffer state + timeout)
- Cleanup auto de imágenes viejas (>7d) en chart_ideas/assets/
- Comando `/bitlobomulti SYM TF1 TF2 TF3` con TFs explícitos
- Multi-symbol: `/bitlobomulti BTC ETH SOL` cross-asset
- Capture screenshot Telegram → guardar auto sin requerir /add_chart explícito
