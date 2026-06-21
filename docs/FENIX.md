# PLAN FÉNIX — Runbook de deploy + regla de disciplina

> Estado al 2026-06-20: trabajo local hecho y verificado (poda A + F0 + F1 + F2). Falta el deploy en Railway (cloud).

## Qué es el Fénix (1 párrafo)
El bot pasó de **auto-alert ciego multi-símbolo** (18.7% WR, los 91 trades cerrados eran SWING/COMMODITY) a **cockpit de intel + 1 experimento auto ZEC medido**. El experimento = V3-REVERSAL sobre ZEC (nunca testeado en prod), telemetría encendida, **fecha de muerte 30d** (se prueba o se mata). Ver `docs/LEARNINGS.md` para el porqué.

---

## RUNBOOK Railway (cloud — lo ejecuta Fernando en el dashboard)

### Paso 1 — Volume (MUST). Sin esto el histórico se borra cada redeploy.
- Servicio del bot → **Settings → Volumes → + New Volume**.
- Mount path: **`/data`** → Save.

### Paso 2 — Env var (MUST).
- **Variables** → New Variable:
  - `TRACKER_DB` = `/data/trades.db`
- (Opcional) `MACRO_FEED_ENABLED` — dejar SIN setear (default off, correcto). Solo poner `true` si algún día yfinance funciona desde Railway.
- (Opcional) `HMM_ENABLED` — dejar sin setear (default off).

### Paso 3 — Redeploy.
- El push a `main` ya dispara redeploy (autoDeploy ON). Si no, **Deployments → Redeploy**.

### Paso 4 — Seed del histórico viejo (OPCIONAL — saltar).
Los 92 trades viejos son SWING/COMMODITY (los perdedores jubilados). La telemetría que importa es la NUEVA de V3 ZEC. **No vale la pena seedear.** Si algún día se quiere: subir `./trades.db` local al volumen vía Railway CLI/shell a `/data/trades.db` con el bot detenido.

### Paso 5 — Verificar "está vivo" (checklist).
- [ ] Bot corre >24h sin crash-restart (no llega alerta `thread DEAD` a Telegram).
- [ ] `/apihealth` en Telegram → Gemini/Groq/data_feed 🟢.
- [ ] Llega ≥1 línea de scan/alerta ZEC (o reporte Market Status).
- [ ] Tras un redeploy: `/metrics` o `/api/metrics/intel_ab` → `total` NO baja a 0.
- [ ] Logs sin `400` de Groq. BRI muestra `OFF` (no `0 NEUTRAL` falso).

---

## REGLA DE DISCIPLINA (F3 — el gate que mata el sprawl)

> Las 36 specs encimadas pasaron porque NUNCA hubo un gate de "¿la anterior sirvió?". Esta regla lo impone.

**Una feature/spec N+1 NO se mergea hasta que `intel_outcomes` tenga ≥N trades resueltos del cambio N, con señal clara (WR o pnl medio) vs baseline.**

Checklist antes de codear CUALQUIER spec nueva:
1. **Baseline:** correr `/api/metrics/intel_ab` y anotar WR + avg_pnl actuales.
2. **Métrica + N-mínimo:** la spec declara EN `intel_outcomes` qué métrica mueve y cuántos trades necesita (default N≥20).
3. **Veredicto:** tras N trades, si no movió la aguja → se apaga por flag (no se itera en sub-decimales 022.5.1.2…).

**Intel macro = manual on-demand, NO gate auto:** PTS/BitLobo (`bitlobo_agent.py`) y todo lo que dependa de env vars nunca seteadas (Etherscan/Reddit) quedan como comandos Telegram, no cableados a la confluencia.

**Decisión 30d del experimento ZEC:** con la telemetría de F2, evaluar si V3 ZEC mostró edge. Si no → matar el auto entero (cockpit puro). Si sí → primer caso real de spec con gate.

---

## Métrica de éxito a 30 días (honesta, no vanity)
1. **Uso deliberado:** Fernando consulta el cockpit (`/intel /macro /pos /bitlobo`) ≥3 de cada 5 días hábiles por iniciativa propia.
2. **Decisión informada:** ≥2 posiciones manuales gestionadas usando intel del cockpit.
3. **Experimento ZEC:** ≥20 trades resueltos en `intel_outcomes` → veredicto auto vive/muere.

**Anti-métrica (prohibido celebrar):** nº de alertas, símbolos cubiertos, specs nuevas, WR con n<20.
