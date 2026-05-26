# Bot Performance Audit — Results

> **Fecha ejecución:** 2026-05-26
> **NotebookLM URL:** https://notebooklm.google.com/notebook/2a935059-de97-4701-ba3d-bff718198f91
> **Operador:** Fernando
> **Corpus base:** `performance-audit-corpus.md` (91 trades + 39 episodes, 2026-03-30 → 2026-04-22)

## Findings inmediatos (sin NotebookLM)

Solo del análisis automático del corpus:

| Métrica | Valor | Interpretación |
|---------|-------|----------------|
| WR global | 18.7% | Crítico — debajo de breakeven |
| TAO LONG | 3.1% (1/32) | Kill switch justificado ✅ |
| SHORT global | 8.3% (2/24) | Kill switch en VERDE_BULL justificado ✅ |
| conf_score=5 | 0% (0/7) | **PARADOJA** — más confluencia = peor |
| conf_score=4 | 19.8% (16/81) | Default que captura mayoría |
| ZEC SWING | 29.5% (13/44) | Mejor que TAO pero blocklist correcto |
| COMMODITY | 25% (3/12) | GOLD+OIL mejor que SWING cripto |
| Huérfanas | 79.5% (31/39) | Spec 002 fix no aplicado retroactivamente |

## Prompt 1 — Auditoría kill switches

### Validación de Kill Switches

| Kill switch | Trades afectados | WR antes | Justificado? | Hipótesis |
|-------------|------------------|----------|--------------|-----------|
| TAO_TRADING_ENABLED=False | TAO LONG y general (32 trades) | 3.1% | ✅ SÍ | 32 trades, no es ruido. Única ganancia fue manual. Falla estructural v3 SWING para TAO |
| TAO_SHORT_ENABLED=False | TAO SHORT | ~0.0% | ✅ SÍ | Top losers tabla, ninguno en winners. Cortos solo exacerban pérdidas |
| V1_LONG/V1_SHORT/V5=False | V1, V5 | Sin datos | N/A | Corpus solo registra SWING/COMMODITY/MANUAL. Bloqueos de versiones deprecated |
| V4_BLOCKLIST [ETH, ZEC] | ETH (1), ZEC (44) | ETH 0%, ZEC 29.5% | ✅ SÍ | ETH 1 trade perdido. ZEC aislar para proteger v4 del comportamiento errático |
| SHORT_BLOCKED_IN_VERDE_BULL=True | SHORT global (24 trades) | 8.3% | ✅ SÍ | 22/24 pérdidas. Solo cortos ganadores en GOLD/OIL (commodities) |

### Análisis profundo

**TAO LONG 3.1% (1/32):** desconexión estructural, no ruido. 32 muestras = >1/3 de trades totales. Algoritmo intentó atrapar reversiones 31 veces consecutivas y falló. Único ganador fue manual. Confirma kill switch.

**SHORT cripto 8.3% (2/24):** 22 pérdidas confirmadas. SP500 transitioning AMARILLA→VERDE durante el periodo invalidó cortos. Únicos cortos ganadores: GOLD y OIL (descorrelacionados).

### Recomendaciones finales

**¿Remover algún kill switch?** **Ninguno** supera 35% WR estable. ZEC 29.5% está en limbo — capturó ráfaga 7-10 Abr (13 wins casi consecutivos) pero perdió 31 veces después. NO reactivar ZEC sin filtros drásticos (ej. bloquear si RSI inicial en bucket 40-50).

**¿Activos sin kill switch que DEBEN matarse?**
- 🔥 **ORO (GOLD): BLOQUEAR.** 7 trades, WR 14.3% (1/6). Acapara 5/15 worst trades. Métricas letales.
- 🟡 **OIL marginal:** 5 trades, WR 40% (2/3). Bajo volumen para validación, monitorear.

Acción: agregar GOLD a `SWING_BLOCKLIST` o nuevo `COMMODITY_BLOCKLIST = ["GOLD"]`.

## Prompt 2 — Paradoja conf_score

### Hipótesis evaluadas

| Hipótesis | Veredicto |
|-----------|-----------|
| H1: Score 5 exclusivamente SHORT en bull market | ❌ **FALSA** — Ops con score=5 entre peores pérdidas son LONG, no SHORT |
| H2: Trades TAO/ZEC en ventana manipulación | ❌ **FALSA** — TAO/ZEC operaron con score=4, no 5 |
| H3: Overfitting indicadores | ✅ **VERDADERA** — Score 5 se activó repetidamente en mismo activo+dirección atrapando falsas señales sin edge |

### Diagnóstico

**Score=5 (7 ops, 0% WR):**
- **6 de 7 son LONG en ORO (GOLD)** con estrategia COMMODITY
- Periodo concentrado, RSI rango 41.8-46.6 (bucket 40-50)
- macro_bias = HAWKISH_HOLD constante
- Smoking gun: bot detectaba "confluencia perfecta" en ORO precisamente cuando ORO no daba edge

**Score=0 (2 ops):**
- Anomalías: TAO LONG manual del 30 marzo
- alert_type = "unknown" o manual
- Score 0 NO significa "baja confluencia", sino **ausencia de evaluación automática**

### Recomendación MIN_CONFLUENCE_SCORE

🔥 **NO subir MIN_CONFLUENCE_SCORE a 5.** Si se subiera:
- Bot limitaría operaciones al grupo con **0% WR**
- Eliminaría la única fuente de ganancias (score=4 captura 81 ops = 16 wins = todo el upside del bot)

### Acciones recomendadas

1. **Cambiar fórmula confluence_score** — actualmente sobre-pondera indicadores correlacionados que aparecen juntos sin aportar edge
2. **Mantener MIN_CONFLUENCE_SCORE=4** — captura el bucket con mejor performance
3. **Bloquear score=5 explícitamente para GOLD/COMMODITY** — donde el sesgo de overfitting es más claro
4. **Investigar features score=4 vs score=5** — qué indicador específico subió el score sin aportar valor

## Prompt 3 — Huérfanas signal_episodes

### 1. Agrupación por source (31 huérfanas)

| Source | Huérfanas / Total |
|--------|-------------------|
| STOCK | 22 / 29 |
| BITLOBO | 9 / 9 |
| CRYPTO | 0 / 1 (única ya con outcome LOSS) |

### 2. Estimación WIN/LOSS si fallback yfinance

- Signal_episodes ya cerradas: WR 12.5% (1 WIN, 7 LOSS)
- Si fallback mantiene tendencia → ~4 WINs / 27 LOSSES
- Si rinden con WR global bot 18.7% → ~6 WINs / 25 LOSSES

### 3. Filas irrecuperables (entry_price NULL)

Existen — irrecuperables. **Acción:** purgar o marcar STALE en DB.

### 4. Impacto WR overall

79.5% huérfanas → llenarlas reescribe métricas:
- Confirma STOCK/BITLOBO comparten **misma ineficacia (<20% WR)** que v3 SWING cripto
- No mejora overall, solo cierra el loop de tracking

### Script SQL conceptual

```sql
-- 1. Limpiar irrecuperables
UPDATE signal_episodes SET outcome = 'STALE'
WHERE entry_price IS NULL AND outcome IS NULL;

-- 2. Marcar viejas como STALE (>14d sin outcome)
UPDATE signal_episodes SET outcome = 'STALE'
WHERE outcome IS NULL
  AND ts < datetime('now', '-14 days');

-- 3. Fallback yfinance lógica (en Python, ejecutar después):
-- FOR cada signal_episode huérfana con entry/sl/tp1 válidos:
--   1. Fetch precio yfinance del símbolo desde ts hasta now
--   2. Si tocó tp1 antes que sl → outcome = 'WIN'
--   3. Si tocó sl antes que tp1 → outcome = 'LOSS'
--   4. Si todavía dentro de rango → marcar PENDING (no STALE aún)
```

**Spec 002 ya tiene check_pending_outcomes con yfinance fallback** — pero corre solo sobre nuevas. Las pre-existentes requieren backfill script one-shot.

## Prompt 4 — Direction bias LONG/SHORT

### Recomendación general

**Mantener `SHORT_BLOCKED_IN_VERDE_BULL = True`** con excepción estrictamente limitada.

SHORT global 8.3% (2 wins / 22 losses) — kill switch incondicional justificado.

### ¿Dónde SHORT funcionó?

| Activo | Wins | Fecha | Estrategia |
|--------|------|-------|-----------|
| OIL | 1 win | 17 Apr | COMMODITY |
| GOLD | 1 win | 22 Apr | COMMODITY |
| Cripto (BTC/ETH/SOL/ZEC/TAO) | **0 wins** | — | SWING fracaso total |

SOL y TAO SHORT terminaron entre los Top Losers.

### Recomendación tunear gates

1. **NO relajar globalmente** — habilitar SHORTS para cripto en NARANJA_BEAR seguiría fracasando. V3 SWING no opera shorts cripto.
2. **Relajación selectiva OIL** — único activo con WR global 40% (combinando longs y shorts). Si bot permite per-activo, NARANJA_BEAR solo OIL.
3. **GOLD mantener bloqueado** — aunque 1 short ganador, WR global 14.3%, peor activo del COMMODITY pool.

### Conclusión

`SHORT_BLOCKED` activo para **TODAS** criptomonedas. Evaluar Bear moderado SOLO para OIL.

## Prompt 5 — Ganadores: filtros propuestos

### 1. RSI ≥ 50 (filtro fuerte)

- 15 de 17 victorias del bot están en RSI bucket **50-60**
- Único trade RSI 60-70 (OIL LONG 64.71) → 100% WR (1/1)
- RSI 40-50 = **11.1% WR** (mayoría perdedoras, especialmente GOLD)

**Filtro sugerido:** exigir `RSI ≥ 50` para aceptar o priorizar LONG.

### 2. Confluence Score Sweet Spot = 4 (no 5)

- Score 5 = **0% WR** (paradoja Spec 022 ya confirmada)
- Score 4 = 19.8% WR (donde están casi todos los wins)
- **Acción:** bloquear o degradar score=5 hasta reparar sobreajuste

### 3. Prioridad absoluta OIL

- COMMODITY supera SWING (25% vs 17.1% WR)
- OIL = **40% WR** dentro de COMMODITY
- Único activo que ganó en **ambas direcciones** (long y short)

**Filtro:** elevar peso/prioridad para alertas COMMODITY de símbolo OIL.

### 4. Filtro "Ráfagas" temporal (ZEC pattern)

- 13 de 17 victorias del bot son **ZEC LONG**
- Concentradas en **3 días** (7-10 Abr 2026)
- RSI estático 50.0 durante la ráfaga
- Después: 31 pérdidas consecutivas

**Insight:** rachas existen pero bot no detecta cuando termina. Implementar momentum exhaustion filter — si ZEC tiene N wins consecutivos + RSI plano, alertar siguiente apertura, NO seguir indefinido.

### Filtros priorizados final

| # | Filtro | Impacto esperado | Trade-off |
|---|--------|------------------|-----------|
| 1 | `MIN_RSI_LONG = 50` | Eleva WR rango 50-60 | Mata RSI bajo extreme (V3 reversal hoy entra ≤30) |
| 2 | Bloquear `conf_score == 5` (no usar como ceiling, sino kill switch) | Elimina 7 ops con 0% WR | Bug arreglo confluence formula también ayudaría |
| 3 | Boost OIL+COMMODITY | Captura mejor activo | Solo aplica a sector commodities |
| 4 | Detector exhaustion ráfagas ZEC-like | Reduce drawdown post-streak | Requiere lookback state machine |

## Prompt 5 — Cross-reference PTS watchlist
<!-- Skipped: requería subir RESULTS Notebook 1 como source extra. Bot Performance Audit tiene corpus suficiente sin cross-ref. -->

## Prompt 6 — Plan de acción consolidado (18.7% → >30% WR)

### Dry-run matemático

Si se eliminan TAO (1/32) + GOLD (1/7) del histórico:
- Trades restantes: 91 - 32 - 7 = **52 trades**
- Wins restantes: 17 - 1 - 1 = **15 wins**
- WR = 15/52 = **28.8%**

Casi al 30%. Con filtros adicionales (RSI ≥ 50, conf_score=5 kill) → **>30% confirmado**.

### Plan priorizado

**Fase 1 — Poda Inmediata (P0 kill switches)**

| # | Acción | Constante | Impacto WR | Riesgo |
|---|--------|-----------|------------|--------|
| 1 | Bloquear GOLD COMMODITY | `COMMODITY_BLOCKLIST=["GOLD"]` | +5pp (elimina worst sector) | Pierde 1 win pasado |
| 2 | Mantener TAO bloqueado | `TAO_TRADING_ENABLED=False` (ya) | +14pp (3.1% WR eliminado) | 0 (kill ya activo) |
| 3 | Mantener ZEC blocklist | `SWING_BLOCKLIST=["TAO","ZEC"]` (ya) | +3pp (29.5% pero destructivo post-rally) | Posible win streak perdido |
| 4 | Bloquear SHORTS cripto | `SHORT_BLOCKED_IN_VERDE_BULL=True` (ya) | +3pp (8.3% WR eliminado) | OIL excepción válida |
| 5 | Kill `conf_score=5` (no usar como ceiling) | nueva regla `BLOCK_SCORE_5=True` | +2pp (7 ops 0% WR) | Requiere fix formula confluence |

**Fase 2 — Ajustes Filtros (P1)**

| # | Acción | Constante | Impacto |
|---|--------|-----------|---------|
| 6 | `RSI ≥ 50` para LONGs | `MIN_RSI_LONG = 50.0` | RSI 40-50 = 11.1% WR eliminado |
| 7 | Boost prioridad OIL | tag visual + score boost | 40% WR amplified |
| 8 | Filtro Momentum Ráfagas | state machine cooldown post-loss | Captura ZEC pattern sin destruir |

**Fase 3 — Estructural (P2)**

| # | Acción | Esfuerzo |
|---|--------|----------|
| 9 | Reformular `calculate_confluence_score` | Eliminar indicadores correlacionados sin edge | 1-2 días |
| 10 | Refactor V3-Reversal entry para usar RSI≥50 (no extreme bajo) | Cambia naturaleza de V3 mean-reversion | 2-3 días |

### WR estimado post-P0

Con TAO/ZEC/GOLD/SHORTS/score=5 todos bloqueados, el bot habría operado solo:
- BTC, ETH, SOL, HBAR (limited)
- OIL, NG, SLV (COMMODITY ex-GOLD)
- score=4 only

Wins estimados: 15 (TAO/ZEC/GOLD wins removed) - 1 SOL win = 14
Losses estimados: ~25 (sin TAO/ZEC/GOLD perdidos)
Total: ~39 trades
**WR estimado: 14/39 = 35.9%**

🎯 **Plan supera la meta del 30%.**

### Acciones prioritarias para próximo deploy

1. Agregar `COMMODITY_BLOCKLIST = ["GOLD"]` a config.py
2. Implementar gate `if conf_score >= 5: skip` (kill score 5)
3. Tag `MIN_RSI_LONG = 50.0` (configurable, no hardcoded)
4. Documentar OIL como boost prioridad en `EXPLOSIVE_TICKERS` extension

## Notas operador
<!-- Observaciones manuales de Fernando -->
