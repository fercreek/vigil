# Learning Log — Scalp Bot / Zenith

Auto-reflexión por sesión. Objetivo: cómo prompteamos a Claude mejor la próxima vez.

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
