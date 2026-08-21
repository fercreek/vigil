# Pre-registered signal hypotheses

> Written and frozen **before** `scripts/test_hypotheses.py` was run once. Do not edit
> this file after seeing numbers — a bad result gets reported here, not patched away.
> Context: two prior grid searches (120 configs, then 1,296 configs) both produced a
> config that looked great in-sample and inverted out-of-sample, or lost to a naive
> always-LONG baseline riding asset drift. This file exists to not do that a third time:
> 5 fixed configurations, tested once, each with an economic reason to exist.

## Shared method (applies to every hypothesis below)

- **Universe:** all 6 corpus symbols — ZEC, TAO, BTC, ETH, SOL, BNB — 1h candles,
  2024-08-01 → 2026-08-21.
- **Walk-forward segments** (fixed calendar splits, not chosen to flatter any config):
  `S1` 2024-08-01→2025-02-01, `S2` 2025-02-01→2025-08-01, `S3` 2025-08-01→2026-02-01,
  `S4` 2026-02-01→2026-08-21.
- **Geometry is identical across every hypothesis and the baseline**, imported from
  `rules.py` rather than re-invented: `SL = 1.5×ATR(14)`, `TP1 = entry ± 0.7R`,
  `TP2 = entry ± 1.3R`. Holding this constant means the only thing under test in this
  file is *when and which side to enter* — never the exit math.
- **Resolution** uses `resolver.resolve` unchanged, `max_bars=72` (the frozen max-hold).
- **Baseline** = unconditional LONG on every ATR-eligible bar, same geometry, no gate at
  all. It is computed once per symbol over the full corpus and bucketed into the same
  segments. Positions overlap (a new one opens every bar) — it is not a tradeable
  strategy, it is a drift detector: if a hypothesis cannot beat "just always be long
  here," its apparent edge is the asset's drift, not the rule.
- **Every ratio is reported with n next to it.** A cell with n<30 is printed, never
  hidden, but flagged `low-n` and does not count toward the qualifying vote below.

## Success criterion — fixed before any run

A hypothesis is declared to have **an edge** only if ALL five hold, pooled across all
6 symbols × 4 segments (24 cells):

1. **Evidence floor:** total resolved signals across the whole universe ≥ 30.
2. **Positive & significant:** pooled expectancy_r > 0 AND the lower bound of its 95%
   CI (normal approximation, `mean ± 1.96·s/√n`) > 0.
3. **Beats the baseline:** pooled expectancy_r > the pooled baseline expectancy_r over
   the identical 6-symbol/2-year universe.
4. **Not one-symbol luck:** expectancy_r > 0 in at least 4 of the symbols that reach
   n≥10 individually (and at least 5 of the 6 symbols must reach n≥10, or this
   criterion fails outright — too thin a base to call a symbol either way).
5. **Not one-regime luck:** pooled (across symbols) expectancy_r > 0 in at least 3 of
   the 4 walk-forward segments.

Any single failure → verdict is **NO EDGE**, reported with the criterion that broke it.
This is deliberately strict: the point of this file is to stop shipping the best of N,
not to find a reason to keep one.

---

## H1 — Liquidity-sweep reversal (stop-hunt fade)

**Statement:** when price wicks past the prior day's high/low and closes back inside
it, fade the wick.

**Mechanism:** obvious swing points (the prior 24h high/low) are exactly where
breakout-order stops and leveraged-position liquidation levels cluster. Pushing price
just past that level for one bar before reversing lets whoever is on the other side
fill against those orders; the breakout traders who bought/sold the poke are now
trapped and their unwind adds fuel to the reversal. This is a documented microstructure
pattern in thin/perp-driven crypto books, not a statistical artifact of one dataset.

**Parameters (fixed):**
- Lookback N = 24 closed bars (prior calendar day).
- SHORT trigger at bar i: `high[i] > max(high[i-24:i])` and `close[i] < max(high[i-24:i])`.
- LONG trigger at bar i: `low[i] < min(low[i-24:i])` and `close[i] > min(low[i-24:i])`.
- If both fire on the same bar (both extremes swept), skip — ambiguous, no bias applied.

**Success criterion:** the 5 shared criteria above, applied to H1's signals only.

---

## H2 — Asian-session compression → session-open continuation

**Statement:** if the low-liquidity Asian session (00:00–07:59 UTC) coils into an
unusually tight range, the move that follows once EU/US desks return continues in the
direction the coil already leaned.

**Mechanism:** Asian hours carry a real liquidity gap — most institutional desks and
market makers active in BTC/ETH/majors are EU/US-hours operations. Thin books produce
directionless chop; when volume returns, the resolving move is amplified by returning
trend-following flow (a large share of crypto volume is systematic/momentum) rather
than starting from a random walk.

**Parameters (fixed):**
- Asian session = bars with UTC hour in [0,7] (8 bars/day, i.e. `candles[d*24 : d*24+8]`
  for calendar day d).
- `session_range = max(high) - min(low)` over those 8 bars.
- `reference = median(session_range)` over the trailing 20 sessions (20 prior days).
- Compressed if `session_range <= 0.6 × reference` (needs ≥20 prior sessions to exist).
- Trigger bar = the hour-08 bar (first bar of the new session, already closed).
- Direction = sign of `close[hour07] - open[hour00]` (the session's own net move):
  LONG if positive, SHORT if negative, skip if exactly zero.

**Success criterion:** the 5 shared criteria above, applied to H2's signals only.

---

## H3 — Consecutive-close momentum continuation (herding)

**Statement:** four consecutive same-direction hourly closes predict a fifth.

**Mechanism:** short-horizon momentum-chasing is a well-documented retail behavior in
crypto (buying green candles, FOMO), and a large fraction of crypto volume is
systematic momentum/trend-following that mechanically adds exposure once a run
confirms. Counter-positioned short-term traders caught the wrong way also have to
cover into the move, adding fuel independent of any new information arriving.

**Parameters (fixed):**
- Streak length = 4: `close[i] > close[i-1] > close[i-2] > close[i-3] > close[i-4]` →
  LONG at close[i]. Strict mirror (4 consecutive down-closes) → SHORT.

**Success criterion:** the 5 shared criteria above, applied to H3's signals only.

---

## H4 — Single-bar capitulation fade (forced-flow overreaction)

**Statement:** an hourly bar with a true range ≥3× the trailing ATR is a forced-flow
event, not new information, and partially reverts.

**Mechanism:** a bar that large in a liquid major is characteristic of a liquidation
cascade or a single large market order sweeping the book, not of organic price
discovery. Once the forced selling/buying is exhausted (margin calls satisfied, the
order filled), mean-reversion desks and resting liquidity providers arb the overshoot
back toward the pre-event level.

**Parameters (fixed):**
- `tr[i] = max(high[i]-low[i], |high[i]-close[i-1]|, |low[i]-close[i-1]|)`.
- Trigger: `tr[i] >= 3.0 × ATR(14)[i-1]` (trailing ATR, excludes the shock bar itself).
- If `close[i] < open[i]` (down bar): LONG fade. If `close[i] > open[i]`: SHORT fade.
  If `close[i] == open[i]`: skip (no directional read on the shock).

**Success criterion:** the 5 shared criteria above, applied to H4's signals only.

---

## H5 — Weekend-drift reversion (Monday-open fade toward Friday's level)

**Statement:** if price drifts more than 1 ATR away from Friday's close over the
weekend, it fades back toward that level once Monday trading resumes.

**Mechanism:** crypto trades 24/7, but the institutional participants who anchor price
to fair value (desks, market makers, arbitrageurs) are largely weekday operations.
Weekend order flow is thinner and more retail-dominated, so the same-size order moves
price further; when weekday liquidity and price-discovery return Monday, part of the
weekend's move gets arbed back.

**Parameters (fixed):**
- Reference bar = the one 48h before the Monday-00:00 bar (i.e. Saturday 00:00 UTC,
  which is Friday's last close carried forward).
- Trigger bar = the Monday 00:00 UTC bar (`weekday()==0`, `hour==0`).
- `drift_r = (close[monday00] - close[monday00 - 48h]) / ATR(14)[monday00 - 1]`.
- If `drift_r >= 1.0` (rose ≥1 ATR over the weekend): SHORT (fade down toward Friday's
  level). If `drift_r <= -1.0`: LONG (fade up). Otherwise skip.

**Success criterion:** the 5 shared criteria above, applied to H5's signals only.

---

## Breakout — Donchian range breakout + volatility expansion (built 2026-08-21)

> Pre-registered here, in `instrument/breakout.py`'s own module docstring, and in
> `instrument/scripts/GATES.md`'s G3 accounting -- all written **before** running the
> 30-day alert-rate measurement or looking at what the module would have said about
> ETH's 2026-08-19 move. Same rule as the rest of this file: a bad result gets reported,
> not patched into a better-looking one.

**Statement:** a close beyond a 20-bar Donchian channel, on a bar whose true range has
clearly expanded versus its own trailing volatility, continues in the breakout's direction.

**Trigger for this build:** `rules.py` is a pullback-in-trend ruleset (RSI extreme +
Bollinger extreme + ADX) and is blind by design to a clean directional break of a range.
Measured cost of that blindness: 30 days in production, 8 alerts, all 8 on ZEC, 0 on the
other 5 symbols; on 2026-08-19 ETH moved +19.6% in 24h with RSI at 96.6 and price ABOVE
the upper Bollinger band -- the opposite of what `rules.py` requires (RSI<=30, price in
the LOWER band) -- so `rules.py` could not have alerted on it by construction, not by an
untuned threshold.

**Mechanism:** the closest thing to a measured edge in this file is H3 above (+0.015R,
beat the baseline in 4 of 6 symbols, missed the n>=30-per-symbol / significance bar) --
momentum continuation. This instrument operationalises that same mechanism with a
textbook range-breakout construct instead of H3's raw 4-close streak, because a streak
says nothing about whether the move clears enough ground to trade; a channel breakout
does.

**Parameters (fixed, not fit -- full reasoning in `breakout.py`'s module docstring):**
- Donchian channel, N=20 closed bars, excluding the current bar (the Entry-1 lookback
  from the original Turtle Trading rules; also `rules.py`'s existing `BB_PERIOD`).
- LONG trigger: `close[i] > max(high[i-20:i])`. SHORT trigger: `close[i] < min(low[i-20:i])`.
- Volatility-expansion filter: the breakout bar's true range >= 1.5 × ATR(14) measured on
  the PRIOR bar (trailing, excludes the breakout bar itself -- same convention as H4's
  `tr[i] >= 3.0 × ATR(14)[i-1]` above, at a milder multiple since a breakout needs an
  above-normal range, not H4's single-bar-shock extremity).
- Geometry differs from every hypothesis above by design, not by oversight: the stop is
  the OTHER side of the SAME Donchian channel that broke (risking the width of the base),
  and the targets are outright ATR multiples added to entry (2.0×ATR / 4.0×ATR) rather
  than an R-multiple of that stop -- the two legs are sized by different rulers on
  purpose (see `breakout.py`).

**Success criterion:** the 5 shared criteria above, applied to this instrument's signals
only. It has NOT been run against them yet -- `scripts/test_hypotheses.py` covers H1-H5;
extending it to this instrument is future work, not done as part of this build.
