# LEARNINGS — Zenith/Scalp Bot (destilado venom, 2026-06-20)

> Qué funcionó, qué falló, y qué patrones llevarse al próximo sistema. Fundamentado en data verificada del código y `trades.db`, no en memoria. Escrito al inicio del Plan Fénix.

## Data dura (no de memoria)
- **Win rate global 18.7%** (17W / 74L, n=91). ZEC 30% (lo *menos* malo, no bueno), TAO 3% (32 trades), OIL 40% (n=5, ruido).
- **Los 92 trades cerrados son 100% SWING/COMMODITY.** V3-REVERSAL nunca cerró un outcome en producción → su "~60% histórico" es backtest, no real.
- **`intel_outcomes`: 8 rows logged, 0 resueltas** en 3 meses. El framework A/B nunca midió nada.
- **36 specs** (no 25) con sub-decimales (002.5, 002.6, 002.7, 022.5, 022.6, 022.6.3…) = micro-iteración sin gate.
- Bot **muerto desde 27-may**, nadie lo notó hasta el 20-jun (~3 semanas). Las últimas 5 sesiones de `_NEXT.md` fueron 100% infra/firefighting (geo-block, API cap, watchdog, HYPE) — nadie tocó "¿las señales ganan dinero?".

---

## 1. LO QUE FUNCIONÓ (capital reusable)
- **`exchange_singleton.py` — fallback multi-exchange** (OKX→KuCoin→Bybit→Binance). Resolvió el geo-block 451 de Railway de raíz. Patrón sólido: nunca dependas de un solo feed de precio.
- **`ai_budget.py` — cap duro $10/mes** con auto-tope. Evitó que un loop de IA quemara el presupuesto. Todo sistema con LLM en loop necesita esto desde el día 1.
- **`api_health.py` + `thread_health.py` — watchdogs.** Auto-restart de threads con backoff + alerta Telegram por cambio de estado. Habría avisado del 429 silencioso de Gemini.
- **Cuadrilla Zenith (multi-voz).** Patrón validado — graduó al plugin `cortex-consejo`. El valor estaba en el *consenso multi-perspectiva*, no en justificar señales auto.
- **Intel macro curado manual (PTS/BitLobo).** El único activo con valor demostrado — setups con entry/SL/BE/target reales. Es trabajo humano de Fernando, insustituible. Es lo que de verdad se consumía.
- **`indicators.py` con Wilder smoothing** (RSI/BB/EMA/ATR). Cálculo correcto y sólido.

## 2. LO QUE FALLÓ (honestidad brutal)
- **Spec sprawl sin gate.** 36 specs en ~3 meses, ninguna con un check de "¿la anterior sirvió?" antes de la siguiente. La dopamina estaba en shippear, no en validar edge. Costo: ~20K líneas, 6 archivos >800L, telemetría que nunca cerró.
- **A/B framework construido pero inútil.** `intel_outcomes` loguea pero 0 resoluciones. La causa NO era código (la cadena log→resolve existía) sino: (a) DB efímera borraba rows antes del cierre, (b) solo V3/stock logeaban, no SWING. Se construyó la telemetría pero nunca se cerró el loop de confirmación.
- **TAO: 32 trades a 3% WR.** Se insistió en un símbolo que sangraba. Axioma de Odi Sa ya en CLAUDE.md: "su suerte no está donde usted trabaja" — ignorado 32 veces.
- **Specs muertas por creds nunca seteadas** (Etherscan/Reddit, Specs 010/013/019). ~660L de código zombi que consumía branches sin nunca devolver data. Pendientes desde 27-may.
- **4 engines bot compitiendo** (scalp_alert, swing, commodities, scalper_shorts) — 2 muertos. Confusión de mapa mental.
- **2 sistemas de régimen solapados** (HMM Spec 009 vs state machine Spec 002.5) clasificando lo mismo por caminos distintos.

## 3. PATRONES GENERALIZABLES (reglas pa' el próximo sistema)
1. **No agregar spec N+1 hasta que la telemetría confirme que spec N sirvió.** Define métrica + N-mínimo de trades ANTES de codear. Sin gate = sprawl.
2. **Telemetría encendida en el trade 1, no como spec aparte.** Si lo que mide "qué sirve" no funciona, todo lo demás es fe ciega.
3. **Kill rápido de símbolo con WR<10% en n>15.** No insistir en perdedores por apego.
4. **Persistencia ANTES de cualquier histórico.** DB efímera = toda la telemetría se borra silenciosamente. Volumen/DB persistente es paso 0, no optimización.
5. **Mide USO real, no actividad.** Nº de specs/alertas/símbolos = vanity. La métrica honesta es: ¿alguien lo usó? ¿informó una decisión? (El bot murió 3 semanas sin que nadie lo notara — ese es el dato más duro.)

## 4. VEREDICTO ESTRATÉGICO
No revivir el auto-bot ciego a 18.7% WR. El valor real está en: **(a)** el intel macro manual (PTS/BitLobo), **(b)** la infra reusable (exchange_singleton, ai_budget, api_health, watchdogs), **(c)** Cuadrilla Zenith ya graduada a plugin. Si vuelve a haber señales auto: **1 símbolo (ZEC), telemetría encendida desde el trade 1, kill-switch cableado, fecha de muerte.** → Plan Fénix Opción C: cockpit de intel + 1 experimento ZEC medido con muerte a 30d.

> **Filtro madre pa' "renovar":** ¿esto cerró aunque sea un outcome, o informó aunque sea una decisión, en los últimos 3 meses? Si no → se jubila, no se renueva.
