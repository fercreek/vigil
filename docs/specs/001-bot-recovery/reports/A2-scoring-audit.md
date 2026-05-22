# A2 — Scoring Audit

**Stats (is_sim=0):** score=5 → 0/7 (0% WR). score=4 → 16/81 (19.8%). score=3 → 0/1. score=0 → 1/2.
**Binomial:** P(0/7 wins | true WR=50%) = 0.78%. Sample small but the issue is **not noise** — it's a single-strategy concentration.

## Where conf_score is computed

Two completely separate scoring systems write to the same DB column. They are not equivalent.

### System 1 — crypto/V1-V5 (`strategies.py:38-95`, `calculate_confluence_score`)

Range 0–7, capped at 7. Factors:

| factor | pts | file:line |
|--------|-----|-----------|
| RSI ≤30 (LONG) / ≥70 (SHORT) | +2 | strategies.py:51-56 |
| RSI ≤40 / ≥60 (weak) | +1 | strategies.py:53,56 |
| Price vs EMA200 in side direction | +1 | strategies.py:59 |
| BB lower/upper touch | +1 | strategies.py:63 |
| USDT.D bias (<8.05 long, >8.05 short) | +1 | strategies.py:67 |
| Elliott "Onda 3" / "Corrección" | ±1 | strategies.py:71-74 |
| Macro LONG bias (SPY>0 AND USDT.D<8.05) | +1 | strategies.py:78-80 |
| NVDA+PLTR cache present | +1 | strategies.py:83-86 |
| Order Block detected | +1 | strategies.py:89 |
| Funding contrarian | +funding_signal | strategies.py:93 |
| social_adj | float added post-return | strategies.py:420 etc |

Then **enforced** at strategies.py:556 `if conf_score < MIN_CONFLUENCE_SCORE` (config = **5**). Per-strategy overrides: V3=4, V4=3, V5=3, SHORT=3, V2-AI internal=4.

### System 2 — commodities (`commodities_bot.py:428-507`)

Range 0–5, **completely different**. Factors (each +1):

| factor | line |
|--------|------|
| EMA50>EMA200 (long) / < (short) | 433-436 |
| RSI 30<x<55 long, RSI>62 short | 442-445 |
| price vs EMA200 | 448-451 |
| DXY filter (gold: <103 long, >103 short; oil: <104/>104) | 456-465 |
| ATR baseline (**unconditional +1 always**) | 472-473 |

Threshold: `MIN_CONFLUENCE=4` (commodities_bot.py:79). Max possible = 5. Score 5 = "all 5 factors aligned".

### System 3 — swing_bot (`swing_bot.py:266`)

**Hardcoded score=4.** Never varies. All 76 `swing_institutional` trades in DB sit at score=4. That's why bucket 4 = 81 trades, ~all swing.

### Tracker write
`tracker.log_trade(..., score=score, ...)` → INSERT `conf_score` column (tracker.py:171,180). Also `_store_pending(...)` (scalp_alert_bot._store_pending) carries `conf_score` from signal → pending → finalized trade.

## conf_score=5 trades (the 7 losers)

| id | symbol | type | alert_type | open_time |
|----|--------|------|-----------|-----------|
| 25 | TAO | LONG | manual_long | 2026-04-08 |
| 77 | GOLD | LONG | commodity_conservative | 2026-04-15 13:23 |
| 80 | GOLD | LONG | commodity_conservative | 2026-04-15 14:38 |
| 81 | GOLD | LONG | commodity_conservative | 2026-04-15 15:11 |
| 82 | GOLD | LONG | commodity_conservative | 2026-04-15 15:41 |
| 84 | GOLD | LONG | commodity_conservative | 2026-04-17 01:19 |
| 89 | GOLD | LONG | commodity_conservative | 2026-04-20 22:47 |

**6 of 7 are GOLD LONG from commodities_bot in a 5-day window.** This is the "6 GOLD LOSSES Apr 15-22 — re-entries en pullback bajista" already documented at commodities_bot.py:523. The 1D-BEAR filter (line 524-528) was **added after** these trades happened to prevent the recurrence.

## Root cause hypothesis

### 1. [Most likely — confirmed] commodity score=5 was easy + GOLD was bleeding intraday during a 1D BEAR phase

In `commodities_bot.py`:
- ATR is **always +1** (line 472-473) — anyone who passes the min-ATR gate gets a free point.
- During Apr 15-22, GOLD: DXY<103 (+1), EMA50>EMA200 (+1), RSI 30-55 (+1), price>EMA200 (+1), ATR (+1) → trivially 5/5.
- Daily bias was BEAR (pullback inside a larger bear leg). Hourly buy-the-dip kept getting stopped.
- The fix (1D bias filter, line 524-528) was added *after* these losses. Comment in code confirms: "Causa de 6 GOLD LOSSES Apr 15-22".

**So score=5 is not "inverted"** — it's correctly summing factors. It's that the commodity score's 5 factors are weak (all 1-pt, EMA-based, no HTF context) and the bot fires repeated re-entries every ~30 min during pullbacks. id 77/80/81/82 fired in **2h17m**, all GOLD LONG, sequential pullback dip-buys → all stopped.

### 2. Score column is a Frankenstein

Three subsystems (crypto strategies / commodities / swing) all write `conf_score` with different scales/semantics. Cross-bucket WR is meaningless because score=5 today means "5/5 commodities" and score=4 means "hardcoded swing default". `MIN_CONFLUENCE_SCORE=5` in `config.py` is **never read by commodities or swing** — only by `strategies.py:556` (V12 long path). Cite: grep shows only `strategies.py` and `backtester.py` import it.

### 3. Sample size caveat

7 trades is small but P(0/7|0.5)=0.78%. Even if true WR were 30%, P(0/7)=8.2%. The bigger story: combined with id 25 (manual_long TAO -$345, already known dead trade), this bucket is structurally biased to losers, not just unlucky.

## Why MIN_CONFLUENCE_SCORE=5 is/isn't enforced

- **Enforced only in** `strategies.py:556` (V12 long path).
- **Not enforced** in commodities_bot.py (uses local `MIN_CONFLUENCE=4`), swing_bot.py (hardcoded 4), scalper_shorts_bot.py, stock_watchlist.py, manual_positions.
- That's why DB has 81 trades at score=4 despite global config saying 5 — those came from other modules with their own thresholds.

## Recommended fix (3 options)

### Option A — Gate at 4, eliminate score=5 entries from commodity quick-reentry
```python
# commodities_bot.py — add reentry cooldown for HIGH score signals
# After line 502 (if long_score >= MIN_CONFLUENCE)
if score >= 5 and (time.time() - _last_alert.get(key, 0)) < 4*3600:
    logger.info("    %s: score 5 reentry blocked (4h cooldown)", key); return
```
Risk: low. Impact: would have blocked 5 of 6 GOLD losers (all within 2h of each other).

### Option B — Drop the unconditional ATR +1 (commodities_bot.py:472-473)
```python
# DELETE these 2 lines — ATR is a gate, not a confluence factor
- long_score += 1
- short_score += 1
```
Risk: low (rescaling). Most current "score 5" become 4. Forces MIN_CONFLUENCE recalibration to 3. **Expected: removes inflation; score now means something.**

### Option C — Require HTF alignment to allow score=5 (already half-built)
The 1D-BEAR filter at commodities_bot.py:524-528 already blocks GOLD/SLV LONG on bear daily. Extend: require **score≥5 only with bull HTF**.
```python
if score >= 5 and side == "LONG" and key in ("GOLD","SLV"):
    if _daily_trend_bias(yf_ticker) != "BULL":
        logger.info("    %s: score=5 requires 1D BULL", key); return
```
Risk: low. Impact: identical to the existing patch but tightens future regressions.

**Bonus fix (cross-cutting):** Add a `score_system` column to trades (`'crypto_v12' | 'commodity' | 'swing' | 'manual'`) so WR audits stop comparing apples to oranges.

## Confidence: **High**

Root cause is documented in the code itself (`commodities_bot.py:523` comment). 6 of 7 score=5 losses are the same incident, same symbol, same 5-day window, already partially mitigated. The "0% WR at score=5" headline is essentially **one historical incident**, not an ongoing inverted signal.
