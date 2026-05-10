# _BACKLOG — Items diferidos del Audit (2026-05-09)

> Items identificados en auditoría externa. NO son urgentes ahora — focus actual = win rate.
> Cada item con severidad y esfuerzo estimado.

---

## 🔴 CRÍTICO (Security & Data)

### S1. Secrets en `.env` committeados al repo
- **Severidad:** Alta — API keys expuestas en GitHub
- **Estado:** Diferido por decisión Fernando 2026-05-09
- **Keys expuestas:** TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, BINANCE_API_KEY, BINANCE_SECRET_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY, TV_WEBHOOK_SECRET
- **Fix cuando se aborde:**
  ```bash
  # 1. Rotar TODAS las keys (Telegram, Gemini, Anthropic, Binance, TV)
  # 2. Sacar .env del git
  git rm --cached .env
  echo ".env" >> .gitignore
  git commit -m "security: untrack .env"
  # 3. Limpiar history (opcional, pesado): git filter-repo --path .env --invert-paths
  ```
- **Esfuerzo:** 30 min + tiempo de rotación de cada key

### S2. Sin Railway Volume — `trades.db` pierde data en cada redeploy
- **Severidad:** Alta — pérdida de WR histórico, audit trail
- **Estado:** Diferido (mencionado en `_NEXT.md` previo "Volume mount Railway")
- **Fix:** Configurar Railway Volume mount en `/app/trades.db`
- **Esfuerzo:** 15 min

---

## 🟡 IMPORTANTE — Data integrity & observability

### D1. Columnas `trigger_conditions` y `events_json` 0/91 pobladas
- **Problema:** `tracker.log_trade()` recibe parámetro `trigger_conditions` pero strategies.py no lo pasa siempre. `append_event()` se llama poco
- **Impacto:** Imposible auditar por qué se tomó cada decisión
- **Fix:** Verificar todos los `log_trade()` calls pasan `trigger_conditions=build_trigger_conditions(...)`. Llamar `append_event()` en SL/TP/BE hits
- **Esfuerzo:** 1-2h

### D2. Tabla `ai_calls` nunca inicializada
- **Problema:** `ai_budget.py` existe pero la tabla no fue creada. `MAX_MONTHLY_USD=$10` no se enforce realmente
- **Fix:** Init tabla en arranque + log cada llamada Gemini/Claude con costo
- **Esfuerzo:** 2h

### D3. 31 episodios `signal_episodes` pendientes sin outcome
- **Problema:** `check_pending_outcomes()` no corre o falla silenciosamente
- **Fix:** Cron explícito en main loop + logging de errores
- **Esfuerzo:** 1h

### D4. Logs sin rotación
- **Problema:** `logs/bot.log` 71KB sin RotatingFileHandler. `logs/app.log` 0 bytes (no escribe)
- **Fix:** `logger_core.py` usar `RotatingFileHandler(maxBytes=10MB, backupCount=5)`
- **Esfuerzo:** 30 min

### D5. 177 `except Exception:` silenciados
- **Problema:** errores invisibles en prod. Ejemplos en `scan_status.py:43,54,95,145`
- **Fix:** Reemplazar 20-30 críticos con `logger.error("...", exc_info=True)`
- **Esfuerzo:** 2-3h

---

## 🟢 LIMPIEZA — Cuando haya tiempo

### C1. Archivos > 800 líneas (refactor)
- `gemini_analyzer.py` (1268L) — separar personas en `agents/` folder
- `scalp_alert_bot.py` (1143L) — extraer `signal_dispatcher.py` + `execution_hooks.py`
- `telegram_commands.py` (843L) — separar handlers por categoría
- `strategies.py` (840L) — un archivo por estrategia (`v1_long.py`, `v3_reversal.py`, etc.)
- `tracker.py` (734L) — separar queries de schema

### C2. Duplicación `_calc_rsi`/`_calc_atr`
- 3 archivos con código idéntico: `commodities_bot.py`, `scalper_shorts_bot.py`, `indicators.py`
- Fix: crear `indicators_util.py` central, importar de ahí

### C3. Constantes muertas en config.py
- `MACRO_WATCH = []` — nunca leído
- `RATE_BIAS = "HAWKISH_HOLD"` — nunca consultado
- `V3_REQUIRE_DIVERGENCE`, `V3_REQUIRE_BB_SQUEEZE` — obsoletos

### C4. Código muerto en scalp_alert_bot.py
- `register_signal_event()` (línea ~522)
- `get_phase()`, `set_phase()` (línea ~560)
- `_handle_user_question()` fallback sin uso

### C5. Tests sin coverage
- `gemini_analyzer.py` (1268L) → 0 tests
- `alert_manager.py`, `trading_executor.py` → 0 tests
- Sin `pytest.ini` con config explícita

### C6. trades.db duplicado
- `./trades.db` (36KB, 6 May) — el activo
- `./data/trades.db` (28KB, 29 Apr) — copia obsoleta
- Decidir cuál es source of truth, eliminar el otro

### C7. Variables muertas
- Identificar y limpiar imports/funciones huérfanas

---

## Prioridad sugerida cuando se aborde

1. S1 + S2 (security/data loss) — antes que nada
2. D1 (trigger_conditions) — habilita auditoría WR profunda
3. D2 (ai_calls) — control de costo real
4. D3 (episodes pendientes) — feedback loop de aprendizaje
5. C2 (indicators centralizados) — 30 min, reduce mantenimiento
6. Resto cuando haya bandwidth
