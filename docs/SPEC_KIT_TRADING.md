# SPEC KIT — Zenith Trading Suite
> Versión: 1.0 · Creado: 2026-05-27 · Autor: Fernando + Claude

Documento maestro de invariantes, acceptance criteria y gates de calidad.
Este es el contrato de lo que el sistema **debe hacer** y **cómo se verifica**.

---

## 1. System Invariants

Cosas que deben ser TRUE en cualquier momento. Si alguna falla → el bot está roto.

| # | Invariante | Cómo verificar |
|---|-----------|----------------|
| I-1 | Proceso `main.py` corriendo | `pgrep -f main.py` retorna PID |
| I-2 | 5 threads activos (scalp_bot, swing, telegram, stock, daily_report) | `ps aux \| grep main.py` + log de boot |
| I-3 | `app.log` con entry en últimos 10 min | `stat logs/app.log` mtime |
| I-4 | Telegram token válido (`@tradercreekbot`) | `getMe` API = ok |
| I-5 | `signals.jsonl` con entry del día actual | Check fecha en últimas líneas |
| I-6 | Gemini API responde en < 20s | Llamada de test con timeout |
| I-7 | `ai_budget` DB tiene entries (no siempre vacío) | `get_monthly_cost().calls >= 1` |

---

## 2. Config Guards

Flags que SI se invierten accidentalmente rompen el bot o generan señales malas.

```python
# MUST be False — estrategias con WR probada < 20% o 0 trades
V1_LONG_ENABLED      = False   # 15.4% WR / -34.1% PnL en 53 trades
V1_SHORT_ENABLED     = False   # 0% WR en 16 trades
V5_ENABLED           = False   # 0 trades en 365d (bug en filtros)
TAO_TRADING_ENABLED  = False   # 0/31 WR (0%) — Spec 001 May-22-2026

# MUST be True
ENABLE_TELEGRAM_BUTTONS = True  # UX redesign 2026-05-26

# Blocklists activas (NO vaciar sin data de validación)
V4_BLOCKLIST    = ["ETH", "ZEC"]    # walk-forward overfit confirmado
SWING_BLOCKLIST = ["TAO", "ZEC"]    # ZEC Q3+Q4 WR=0% en swing
```

**Test:** `venv/bin/python -c "from config import *; assert not V1_LONG_ENABLED; assert not TAO_TRADING_ENABLED; print('OK')"`

---

## 3. Acceptance Criteria por Estrategia

### 3.1 SENTINEL (ZEC)
| Criterio | Valor |
|----------|-------|
| Score mínimo | 4/5 (`SENTINEL_MIN_SCORE_OF_5`) |
| Intervalo mínimo | 4h (`SENTINEL_INTERVAL_SEC = 14400`) |
| Dedupe | 90 min mismo símbolo/bias con score ≤ anterior |
| Símbolos activos | ZEC únicamente (TAO = False) |
| **DEBE disparar** | RSI 30–72 + score ≥ 4 + sin posición abierta + fuera hora bloqueada |
| **NO debe disparar** | LONG si RSI ≥ 72, SHORT si RSI ≤ 28, hora UTC en `{4,6,10,11,15,16,17,20}` |

### 3.2 SWING (Ichimoku)
| Criterio | Valor |
|----------|-------|
| Consenso requerido | `kumo_status == ai_bias` (ambos BULL o ambos BEAR) |
| `ai_bias = ACCUMULATION` | → SUPPRESSED (mercado lateral, **no es bug**) |
| `ai_bias = NEUTRAL` | → SUPPRESSED |
| EMA50 filter | LONG solo si precio > EMA50 4H, SHORT solo si precio < EMA50 4H |
| Símbolos | ZEC/USDT, TAO/USDT (ambos en SWING_BLOCKLIST actualmente) |
| **NOTA** | Con SWING_BLOCKLIST = ["TAO","ZEC"], swing no dispara en producción actual. Diseñado así. |

### 3.3 V3-REVERSAL
| Criterio | Valor |
|----------|-------|
| RSI entry | Por símbolo (`RSI_REVERSAL_BY_SYMBOL`) — aprox 40-45 |
| Confluencia mínima | 4/5 (`V3_MIN_CONFLUENCE = 4`) |
| Símbolos | BTC, ETH, ZEC (no TAO) |
| Timeframe | 15m |
| Bloqueado si | FOMC proximity 24h, hora UTC bloqueada, posición abierta |

### 3.4 V4-EMA
| Criterio | Valor |
|----------|-------|
| Proximidad EMA | Por símbolo (`V4_EMA_PROX_MAP`) |
| Confluencia mínima | 3/5 (`V4_MIN_CONFLUENCE = 3`) |
| Símbolos | BTC, TAO (**ETH y ZEC en V4_BLOCKLIST**) |
| TAO | Bloqueado (`TAO_TRADING_ENABLED = False`) |
| Efectivo | Solo BTC opera con V4 actualmente |

### 3.5 STOCK WATCHLIST
| Criterio | Valor |
|----------|-------|
| Símbolos activos | PTS watchlist (COIN, SOFI, XLE, etc.) |
| Supresiones activas | IONQ/RGTI sobreextendidas hasta corrección, OKLO earnings |
| Intervalo | 15 min (`stock_watchdog`) |
| **No auto-trade** | Solo alertas informativas |

---

## 4. Budget Gate

| Item | Valor |
|------|-------|
| Cap mensual | $10 USD (`MAX_MONTHLY_USD` en `ai_budget`) |
| Costo estimado real | < $2 USD/mes (Gemini Flash 2.5) |
| Rate Gemini 2.5 Flash | $0.15/M tokens in, $0.60/M tokens out |
| Rate Claude Haiku | $0.80/M in, $4.00/M out |
| Tracking DB | `data/ai_budget.db` vía `ai_budget.log_ai_call()` |
| **BUG CORREGIDO** | `gemini-2.5-flash` tenía rates = $0.0 (May 27 2026) |

---

## 5. Signal Quality Gate

| Gate | Regla |
|------|-------|
| Sentinel dedupe | No mismo símbolo/bias en < 90 min con score ≤ previo |
| Swing cooldown | No misma dirección en < 4H por símbolo |
| Hour filter | UTC `{4, 6, 10, 11, 15, 16, 17, 20}` = 0% WR histórico → bloqueado |
| RSI contradiction | No LONG si RSI ≥ 72, no SHORT si RSI ≤ 28 |
| Max alertas/symbol | Max 3 del mismo símbolo en ventana 4H (via cooldown) |
| Posición abierta | No nueva señal si posición del mismo símbolo está abierta |

---

## 6. Threads & Health

| Thread | Archivo | Función | Intervalo |
|--------|---------|---------|-----------|
| `scalp_bot` | `scalp_alert_bot.py` | `main()` | 35s |
| `swing` | `swing_bot.py` | `run_zenith_swing()` | 4H |
| `telegram` | `scalp_alert_bot.py` | `run_telegram_worker()` | 5s |
| `stock` | `stock_analyzer.py` | `stock_watchdog()` | 15min |
| `daily_report` | `daily_report.py` | `run_daily_report()` | 24h @ 13:00 UTC |

**Disabled (código existe):**
- `commodities` — GOLD/OIL/NG/SLV (último bug May 2026: format string inválido, fixed)
- `manual_monitor` — P&L posiciones manuales
- `scalper_shorts` — DOGE/FIL/TAO SHORT

**Watchdog:** `main.py` auto-reinicia threads muertos (MAX_RESTARTS=10, check 120s).

---

## 7. Spec Wire Status

> Ver `docs/SPEC_WIRE_AUDIT.md` para detalle completo.

| Status | Specs |
|--------|-------|
| ✅ Wired + logged | 002.5, 005, 009, 010, 012, 013, 014, 022, 023 (y más) |
| ⚠️ Dormant si V3 no dispara | 007 (Liquidity Sweeps), 008 (FVG) |
| ⏳ Pendiente log_intel_event | V1/V2/V4 strategies (Spec 022.6.3) |

---

## 8. Rutas de Verificación

### Smoke test (infra + señales + config)
```bash
venv/bin/python tests/smoke_test.py
# Esperado: 15/15 PASS
```

### Integration test (API real)
```bash
venv/bin/python tests/integration_system.py
# Esperado: 3/3 PASS
```

### Budget check
```bash
venv/bin/python -c "from ai_budget import get_monthly_cost; import json; print(json.dumps(get_monthly_cost(), indent=2))"
# Esperado: gemini_usd > 0.0
```

### Signal summary
```bash
curl http://localhost:8080/api/signals/summary
# Esperado: totals.SENT >= 1 si el bot lleva > 4H corriendo
```

### Config guards
```bash
venv/bin/python -c "
from config import V1_LONG_ENABLED, V1_SHORT_ENABLED, V5_ENABLED, TAO_TRADING_ENABLED, ENABLE_TELEGRAM_BUTTONS
assert not V1_LONG_ENABLED
assert not V1_SHORT_ENABLED
assert not V5_ENABLED
assert not TAO_TRADING_ENABLED
assert ENABLE_TELEGRAM_BUTTONS
print('✅ Config guards OK')
"
```

---

## 9. Histórico de cambios críticos

| Fecha | Cambio | Impacto |
|-------|--------|---------|
| 2026-04-20 | Bot murió (format string + yfinance NoneType) | 5 semanas sin señales |
| 2026-05-22 | Spec 001: TAO_TRADING_ENABLED = False | TAO eliminado |
| 2026-05-26 | Specs 009-023 wired + SPEC_WIRE_AUDIT | Intel pipeline activo |
| 2026-05-27 | social_analyzer timeout fix (45s daemon thread) | Fin del freeze en TON |
| 2026-05-27 | signal_logger.py creado | Visibilidad de señales |
| 2026-05-27 | ai_budget Gemini rates fix ($0→$0.15/M) | Costo tracking real |
