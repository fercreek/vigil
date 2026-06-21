# Learning Log — Scalp Bot / Zenith

Auto-reflexión por sesión. Objetivo: cómo prompteamos a Claude mejor la próxima vez.

---

### 2026-06-20 · Plan Fénix — revivir bot como cockpit + experimento ZEC

**Pros (qué salió bien):**
- Plan mode + AskUserQuestion en la bifurcación estratégica real (Opción C) ANTES de codear. Evitó revivir el modelo fallido (18.7% WR auto) por inercia.
- Verify-before-build pagó: F2 "telemetría rota" no necesitó código (cadena existía; bug raíz = DB efímera F0.1). F0.2 Groq verificado en vivo antes de "arreglar" lo que ya estaba bien.
- Smoke en vivo (correr el binario 60-90s) destapó 2 bugs que el análisis estático (2 Explore + debugger) no vio: 2do macro feed yfinance + el "Groq flaky" era 429 TPM (no schema).
- Commits checkpoint por path explícito (regla #19); tree ajeno intacto. venom en background mientras se podaba.

**Cons (qué se atoró o sobrecomplicó):**
- F0.3 incompleto en 1er pase: gateé solo el macro feed iShares; había un 2do feed yfinance en scalp_alert_bot.py sin gatear. Lo encontró el smoke después, no el análisis upfront.
- `git add` multi-path abortó silencioso por un pathspec sobre archivo ya borrado → commiteó solo el delete, costó un amend.
- `timeout` no existe en macOS (exit 127) → 1 intento de smoke perdido antes de `perl alarm`.

**Consejo Claude Code (cómo prompteamos mejor):**
- Correr el smoke en vivo TEMPRANO (post-F0), no al cierre — es ground-truth; encuentra 429/feeds-fantasma/$0.00 que el snapshot estático no.
- Antes de gatear un "feed": grep exhaustivo de TODAS sus llamadas (`yf.download`/módulo), no confiar en el snapshot. Repos enredados tienen fuentes duplicadas.
- Tras `git add` multi-path: `git diff --cached --stat` antes de commitear.

**Patrón nuevo capturado:** Live-smoke-early > static-analysis-deep en repos con deuda alta. Correr el binario revela más verdad que N agentes de exploración estática.

---

### 2026-06-01 · Monitoreo HYPE (Hyperliquid) — add símbolo + fix loop hardcoded

**Pros (qué salió bien):**
- Probé acceso OKX (ticker + candles vía curl) antes de asumir soporte de exchange → HYPE/USDT confirmado sin perder tiempo con Binance/ccxt local.
- Detecté que `stock_watchlist.py` usa yfinance (acciones) = inútil para HYPE cripto, pivoteé a la ruta `SYMBOLS` sin insistir.
- Fix raíz en vez de parche: cambié el loop a `config.SYMBOLS` en vez de appendear "HYPE" a la lista hardcoded → mata el drift a futuro.
- Precio HYPE vía OKX aislado, sin tocar el batch frágil de `binance_ex.fetch_tickers` (habría roto todos los precios).

**Cons (qué se atoró o sobrecomplicó):**
- 4 deploys + ~4 checks por wakeup persiguiendo "¿por qué HYPE no aparece en el scan?" — el fix real era 1 línea (`scalp_alert_bot.py:851` tenía lista hardcoded, no leía `config.SYMBOLS`).
- Commit 1 agregó HYPE a config asumiendo que el scan lo lee. No lo leía. No tracé al consumidor antes de escribir.

**Consejo Claude Code (cómo prompteamos mejor):**
- Antes de agregar un símbolo/valor a un config: `grep -rn "SYMBOLS\|for sym in" *.py` para ver quién lo CONSUME. Si hay lista hardcoded paralela, esa es la fuente de verdad real.
- Ordenar commits por dependencia (fix plumbing primero), no por orden de descubrimiento → 1 deploy en vez de 4.

**Patrón nuevo capturado:**
- **Trace-the-consumer**: una lista hardcoded paralela a un config es la fuente de verdad real; el config es decorativo hasta reconectarla. Grep el consumidor antes del primer commit.

---

### 2026-05-31 · Bot caído silencioso → Gemini key + Binance 451 + API watchdog

**Pros (qué salió bien):**
- Diagnóstico en capas: reporte all-zeros + circuit breaker UNKNOWN + $0 IA → no asumí "bot fino", fui a Railway logs y hallé la causa real (Gemini 429 spend cap, NO el budget interno $10).
- Distinguí dos caps que se confunden: `MAX_MONTHLY_USD=$10` interno vs spend cap del proyecto Google AI Studio (el que reventó).
- Token nuevo `AQ.Ab8…` no era `AIza…` → lo probé con curl `/v1beta/models` → 200 antes de cablear, no asumí inválido.
- Fix Binance 451 testeado en vivo (venv) ANTES de deploy. Watchdog validado con transición forzada, no solo "compila".

**Cons (qué se atoró o sobrecomplicó):**
- `python` no existe (es `python3`), ccxt solo en `venv/bin/python` — 2 reruns. Checar venv primero.
- `railway variables --set` NO reinicia el contenedor (env vieja en memoria) → 429 seguía. Forcé redeploy.
- Classifier bloqueó dump de `railway variables` (prod read) — correcto, pero perdí turno. Pedir autorización desde inicio.

**Consejo Claude Code (cómo prompteamos mejor):**
- Bots en Railway: `ps aux` local inútil (prod remoto). Ir directo a `railway logs` filtrando spam con `grep -ivE`.
- Secreto con formato raro → validar con llamada barata (curl) antes de cablear, nunca asumir por prefijo.
- Env var de prod cambiada → asumir redeploy explícito requerido, no confiar en auto-deploy.

**Patrón nuevo capturado:**
- Reporte de bot con métricas en cero + un campo "UNKNOWN" = señal de API/infra caída, no "mercado quieto". Verificar infra antes de creer la narrativa de los datos.

### 2026-05-27 · Bot resucitado + spec kit pro + monitor ZEC/TAO/TON

**Pros (qué salió bien):**
- Diagnóstico del freeze rápido: `social_analyzer.py` Gemini sin timeout → thread frozen en TON. Debug con prints `flush=True` fue clave.
- Spec kit en una sesión: 15 checks smoke test + integration test + SPEC_KIT_TRADING.md + signal_logger + market_status_report.py — sistema pasó de 0 visibilidad a monitoreo real.
- Sentinel mejorado: campos entry_zone/sl/tp1/tp2 + voces con roles distintos — alerta mucho más accionable.
- PTS intel integrado bien: web search confirmó datos (OKLO META deal, IREN targets, USDT.D datos) antes de guardar en neural memory.

**Cons (qué se atoró o sobrecomplicó):**
- El fix de timeout tuvo dos bugs consecutivos: primero `with ThreadPoolExecutor` (bloquea en exit), luego indentación mal copiada. Mejor haber escrito la solución daemon thread correcta de entrada.
- Explore agents lanzados en plan mode no pudieron usar herramientas — tuvieron que reintentarse. Perder 2-3 turnos.
- El `GEMINI_TIMEOUT` bug tomó 3 reinicios para confirmar porque los logs no mostraban el timeout warning (usé logger en vez de print flush). Si hubiera puesto print flush desde el principio → 1 reinicio.

**Consejo Claude Code (cómo promptear mejor):**
- Para bugs de threading: pedir primero `print(flush=True)` en el punto sospechoso antes de cualquier "fix" — los logs de `logger` pueden perderse si el thread está colgado.
- Para session larga con múltiples features: dividir en "fix crítico primero, commit, luego features" — esta sesión mezcló todo y costó más context.

**Patrón nuevo capturado:**
- `daemon=True` + `t.join(timeout=N)` → forma correcta de timeout para llamadas Gemini bloqueantes. `ThreadPoolExecutor` con `with` bloquea en `__exit__` si future no terminó.

---

### 2026-05-23 · Alert noise audit + 4 failure modes silenciosos

**Pros (qué salió bien):**
- 3 audits paralelos (B/C/D) lanzados en una sola call de Agent — ahorró ~10 min vs serial
- Caveman mode + TDAH mode combinados → Fernando respondía con 1-3 palabras, decisiones rápidas
- Spec-driven al cierre: spec.md + plan.md + tasks.md documenta el porqué de los 4 commits
- Kill switches en lugar de borrar código → reversible en 1 flag

**Cons (qué se atoró o sobrecomplicó):**
- Asumí que datos locales (DB) reflejaban prod — eran stale Apr 22. Fernando corrigió "los datos son recientes de mayo". Tardé 2 turnos en aceptar que el análisis era a partir del paste de Telegram + código, no DB
- Edit con if/else mal indentado en `scalp_alert_bot.py:1027` la primera vez. Tuve que volver a editar el bloque completo para corregir indentación del panorama
- `_alert_cache` regex de bulk replace metió recursion en `_clear_alert` (matcheó el .pop dentro de la propia función). Fix manual rápido pero error evitable

**Consejo Claude Code (cómo prompteamos mejor):**
- Cuando Fernando pegue alertas de Telegram, NO asumir que la DB local refleja eso. Las alertas son de prod (Railway); local puede estar congelado. Preguntar primero: "¿estos son alerts de Railway o local?" antes de cruzar con DB
- Al hacer Edit con bloques anidados (if/else), siempre Read primero las 5-10 líneas alrededor del cambio para confirmar indentación
- Para refactors regex, NUNCA aplicar sin verificar que el patrón no matchea su propia definición (función auto-referencial). Mejor: hacer 1 replace_all por función y revisar diff antes del siguiente

**Patrón nuevo capturado:**
- Auditorías paralelas con agentes Agent(run_in_background=True) son la herramienta ideal para audit cross-cutting (cost, noise, failure) — pero el reporte agent debe ser self-contained porque luego se consolida sin contexto extra

---

### 2026-05-22 · Bot Recovery Spec 001 (ref)

Ver [docs/specs/001-bot-recovery/](docs/specs/001-bot-recovery/). Cubrió: kill switches V1/V5, FOMC gates, macro régimen wiring. Resultado: bot mudo confirmado, prep para spec-002.

### 2026-05-26 · Sesión continuación — audit wires + UX fixes

**Pros:**
- Audit reveló intel_outcomes=0 en prod → identificó que Sentinel (no V3-Reversal) es la strategy real
- Fix Sentinel intel wire fue de alto impacto: todas las specs 009-023 ahora conectadas al flujo real
- Kill switch ENABLE_TELEGRAM_BUTTONS=False encontrado — explica por qué keyboard nunca actualizó
- `t.split()` pattern para capturar botones sin `/` es limpio y seguro

**Cons:**
- Kill switch llevaba tiempo activo sin que nadie lo notara — falta un audit de config flags al inicio de sesión
- alert_id mismatch (counter vs trade.id) es el tipo de bug que pasa cuando dos features se implementan en sprints distintos sin integration test

**Consejo Claude Code:**
- Antes de implementar features de logging, verificar que el ID usado para correlacionar tablas sea el mismo en sender y receiver — no asumir que `_sid` == `trade.id`
- Cuando keyboard no actualiza en Telegram: siempre verificar kill switches en config.py ANTES de debuggear API/cliente

**Patrón nuevo capturado:**
- `"palabra" in t.split()` = match word-boundary seguro para botones Telegram sin activar falsos positivos en mensajes de texto libre

### 2026-06-01 · Groq LLM Vigil + data hardening (Spec 024)

**Pros (qué salió bien):**
- Diagnosis-first: probé `/api/ai_budget` + railway logs antes de asumir "spend cap" (era free-tier 20/día). Rules #1+#15.
- Research-first (parallel-research 3 agentes, ~6min) para decisión de provider; síntesis usó el outage real como desempate web-vs-comunidad.
- Verify-before-build: probé Groq key + structured `SentinelResponse` antes de cablear → atrapé bug `additionalProperties` (schema strict) en test.
- Catch de diseño: Gemini client lazy → fallback real (eager mataba la función antes del fallback).

**Cons (qué se atoró):**
- "voices empty" ya parchado 2× antes (7d306a7 05-26, 05-31) con guards; root cause (Gemini free-tier + JSON poco confiable) no se nombró hasta hoy. 3 sesiones de síntoma antes del provider.
- 3 muros del classifier (Railway var + 2 push) — no declaré el patrón "cada push pedirá OK" al primer deploy.
- Groq free TPM burst solo visto en prod (research dio RPD, no modeló TPM por-minuto).
- Tests locales: corrí python global sin deps antes de hallar `venv/bin/python`.

**Consejo Claude Code (cómo prompteamos mejor):**
- Síntoma que recurre cross-sesión → grep learning log + commits PRIMERO ("¿ya lo parché?") → si sí, ir a causa raíz/provider, saltar el guard incremental.
- Research de APIs externas: pedir límites TPM/RPM (por-minuto), no solo RPD. Modelar el burst real.
- Deploy con classifier: al primer push, ofrecer regla de permiso de sesión en vez de chocar muro por muro.

**Patrón nuevo capturado:**
- Síntoma recurrente cross-sesión = atacar la capa de abajo (provider/infra), no agregar otro guard. Guard nuevo sobre el mismo síntoma = deuda, no fix.
