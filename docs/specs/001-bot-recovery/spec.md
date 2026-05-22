# Spec 001 — Bot Recovery + Pipeline Repair

> **Status:** OPEN
> **Created:** 2026-05-22
> **Owner:** Fernando
> **Severity:** P0 — bot no opera como debería

## Problema raíz

Bot **mudo desde 2026-04-22** (30+ días sin trade nuevo). Win rate global estancado en 18.7% (objetivo >55%). Múltiples bugs y configuraciones huérfanas detectadas en auditoría.

## Síntomas medidos (May 22 audit)

| # | Síntoma | Métrica | Esperado | Severidad |
|---|---------|---------|----------|-----------|
| S1 | Bot sin trades nuevos | último `open_time` = 2026-04-22 | ≥ 1/semana | P0 |
| S2 | conf_score=5 (máx confianza) → 0% WR | 0/7 wins | > 55% | P0 |
| S3 | SHORT WR | 8.3% (2/24) | > 40% | P1 |
| S4 | TAO sigue activo con WR muerto | 3.1% (1/32) | kill switch | P1 |
| S5 | ZEC degradó de winner a perdedor | 56.5% → 29.5% | re-tunear o pausar | P1 |
| S6 | `DEFENSIVE_SECTORS` no consumido | 0 refs en código | wire en strategies/scalp_alert_bot | P2 |
| S7 | `SECTOR_CLUSTERS` no consumido | 0 refs en código | exposure cap activo | P2 |
| S8 | `VIX_DORMANT_THRESHOLD` no consumido | 0 refs en código | macro gate aplica | P2 |
| S9 | `SP500_VERDE/NARANJA` no aplicado | macro regime gate ausente | dynamic regime check | P2 |
| S10 | Earnings suppression solo FOMC | NVDA/OKLO/TSLA earnings sin filtro | extender FOMC logic | P2 |
| S11 | Watchlist nuevos sin niveles | RGTI, CORZ, CIFR, JNJ, KO, CL: entry=None | calcular ATR-based | P3 |

## Goals (qué se considera resuelto)

1. **Bot abre ≥1 trade real en próxima ventana de 72h** post-deploy.
2. **conf_score=5 vuelve a > 50% WR** o se elimina del scoring.
3. **SHORT WR > 30%** o queda desactivado por símbolo.
4. **TAO kill switch activado** (igual que V1-SHORT en config).
5. **Macro gates (VIX_DORMANT, SP500_REGIME, DEFENSIVE_SECTORS, SECTOR_CLUSTERS) wired** en pipeline real de señales.
6. **Earnings suppression** extendido a watchlist crítica.
7. **Niveles ATR-based** para 6 tickers nuevos sin entry.

## Non-goals

- Refactor de arquitectura completo.
- Migrar a nuevo broker.
- Nuevas estrategias (V6, V7).
- Dashboard nuevo.

## Dependencias

- `trades.db` (auditoría)
- `config.py` (kill switches, gates)
- `strategies.py` (consume gates)
- `scalp_alert_bot.py` (loop principal)
- `gemini_analyzer.py` (Cuadrilla Zenith, contexto macro)

## Riesgos

- Cambiar threshold sin backtest → empeorar WR.
- Kill switch en TAO pierde futura recuperación.
- Wire de macro gates mal aplicado → suprime longs válidos en bull market.

## Plan de ataque

Ver `plan.md` y `tasks.md`. Estrategia: spawn agents paralelos por área (investigación + fix), consolidar en commits chicos por síntoma.
