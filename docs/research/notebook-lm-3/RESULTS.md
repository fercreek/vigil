# Bot Performance Audit — Results

> **Fecha ejecución:** PENDIENTE
> **NotebookLM URL:** PENDIENTE
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
<!-- PEGAR OUTPUT NOTEBOOKLM -->

## Prompt 2 — Paradoja conf_score
<!-- PEGAR OUTPUT NOTEBOOKLM -->

## Prompt 3 — Huérfanas signal_episodes
<!-- PEGAR OUTPUT NOTEBOOKLM -->

## Prompt 4 — Direction bias LONG/SHORT
<!-- PEGAR OUTPUT NOTEBOOKLM -->

## Prompt 5 — Cross-reference PTS watchlist
<!-- PEGAR OUTPUT NOTEBOOKLM -->

## Prompt 6 — Plan de acción consolidado
<!-- PEGAR OUTPUT NOTEBOOKLM -->

## Notas operador
<!-- Observaciones manuales de Fernando -->
