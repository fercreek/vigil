# VIGIL — Plan Maestro

> **Documento autoritativo único** de dónde está vigil y hacia dónde va.
> Repo: `/Users/fernandocastaneda/Documents/ideas/scalp_bot` · remote `github.com/fercreek/vigil`
> Update: 2026-06-20 · Último commit: `4211fb4` · Estado: **Fénix ejecutado local, falta deploy Railway**
> Docs hermanos (no duplicar): `docs/FENIX.md` (runbook deploy + regla-gate) · `docs/LEARNINGS.md` (porqué del giro) · `_NEXT.md` (estado vivo) · `docs/SPEC_WIRE_AUDIT.md` (wires por spec, marcado stale).

---

## 1. Norte del proyecto

**Qué ES vigil hoy:** un **cockpit de inteligencia de mercado** (intel macro curado PTS/BitLobo + Cuadrilla Zenith multi-voz + tracking manual de posiciones + alertas de niveles que Fernando define) **+ un único experimento auto medido: V3-REVERSAL sobre ZEC**, con telemetría encendida y fecha de muerte a 30 días.

Vigil **dejó de ser** un bot de auto-alertas ciego multi-símbolo. Esa máquina llevaba **18.7% win rate** (17W/74L, n=91), estuvo **muerta ~3 semanas** sin que nadie lo notara (27-may → 20-jun), y sus 92 trades cerrados eran 100% SWING/COMMODITY — la estrategia "estrella" (V3-REVERSAL) nunca cerró un outcome en producción. El giro estratégico (Opción C del Plan Fénix) jubila las señales auto multi-símbolo y conserva lo que sí tenía valor demostrado: el intel humano y la infra reusable.

**Métrica de éxito a 30 días** (honesta, anti-vanity — detalle en `docs/FENIX.md`):
1. **Uso deliberado** — Fernando consulta el cockpit (`/intel /macro /pos /bitlobo`) ≥3 de cada 5 días hábiles por iniciativa propia.
2. **Decisión informada** — ≥2 posiciones manuales gestionadas usando intel del cockpit.
3. **Experimento ZEC** — ≥20 trades resueltos en `intel_outcomes` → veredicto: el auto vive o se mata.

> **Anti-métrica (prohibido celebrar):** nº de alertas, símbolos cubiertos, specs nuevas, win rate con n<20.

---

## 2. Arquitectura actual

Entry point: **`main.py`** (`web: python main.py`, Railway/Nixpacks). Arranca threads daemon con auto-restart vía `thread_health.py` + watchdog `api_health.py`.

### 2.1 Threads que arranca `main.py` (verificado en código)

| Thread | Target | Estado |
|--------|--------|--------|
| `scalp_bot` | `scalp_alert_bot.main` | 🟢 VIVO — loop scan ZEC (V3-REVERSAL) |
| `swing` | `swing_bot.run_zenith_swing` | 🟡 EN PAUSA — ZEC en `SWING_BLOCKLIST`, no emite |
| `telegram` | `scalp_alert_bot.run_telegram_worker` | 🟢 VIVO — cockpit (46 comandos) |
| `stock` | `stock_analyzer.stock_watchdog` | 🟢 VIVO — watchlist stocks PTS |
| `daily_report` | `daily_report.run_daily_report` | 🟢 VIVO |
| `market_report` | `market_status_report.run_market_status_reports` | 🟢 VIVO (TAO ya removido del reporte crypto) |
| ~~`commodities`~~ | `commodities_bot.run_commodities_bot` | ⚫ JUBILADO — comentado en `main.py:103` |
| ~~`manual_monitor`~~ | `manual_positions_monitor.run_manual_monitor` | ⚫ JUBILADO — comentado en `main.py:104` |

### 2.2 Módulos — VIVO / JUBILADO / DORMANT

**🟢 CORE (vivo, cargado en el path principal):**
- `main.py` — orquestador de threads + resolver `BOT_MODE` (PROD/DEV).
- `scalp_alert_bot.py` (1277L) — loop scan + alertas + worker Telegram.
- `strategies.py` (1179L) — todas las strategies; **V3-REVERSAL ZEC es la única emisora activa** (RSI extremo + gates funding/HMM).
- `indicators.py` (658L) — RSI/BB/EMA/ATR con Wilder smoothing. Sólido, reusable.
- `tracker.py` (1026L) — SQLite `trades.db` + tabla `intel_outcomes` (A/B). **92 trades, 8 outcomes (0 resueltos histórico).**
- `exchange_singleton.py` — fallback multi-exchange OKX→KuCoin→Bybit→Binance (resolvió geo-block 451 Railway).
- `trade_monitor.py` / `alert_manager.py` — gestión de trades abiertos + dedup de alertas.
- `telegram_commands.py` (1044L) — handlers del cockpit (`cmd_pos`, `cmd_open`, etc.).
- `gemini_analyzer.py` (1460L) — Cuadrilla Zenith (Genesis/Exodo/Salmos/Apocalipsis) + `FOMC_CONTEXT`.
- `ai_budget.py` — cap duro $10/mes con auto-tope.
- `api_health.py` + `thread_health.py` — watchdogs (Gemini/Groq/data feed + auto-restart threads).
- `llm_client.py` — cliente Groq (`SENTINEL_AUTO_SYMS`).
- `app.py` (729L) — Flask dashboard + endpoints `/api/metrics/intel_ab`, `/api/stats` (healthcheck).

**🔵 INTEL (vivo, capa de contexto):**
- `regime_transitions.py` (266L) — state machine SP500 (VERDE/AMARILLA/NARANJA), persiste `data/macro_state.json`.
- `blackrock_intel.py` (292L) — intel institucional.
- `bitlobo_agent.py` (361L) — análisis de gráficas por zonas (Gemini Vision), comandos `/bitlobo` `/bitlobomulti`.
- `market_status_report.py`, `daily_report.py`, `market_intel.py` — reportes programados.
- Cockpit manual: `/manual` `/manual_add/be/sl/tp/off`, `/intel`, `/macro`, `/setup`, `/pos`, `/setsl` `/settp`.

**🟡 DORMANT (cargado pero apagado por flag, no emite):**
- `regime_hmm.py` — Spec 009 HMM 3-state. `HMM_ENABLED=false` (V3 corre determinista).
- `swing_bot.py` (vía thread `swing`) — corre pero ZEC bloqueado en `SWING_BLOCKLIST`.

**⚫ JUBILADO / ZOMBI (a decidir si borrar — ver §5):**
- `scalper_shorts_bot.py` — **BORRADO** esta sesión (504L, commit `427af0f`).
- `commodities_bot.py` (688L) — thread comentado en `main.py`.
- `manual_positions_monitor.py` — thread comentado en `main.py`.
- `onchain.py` (306L) — Spec 010 whale netflows Etherscan. **Importado** en app/stock/telegram/strategies pero `ETHERSCAN_API_KEY` nunca seteada → devuelve vacío. **Zombi.**
- `social_quant.py` (358L) — Spec 013 Reddit+Trends. `REDDIT_*` nunca seteadas → zombi.
- (~664L combinados de onchain+social_quant = código que ramifica sin devolver data.)

### 2.3 Flags de control (`config.py` — verificados)

| Flag | Valor actual | Efecto |
|------|--------------|--------|
| `SYMBOLS` | `["ZEC"]` (línea 13) | Scan aislado al experimento. |
| `MACRO_FEED_ENABLED` | `false` (env, default off) | Gatea DOS feeds yfinance (iShares + SPY/oil). Mató noise `CL=F`. |
| `HMM_ENABLED` | `false` (env, default off) | V3 determinista, sin gate HMM. |
| `SENTINEL_AUTO_SYMS` | `["ZEC"]` (env, default ZEC) | Narrow Sentinel Groq → cortó 429 TPM (free tier 8000 tok/min). |
| `SWING_BLOCKLIST` | `["TAO", "ZEC"]` | Swing en pausa para ZEC. |
| `V1_LONG_ENABLED` / `V1_SHORT_ENABLED` | `False` | V1 muerto (15.4% / 0% WR). |
| `V5_ENABLED` | `False` | 0 trades en backtest 365d. |
| `TAO_TRADING_ENABLED` / `TAO_SHORT_ENABLED` | `False` | TAO 0% WR en 31 trades — kill. |
| `V4_BLOCKLIST` | `["ETH", "ZEC"]` | V4 excluye ZEC/ETH (overfit). |
| `TRACKER_DB` | env (default `./trades.db`) | **MUST en Railway: `/data/trades.db`** + Volume montado. |
| `MANUAL_SYMBOLS` | `["TAO","ZEC","DOGE","SOL","BTC","ETH","TON","HYPE"]` | Tracking manual (no auto-scan). |

> El experimento auto es **solo ZEC vía V3-REVERSAL**. Todo lo demás auto (V1/V4/V5/SWING/TAO/commodities) está apagado por flag o thread comentado.

---

## 3. Estado actual

### 3.1 Hecho esta sesión (06-20, 8 commits en `main`, pusheados)

- **Poda A** (`427af0f`) — TAO fuera de auto-scan; `scalper_shorts_bot.py` borrado (504L).
- **F0 revivir** (`6a42108`) — persistencia `TRACKER_DB` + `makedirs` (soporta Railway Volume `/data`); Groq schema verificado OK; `MACRO_FEED_ENABLED` kill-switch (off) — gateó 2 feeds yfinance + mató noise CL=F.
- **F1 reconfigurar** (`6a42108`) — `SYMBOLS=["ZEC"]`; swing a ZEC en pausa; `HMM_ENABLED` flag (off); `SENTINEL_AUTO_SYMS=["ZEC"]` (`9d67316`) cortó el 429 TPM Groq.
- **F2 telemetría** — verificada e2e: trade V3 ZEC → resuelve WIN +9.52% → `get_intel_ab_stats` 1/1. La cadena log→resolve **ya existía**; el "0 resueltos" era la DB efímera (arreglada en F0).
- **F3 disciplina** — regla-gate documentada (no spec N+1 sin ≥N trades resueltos de N) en `docs/FENIX.md`.
- Verificado en vivo local: bootea, 6 threads + watchdog, scanea ZEC, persiste, cockpit `/pos`+levels OK, sin crashes/429/noise.
- Docs: `docs/FENIX.md`, `docs/LEARNINGS.md`, `docs/SPEC_WIRE_AUDIT.md` (header stale), `_NEXT.md`.

### 3.2 Lo único pendiente — DEPLOY Railway (cloud, acción de Fernando)

Runbook completo en `docs/FENIX.md`. Resumen:
- [ ] **Volume** montado en `/data` (MUST — sin esto el histórico se borra cada redeploy).
- [ ] Env var **`TRACKER_DB=/data/trades.db`** (MUST).
- [ ] Redeploy (autoDeploy ON → el push ya lo disparó; verificar).
- [ ] Checklist "está vivo": `/apihealth` 🟢 · alerta/scan ZEC llega · `total` no baja a 0 tras redeploy · logs sin `400` Groq.
- Seed del histórico viejo = **OPCIONAL** (92 trades = perdedores jubilados, saltar).

---

## 4. Roadmap por fases — "trabajarlo a fondo"

> Orden por impacto/esfuerzo. **F4 está bloqueada por el deploy (§3.2) y por acumular trades reales.** Nada de specs nuevas hasta el veredicto del experimento (regla-gate F3).

### Fase 4 — Veredicto del experimento ZEC (P0, alto impacto / bajo esfuerzo)
**Disparador:** deploy hecho + ~30 días corriendo + ≥20 trades resueltos en `intel_outcomes`.
- Correr `/api/metrics/intel_ab` → WR + avg_pnl del V3-REVERSAL ZEC real (no backtest).
- **Decisión binaria:** mostró edge (WR/pnl > baseline con n≥20) → primer caso real de spec con gate, considerar reactivar 1 símbolo más. NO mostró edge → matar el auto entero, vigil queda cockpit puro.
- Esta fase **es la razón de ser de las otras**. No adelantar §4.2–4.4 antes del veredicto.

### Fase 5 — Adelgazar archivos gordos CON telemetría que lo justifique (P1, medio/medio)
6 archivos >800L: `gemini_analyzer` (1460), `scalp_alert_bot` (1277), `strategies` (1179), `telegram_commands` (1044), `tracker` (1026), `app` (729 ~límite).
- **Solo extraer lo que el veredicto deje vivo.** Si el auto muere, `strategies.py` se desinfla solo (borrar V1/V4/V5/SWING dead paths). Extraer antes = pulir código que quizá se borra.
- Prioridad de extracción si el código se queda: `strategies.py` (separar V3 vivo de strategies muertas) > `gemini_analyzer.py` (extraer agentes a `agent_panel.py`, ya sugerido en CLAUDE.md).

### Fase 6 — Jubilar formalmente las specs muertas (P1, bajo esfuerzo, alta higiene)
~664L zombi: `onchain.py` (Spec 010 Etherscan) + `social_quant.py` (Spec 013 Reddit). Importados pero las creds nunca se setearon en 3+ semanas.
- **Decisión abierta (§5):** borrar vs dejar apagado tras flag. Recomendación venom: **borrar** — el filtro madre de LEARNINGS ("¿cerró un outcome o informó una decisión en 3 meses?") los reprueba. Si Fernando quiere conservarlos como hipótesis futura → mínimo gatearlos tras un flag explícito `ONCHAIN_ENABLED`/`SOCIAL_ENABLED` (default off) para que dejen de ramificar silenciosamente.
- Limpiar también la tabla de wires en `docs/SPEC_WIRE_AUDIT.md` (ya marcada stale).

### Fase 7 — Fortalecer el cockpit (P2, valor incremental, depende de §4)
El cockpit es el activo que sobrevive pase lo que pase con el auto. Candidatos (priorizar tras el veredicto):
- UX Telegram: agrupar los 46 comandos en menú / reply-keyboard por contexto (intel / posiciones / salud / niveles).
- Comandos faltantes detectados: `/regime SYMBOL` (debug régimen — Spec 009.7 backlog), persistir contador grounded_search (Spec 014.6).
- Niveles definidos por Fernando como ciudadanos de primera clase del cockpit (no derivados de specs auto).

### Fase 8 — Postgres si algún día >1 instancia (P3, bajo, hipotético)
SQLite + Volume `/data` es suficiente para 1 instancia. **No tocar** salvo que haya >1 worker escribiendo `trades.db` concurrente (no es el caso hoy). Registrado para no re-discutirlo.

---

## 5. Decisiones abiertas (requieren input de Fernando)

1. **Módulos muertos — ¿borrar o solo apagar?** `onchain.py` + `social_quant.py` (~664L) + `commodities_bot.py` + `manual_positions_monitor.py`. Recomendación venom: borrar los 2 primeros (zombi probado), commodities/manual_monitor pueden quedar comentados si hay intención de revivir. *(Decisión, no acción — esto es planeación.)*
2. **Experimento ZEC — ¿sombra/paper o real?** Hoy corre como experimento medido. Si a 30d muestra edge: ¿pasa a ejecución real (tamaño chico) o sigue paper/shadow indefinido? Define el upside de "ganó el experimento".
3. **¿Se reactiva algún símbolo además de ZEC?** Default Fénix = no, hasta veredicto. Si el experimento gana, ¿cuál sería el candidato #2 y con qué criterio (no por apego, regla kill-WR<10%/n>15)?
4. **Specs backlog (Sprint A–E en `_NEXT.md`) — ¿se jubilan?** 20+ specs encoladas. La regla-gate F3 las congela. ¿Se borran del backlog o se dejan como "ideas si el auto revive"?

---

## 6. Riesgos / deuda técnica conocida

- **DB efímera (riesgo activo hasta el deploy).** Sin Volume `/data` + `TRACKER_DB`, todo `intel_outcomes` se borra en cada redeploy → el experimento ZEC nunca acumula los 20 trades → veredicto imposible. **Es el bloqueante #1.**
- **Bot muerto silencioso (riesgo histórico).** Murió 3 semanas sin alarma. Mitigado con `api_health` + `thread_health` watchdogs, pero la lección: medir USO real, no actividad. Confirmar que la alerta `thread DEAD` llega al Telegram tras el deploy.
- **Groq free tier 8000 tok/min.** `SENTINEL_AUTO_SYMS=["ZEC"]` corta el 429, pero cualquier expansión de símbolos en Sentinel lo revienta de nuevo. Tener presente antes de reactivar símbolos.
- **6 archivos >800L** — deuda de tamaño (regla del repo: 600L). No urgente; se ataca en §5 cuando el veredicto defina qué código sobrevive.
- **Dos sistemas de régimen solapados** — `regime_hmm.py` (Spec 009, dormant) vs `regime_transitions.py` (Spec 002.5, vivo) clasifican lo mismo por caminos distintos. Si el auto sobrevive, consolidar en uno.
- **~664L zombi** (`onchain`/`social_quant`) ramifican en el path principal sin devolver data → costo de mantenimiento sin retorno. Ver §4 Fase 6.
- **A/B framework probado e2e pero con n=1.** La cadena funciona en local; en prod nunca acumuló muestra. El veredicto a 30d es el primer test real de que la telemetría cierra el loop bajo carga.

> **Filtro madre para cualquier "renovar" (de LEARNINGS.md):** ¿esto cerró aunque sea un outcome, o informó aunque sea una decisión, en los últimos 3 meses? Si no → se jubila, no se renueva.
