# Zenith — Agents & Kill Switches

> Estado: **v1.3.1** · Actualizado 2026-04-29

Referencia de los agentes IA activos (Cuadrilla Zenith) y los kill switches
operativos que controlan qué estrategias y símbolos están habilitados.

---

## Cuadrilla Zenith — Agentes IA

Cuatro voces independientes que debaten cada señal. Cada una tiene un sesgo
distinto. El consenso resultante determina el bias final del SENTINEL.

Implementación: `gemini_analyzer.get_ai_consensus()` · `voice_compactor.py`

| Agente | Rol | Sesgo |
|--------|-----|-------|
| **Genesis** | Capital institucional y acumulación | Pregunta: ¿Está el smart money entrando? Volumen, OI, funding |
| **Exodo** | Narrativa y tecnología del proyecto | Pregunta: ¿La narrativa sigue viva? Adopción, catalizadores |
| **Salmos** | Confluencia técnica | Pregunta: ¿RSI, EMA200, BB y ATR alinean? |
| **Apocalipsis** | Riesgo macro | Pregunta: ¿Qué puede matar esta operación? DXY, FOMC, VIX |

### Formato de output (SENTINEL compact v1.2.0+)

```json
{
  "bias": "LONG | SHORT | NEUTRAL",
  "score": 1-5,
  "verdict": "ACUMULAR | ESPERAR | REDUCIR",
  "voices": {
    "genesis":     "≤8 palabras",
    "exodo":       "≤8 palabras",
    "salmos":      "≤8 palabras",
    "apocalipsis": "≤8 palabras"
  },
  "action": "≤12 palabras con nivel de precio si aplica"
}
```

### Reglas SENTINEL (v1.2.0+)

- Score Gemini < 4/5 → **skip** (no enviar)
- Mismo (sym, bias) en últimos 90 min con score igual o menor → **skip** (dedupe)
- Frecuencia: cada **4h** (era 2h)
- `KILL_SALMOS_PROPHECY = True` — SALMOS hourly removido (duplicaba PANORAMA)
- JSON truncado: `_repair_partial()` extrae bias/score/verdict por regex si Gemini corta mid-string

### BitLobo (agente externo)

Agente complementario de análisis por zonas visuales. Ver `bitlobo_agent.py`.
- Input: foto de gráfica vía Telegram con `/bitlobo SYMBOL TF`
- Output: análisis zona verde/roja con entry/SL/target

---

## Kill Switches

Flags en `config.py` que deshabilitan estrategias o símbolos con mal desempeño.
Cambiar a `True` para reactivar — siempre documentar el motivo y el WR que lo justificó.

### Símbolos

| Flag | Valor | Razón | WR al desactivar | Fecha |
|------|-------|-------|-----------------|-------|
| `TAO_TRADING_ENABLED` | `False` | Bittensor consistentemente pierde — tendencia bajista estructural | 3.1% (1/32) | Abr-2026 |

### Estrategias

| Flag | Valor | Razón | WR al desactivar | Fecha |
|------|-------|-------|-----------------|-------|
| `V1_SHORT_ENABLED` | `False` | V1 SHORT genera pérdidas en régimen alcista 2026 | 4.3% (1/23) | Abr-2026 |
| `KILL_SALMOS_PROPHECY` | `True` | SALMOS hourly duplicaba PANORAMA — ratio señal/ruido negativo | N/A | Abr-2026 |

### Umbrales de supresión (soft kills)

| Parámetro | Valor | Efecto |
|-----------|-------|--------|
| `GOLD_BULL_THRESHOLD` | `$2,500` | No emitir GOLD SHORT si precio > umbral (correlación DXY/gold rota en 2026) |
| `SP500_VERDE_MIN` | `7,000` | No emitir OIL SHORT si SP500 > umbral (régimen alcista) |
| `MIN_CONFLUENCE (commodities)` | `4` | Confluencia mínima 4/5 (era 3) — reduce falsas señales en GOLD/OIL |
| `MIN_CONFLUENCE_SCORE (crypto)` | `4` | Score mínimo para emitir alerta crypto |
| `SENTINEL_MIN_SCORE_OF_5` | `4` | SENTINEL no se envía si score Gemini < 4/5 |
| `PHY_ALERT_COOLDOWN` | `1,800s` | PHY ALERT se loguea máx 1x cada 30 min por símbolo (evita spam de loop) |
| `VIX_EXTREME_THRESHOLD` | `32.0` | VIX > 32 → no operar / posición mínima |
| `FOMC_NEXT_MEETING` | `2026-06-17` | Suprimir señales agresivas 24h antes de reunión FOMC |

---

## Régimen Macro SP500 (gate dinámico)

Determina el comportamiento del bot según zona del SP500.
Implementación: `commodities_bot.py` · `config.py`

| Zona | SP500 | Comportamiento bot |
|------|-------|-------------------|
| 🟢 VERDE | > 7,000 | No suprimir longs. OIL SHORT bloqueado. |
| 🟡 AMARILLA | 6,800 – 7,000 | Reducir tamaño 50%, requiere confluencia extra |
| 🟠 NARANJA | < 6,800 | Activar SHORT SPY watch. Filtrar longs débiles. |

---

## Monitor de Posiciones Manuales

Hilo independiente que vigila posiciones manuales de Fernando (fuera del bot).
Implementación: `manual_positions_monitor.py` · hilo `manual_monitor` en `main.py`

**Ciclo:** 30 min · **Cooldown alerta:** 1h por símbolo

**Lógica de recomendación (LONG bias):**

| Condición | Recomendación |
|-----------|--------------|
| P&L ≥ +8% sin parciales tomados | Tomar 30-50% ganancias |
| P&L ≥ +5% sin BE movido | Mover SL a break even |
| P&L ≥ +3% sin BE | Zona BE próxima, vigilar |
| P&L -8% a -15% | Drawdown, evaluar si tesis válida |
| P&L < -15% | Alerta drawdown importante |

**Comandos Telegram:**

```
/manual                  — P&L + recomendación de todas las posiciones
/manual_tp SYM           — Cerrar posición completa (TP hit)
/manual_tp SYM 50        — Tomar 50% de ganancias (partial)
/manual_sl SYM           — Marcar SL hit / cerrar en pérdida
/manual_be SYM           — Anotar que SL fue movido a break even
/manual_off SYM          — Desactivar monitoreo (posición sigue abierta)
/manual_add SYM ENTRY    — Agregar nueva posición al monitor
```

**Persistencia:** `manual_positions.json` (init desde `config.MANUAL_POSITIONS`).
⚠️ No persiste entre redeploys en Railway sin volume mount. Workaround: actualizar
`config.MANUAL_POSITIONS` antes de cada deploy.

---

## Historial de kills — resumen de auditorías

| Fecha | Auditoría | Acción tomada |
|-------|-----------|--------------|
| Abr-13 2026 | WR 36.1%, TAO 0%, 29 trades stuck | TAO kill switch activado |
| Abr-2026 | V1-SHORT 0% WR en 16+ trades | `V1_SHORT_ENABLED = False` |
| Abr-29 2026 | WR 16.9%, GOLD 0/6, SHORT 4.3% | Gold bull lock + MIN_CONFLUENCE commodities 3→4 |
| Abr-29 2026 | SOL PHY spam cada ciclo | `PHY_ALERT_COOLDOWN = 1800s` |
| Abr-29 2026 | Sentinel JSON truncado → parse fail | `_repair_partial()` en voice_compactor |

**Siguiente revisión recomendada:** conf_score 5 = 0% WR (peor que score 4).
Ver `docs/AGENTS_AND_KILLS.md` sección kill switches para contexto.
