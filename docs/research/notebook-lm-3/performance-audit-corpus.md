# Bot Performance Audit — Corpus (trades.db local snapshot)

> **Snapshot date:** 2026-05-26 (DB local, último trade 2026-04-22)
> **Periodo cubierto:** 2026-03-30 → 2026-04-22 (~3.5 semanas)
> **Tablas:** `trades` (91 rows) + `signal_episodes` (39 rows)
> **NOTA:** Esta DB es local. Para análisis vivo, regenerar con DB de Railway. Constantes Spec 003+004 (May-25/26) NO están reflejadas — predates them.

## 1. Schema relevante

**`trades`:** id, symbol, type (LONG/SHORT), entry/sl/tp prices, status, open_time, close_time, strategy_version, rsi_entry, bb_status, atr, elliott_wave, conf_score, macro_bias, alert_type, is_manual, be_moved, partial_pct.

**`signal_episodes`:** id, ts, symbol, strategy, direction, rsi, usdt_d, bb_pos, ema_trend, confluence, atr_pct, outcome (None/WIN/LOSS), outcome_pnl, entry/sl/tp1, source (STOCK/CRYPTO/BITLOBO).

## 2. Distribution overall

### Status
| Status | Count | % |
|--------|-------|---|
| LOST | 74 | 81.3% |
| FULL_WON | 14 | 15.4% |
| PARTIAL_CLOSED | 2 | 2.2% |
| WON | 1 | 1.1% |

**Win rate global:** 14 FULL_WON + 1 WON + 2 PARTIAL = 17/91 = **18.7%**.

### Trades por símbolo
| Símbolo | Trades | WON | LOST | WR% |
|---------|--------|-----|------|-----|
| ZEC | 44 | 13 | 31 | 29.5% |
| TAO | 32 | 1 | 31 | 3.1% |
| GOLD | 7 | 1 | 6 | 14.3% |
| OIL | 5 | 2 | 3 | 40.0% |
| SOL | 1 | 0 | 1 | 0.0% |
| ETH | 1 | 0 | 1 | 0.0% |
| BTC | 1 | 0 | 1 | 0.0% |

### Por strategy_version
| Strategy | Trades | WON | LOST | WR% |
|----------|--------|-----|------|-----|
| SWING | 76 | 13 | 63 | 17.1% |
| COMMODITY | 12 | 3 | 9 | 25.0% |
| MANUAL | 3 | 1 | 2 | 33.3% |

### Por dirección
| Tipo | Trades | WON | LOST | WR% |
|------|--------|-----|------|-----|
| LONG | 67 | 15 | 52 | 22.4% |
| SHORT | 24 | 2 | 22 | 8.3% |

### Por conf_score
| Score | Trades | WON | LOST | WR% |
|-------|--------|-----|------|-----|
| 0 | 2 | 1 | 1 | 50.0% |
| 3 | 1 | 0 | 1 | 0.0% |
| 4 | 81 | 16 | 65 | 19.8% |
| 5 | 7 | 0 | 7 | 0.0% |

### Por RSI entry (buckets)
| RSI bucket | Trades | WON | LOST | WR% |
|------------|--------|-----|------|-----|
| <30 | 0 | 0 | 0 | 0.0% |
| 30-40 | 1 | 0 | 1 | 0.0% |
| 40-50 | 9 | 1 | 8 | 11.1% |
| 50-60 | 80 | 15 | 65 | 18.8% |
| 60-70 | 1 | 1 | 0 | 100.0% |
| 70+ | 0 | 0 | 0 | 0.0% |

## 3. Signal episodes (39 rows)

### Outcome distribution
| Outcome | Count |
|---------|-------|
| None (huérfana) | 31 |
| LOSS | 7 |
| WIN | 1 |

**Huérfanas (sin outcome):** 31/39 = **79.5%**. Audit B en Spec 002 ya identificó esto.

### Por source
| Source | Trades | WIN | LOSS | None |
|--------|--------|-----|------|------|
| STOCK | 29 | 1 | 6 | 22 |
| BITLOBO | 9 | 0 | 0 | 9 |
| CRYPTO | 1 | 0 | 1 | 0 |

## 4. Top losers (worst conf_score / RSI extreme outliers)

| Symbol | Type | Entry | RSI | Conf | Strategy | Open | Close |
|--------|------|-------|-----|------|----------|------|-------|
| GOLD | LONG | 4811.0 | 41.81990881003848 | 5 | COMMODITY | 2026-04-20 | 2026-04-22 |
| SOL | SHORT | 85.26 | 50.0 | 4 | SWING | 2026-04-20 | 2026-04-22 |
| OIL | SHORT | 87.30999755859375 | 55.52557342982326 | 4 | COMMODITY | 2026-04-20 | 2026-04-22 |
| OIL | SHORT | 82.58999633789062 | 34.00675649062046 | 3 | COMMODITY | 2026-04-20 | 2026-04-20 |
| GOLD | LONG | 4811.10009765625 | 45.61640587249537 | 5 | COMMODITY | 2026-04-17 | 2026-04-20 |
| OIL | SHORT | 88.16000366210938 | 45.39627852447466 | 4 | COMMODITY | 2026-04-15 | 2026-04-17 |
| GOLD | LONG | 4813.89990234375 | 43.35215593740572 | 5 | COMMODITY | 2026-04-15 | 2026-04-17 |
| GOLD | LONG | 4813.89990234375 | 43.35215593740572 | 5 | COMMODITY | 2026-04-15 | 2026-04-15 |
| GOLD | LONG | 4816.7001953125 | 44.4328233356343 | 5 | COMMODITY | 2026-04-15 | 2026-04-15 |
| ETH | LONG | 2363.64 | 50.0 | 4 | SWING | 2026-04-15 | 2026-04-20 |
| BTC | LONG | 74633.18 | 50.0 | 4 | SWING | 2026-04-15 | 2026-04-20 |
| GOLD | LONG | 4822.39990234375 | 46.69101656059224 | 5 | COMMODITY | 2026-04-15 | 2026-04-15 |
| TAO | SHORT | 253.7 | 50.0 | 4 | SWING | 2026-04-14 | 2026-04-20 |
| ZEC | LONG | 367.31 | 50.0 | 4 | SWING | 2026-04-14 | 2026-04-17 |
| TAO | SHORT | 255.5 | 50.0 | 4 | SWING | 2026-04-13 | 2026-04-20 |

## 5. Winners

| Symbol | Type | Entry | RSI | Conf | Strategy | Open | Close | Partial% |
|--------|------|-------|-----|------|----------|------|-------|----------|
| OIL | LONG | 92.91000366210938 | 64.71376416397786 | 4 | COMMODITY | 2026-04-22 | 2026-05-06 | 0 |
| GOLD | SHORT | 4757.89990234375 | 45.000689316389796 | 4 | COMMODITY | 2026-04-22 | 2026-05-06 | 0 |
| OIL | SHORT | 89.9800033569336 | 53.59784837201353 | 4 | COMMODITY | 2026-04-17 | 2026-04-20 | 0 |
| ZEC | LONG | 313.74 | 50.0 | 4 | SWING | 2026-04-09 | 2026-04-09 | 0 |
| ZEC | LONG | 318.25 | 50.0 | 4 | SWING | 2026-04-08 | 2026-04-10 | 0 |
| ZEC | LONG | 323.96 | 50.0 | 4 | SWING | 2026-04-08 | 2026-04-10 | 0 |
| ZEC | LONG | 325.69 | 50.0 | 4 | SWING | 2026-04-08 | 2026-04-10 | 0 |
| ZEC | LONG | 323.54 | 50.0 | 4 | SWING | 2026-04-08 | 2026-04-10 | 0 |
| ZEC | LONG | 269.46 | 50.0 | 4 | SWING | 2026-04-07 | 2026-04-07 | 0 |
| ZEC | LONG | 267.6 | 50.0 | 4 | SWING | 2026-04-07 | 2026-04-07 | 0 |
| ZEC | LONG | 264.32 | 50.0 | 4 | SWING | 2026-04-07 | 2026-04-07 | 0 |
| ZEC | LONG | 264.61 | 50.0 | 4 | SWING | 2026-04-07 | 2026-04-07 | 0 |
| ZEC | LONG | 270.86 | 50.0 | 4 | SWING | 2026-04-07 | 2026-04-07 | 0 |
| ZEC | LONG | 271.12 | 50.0 | 4 | SWING | 2026-04-07 | 2026-04-07 | 0 |
| ZEC | LONG | 271.92 | 50.0 | 4 | SWING | 2026-04-07 | 2026-04-07 | 0 |
| ZEC | LONG | 262.18 | 50.0 | 4 | SWING | 2026-04-07 | 2026-04-07 | 0 |
| TAO | LONG | 313.9 | 50.0 | 0 | MANUAL | 2026-03-30 | - | 0 |

## 6. Macro bias attribution

| macro_bias | Trades | WON | LOST | WR% |
|-----------|--------|-----|------|-----|
| None | 91 | 17 | 74 | 18.7% |

## 7. Alert type

| alert_type | Trades | WON | LOST | WR% |
|-----------|--------|-----|------|-----|
| swing_institutional | 76 | 13 | 63 | 17.1% |
| commodity_conservative | 12 | 3 | 9 | 25.0% |
| unknown | 2 | 1 | 1 | 50.0% |
| manual_long | 1 | 0 | 1 | 0.0% |

## 8. Notas para NotebookLM

- TAO/ZEC ya están en kill switch (Spec 002): `TAO_TRADING_ENABLED=False`, `SWING_BLOCKLIST=['TAO','ZEC']`.
- Esta DB **no tiene** trades de stocks (Spec 002+003 alerts solo via signal_episodes, no trades).
- WR 18.7% indica que estrategia v3 SWING en cripto ha sido pésima en el periodo Apr 2026.
- 79.5% huérfanas en signal_episodes confirma diagnosis de Spec 002 (auto-close yfinance fallback ya implementado, falta time para llenar).
- macro_bias `HAWKISH_HOLD` aplica a todos los trades (constante config.py).