# Pre-registered exit hypotheses

> Written and frozen **before** `scripts/test_exits.py` was run once. Do not edit this
> file after seeing numbers.

## Why this file exists

`HYPOTHESES.md` pre-registered and tested 5 **entry** ideas over 6 symbols / 2 years.
All 5 came back NO EDGE, and so did the unconditional-LONG baseline. All 5 shared one
exit geometry, imported unchanged from `rules.py`: `SL = 1.5×ATR(14)`, `TP1 = entry ±
0.7R`, `TP2 = entry ± 1.3R`, half off at TP1. That geometry is not neutral — `TP1_R_MULT
= 0.7` was fit to the MFE **median** of a 59-trade legacy sample, and the entry
hypotheses were then scored against data that includes the trades that produced that
median. It is circular, and a quick, non-pre-registered probe on ZEC (n=716,
unconditional entry, fixed 3% stop) showed why it matters: expectancy climbed
monotonically as the target widened — **+0.032R at 0.7R/1.3R, +0.083R at 1.5R/3.0R,
+0.140R at 3.0R/6.0R** — with no sign of bending over. The exit geometry moves the
number more than any entry rule tested so far.

**The trap this file is built to catch:** in a 2-year window where crypto trended up
hard, "wider target wins" is close to a tautology — the limit of an infinite target is
*never sell*. A result that says "wider is always better, without limit" is not a
discovered exit edge, it is a rediscovery that the sample should not have been traded
at all, just held. So the deciding test below is **not** the pooled R number. It is
(a) whether a design still works in segments the asset's own price fell or went
nowhere, and (b) whether, in the segments it wins, it wins by *less* than just holding
the asset would have — proof it did something besides ride drift.

## Shared method

- **Universe, corpus, segments, ATR:** identical to `HYPOTHESES.md` — 6 symbols (ZEC,
  TAO, BTC, ETH, SOL, BNB), 1h candles, 2024-08-01 → 2026-08-21, ATR(14) computed once
  per bar from `ta.atr` (frozen at signal time, no repaint), the same 4 fixed calendar
  segments S1–S4.
- **Entry is fixed across every design below, and is the same one `HYPOTHESES.md`
  already uses as its neutral reference: unconditional LONG at the close of every
  ATR-eligible bar.** It is "neutral" in the same sense it already carries in that
  file — no side-selection thesis, no gate, just "is a position open here" — so any
  difference between designs below is attributable to the exit, not to when or which
  side entered. It is long-only by construction; that is intentional, because the
  buy-and-hold ceiling this file compares against is long-only too, and comparing a
  long-only entry's exits against a long-only hold isolates the exit as the only
  variable in both arms.
- **Initial risk stays `SL = 1.5×ATR(14)` (frozen at entry) in every design.** No
  design below changes how much is risked to get in; they only change how the
  position comes out. Where a design has no fixed take-profit, "no TP" is implemented
  as a TP placed far enough away (1000R) that it is never realistically reachable —
  so the position can only end by stop, by the design's own exit condition, or by
  timing out at `max_bars` — without touching `resolver.py`'s validation, which still
  requires `sl < entry < tp1 <= tp2`.
- **`max_bars` is set per design** (declared with each one below) because a design
  that only trails or waits for a signal needs more room than a fixed 0.7R/1.3R
  target ever did; using 72 bars for all of them would just re-impose the old
  geometry's timing by the back door.

## Regime classification (fixed thresholds, not tuned to the result)

For every (symbol × segment) cell, `buy_hold_pct = (close_last − close_first) /
close_first` over that segment's own candles (a single, non-overlapping long position
held start-to-end of the segment — this is also the buy-and-hold ceiling itself, see
below). The cell is labeled:

- **BULL** if `buy_hold_pct >= +0.15`
- **BEAR** if `buy_hold_pct <= -0.15`
- **SIDEWAYS** otherwise

24 cells total (6 symbols × 4 segments). A design's pooled mean R is reported per
regime class by pooling every trade whose symbol×segment cell carries that label —
this is the "consistency between regimes" the verdict is actually decided on, not the
grand pooled mean.

## Buy-and-hold ceiling (not a 6th hypothesis — the yardstick)

Two numbers, both derived from the same segment window, computed once and reused by
every design:

1. **`buy_hold_pct`** (defined above) — the raw return of just holding the asset
   long over that segment.
2. **`buy_hold_R_equiv = buy_hold_pct / avg_r_unit_pct`**, where `avg_r_unit_pct` is
   the mean, over every entry that fired in that cell, of `(1.5×ATR at entry) /
   entry_price` — i.e. "how big is 1R, as a fraction of price, in this cell." Dividing
   the ceiling's raw return by that figure expresses buy-and-hold in the same R units
   every design's mean R is reported in, so the two are comparable on the same axis
   instead of comparing a percentage to a multiple.

`buy_hold_R_equiv` is reported next to every design's mean R in BULL cells
specifically, because that is where the tautology would surface: a design whose
BULL-cell mean R sits at or above `buy_hold_R_equiv` isn't beating the ceiling, it's
*at* the ceiling — the exit did no work a buy-and-hold position would not already have
captured (or it re-added leverage/re-entry effects that inflate past the raw return,
which is its own red flag).

## The 5 designs

### X1 — Fixed-R target, wider (structural target, not MFE-fit)

**Statement:** a conventional, non-fit R:R — first target at 1.5R, second at 3.0R —
captures more of a move than the legacy 0.7R/1.3R pair, which was never a target
choice, it was a median of a different sample being read back as one.

**Mechanism:** 0.7R/1.3R truncates winners near the point a *different, 59-trade*
population's average excursion happened to sit. There is no economic reason price
should stop extending there for *this* signal population; a wider, round-number R:R
removes that specific artifact while keeping the same risk-managed, capped-target
family (still a real take-profit, still resolved by `resolver.resolve` unchanged).

**Parameters (fixed):** `SL = 1.5×ATR` (shared), `TP1 = entry ± 1.5R`, `TP2 = entry ±
3.0R`, 50% off at TP1 (resolver default), `max_bars = 72` (same horizon as the
original geometry — only the R multiples change, not the clock).

**Exit:** `resolver.resolve` unchanged, called with this geometry.

### X2 — ATR chandelier trail (no fixed target)

**Statement:** letting the stop trail behind the best price seen since entry, by a
fixed multiple of the entry-time ATR, captures a trend for as long as it keeps
extending and gives back only a fixed, bounded amount of the peak — with no
arbitrary R cap at all.

**Mechanism:** a fixed R target assumes the size of the move is knowable in advance.
A volatility-anchored trailing stop instead assumes only that a real trend gives back
less than some number of average bars' worth of noise before it actually reverses;
it rides winners of any size and cuts losers at the same initial risk as every other
design here.

**Parameters (fixed):** `SL = 1.5×ATR` initial (shared). Once open, `stop = max(prior
stop, running_favourable_extreme − 3.0×ATR_entry)` for LONG (mirror for SHORT) —
the stop only ever ratchets in the trade's favour, never loosens. `ATR_entry` is
frozen at signal time (consistent with every other design; not recomputed bar-to-bar).
No fixed TP (see "Shared method" — set at 1000R, unreachable). `max_bars = 240` (10
days) — a trail needs room a 3-day fixed-target clock never had to give.

**Exit:** custom bar-walk in `test_exits.py` (resolver has no trailing-stop mechanic;
not added to it per the restriction — this is exactly the case the task flagged).

### X3 — Time-boxed exit (no target, no trail — the clock decides)

**Statement:** if the position hasn't been stopped out, exit at market after a fixed
1-day hold regardless of where price sits, on the theory that whatever edge this
entry has (if any) resolves within a session and anything held past that is noise.

**Mechanism:** isolates *time* as the only exit variable, with no price target and no
trailing logic at all — the cleanest possible test of "does simply not holding too
long" beat a target-based or trail-based exit.

**Parameters (fixed):** `SL = 1.5×ATR` (shared). No TP (1000R, unreachable).
`max_bars = 24` (1 calendar day of 1h bars) — forced exit at the close of bar 24 if
the stop hasn't already fired.

**Exit:** `resolver.resolve` unchanged (TIMEOUT branch does the work; no partial logic
engages because TP1 is never reachable, so this design exits as one unit, not two
halves).

### X4 — Partial at 0.7R + fully uncapped runner (no second target)

**Statement:** locking in half the position at a real, historically-observed level
(0.7R — the original TP1) removes variance early, while leaving the other half with
*no* cap lets it capture the fat right tail crypto return distributions are known to
have, instead of discarding that tail at a nearby 1.3R the way the original geometry
did.

**Mechanism:** the original TP2 = 1.3R caps the runner just 0.6R past where the
partial already sold — barely a stretch leg at all. If the informational edge (if any)
of this entry lives in occasional large moves rather than in a high hit-rate of small
ones, a target that close to TP1 discards exactly the trades that would pay for the
strategy.

**Parameters (fixed):** `SL = 1.5×ATR` (shared), `TP1 = entry ± 0.7R` (unchanged from
the original geometry — this is the one parameter kept, deliberately, to isolate "cap
the runner or don't" as the only variable against the original design), 50% off at
TP1, **no TP2** (1000R, unreachable) so the runner half only ends at the
already-existing breakeven stop (once TP1 fills, `resolver` moves the runner's stop to
breakeven — unchanged behaviour) or at `max_bars`. `max_bars = 240` (10 days) — same
room as the trail, since an uncapped runner needs the same headroom.

**Exit:** `resolver.resolve` unchanged, called with this geometry.

### X5 — Opposite-signal exit (trend flip via EMA20, not a price level)

**Statement:** exit not at a static price, but the moment the market's own near-term
trend structure flips against the position — a 20-bar EMA cross-under (for a LONG) —
on the theory that a real regime change invalidates the position better than any
fixed distance from entry can.

**Mechanism:** every other design here defines "wrong" as a price level fixed at
entry. This one defines "wrong" as a change in the market itself: once price closes
back below its own 20h trend average having been above it, whatever conditions
existed at entry have measurably changed, independent of how far price has moved in R
terms.

**Parameters (fixed):** `SL = 1.5×ATR` initial (shared, catastrophic-risk floor only
— a signal exit with literally no stop would conflate "the trend flipped" with "we
blew through unlimited risk waiting for it to"). No fixed TP (1000R, unreachable).
`EMA(20)` on closes, computed once per symbol. Exit at the close of the first bar
after entry where, for a LONG, `close[k-1] >= ema20[k-1]` and `close[k] < ema20[k]`
(strict cross-under); mirror condition for SHORT. `max_bars = 240` — a safety net for
the rare case the EMA never crosses back inside the window; not expected to bind
often.

**Exit:** custom bar-walk in `test_exits.py` (resolver has no signal-based exit
condition; same reasoning as X2 — implemented here, resolver untouched).

## Success criteria — fixed before any run

For each design, pooled across all 6 symbols × 4 segments:

1. **Evidence floor:** total resolved signals ≥ 30 (trivially true at this entry's
   volume, but stated because every prior file states it).
2. **Positive & significant:** pooled expectancy_r > 0 AND the 95% CI lower bound
   (`mean ± 1.96·s/√n`) > 0.
3. **Regime-consistent:** pooled expectancy_r > 0 in **every** regime class (BULL,
   BEAR, SIDEWAYS) that reaches pooled n ≥ 30. A regime class below n=30 is reported
   but excluded from this criterion (too thin to call either way) and flagged.
4. **Not disguised drift-capture:** in BULL cells, the design's pooled expectancy_r
   must be below `buy_hold_R_equiv` pooled over the same BULL cells. If it is at or
   above, and BEAR/SIDEWAYS pooled expectancy_r is ≤ 0, the verdict is **DRIFT-CAPTURE**
   regardless of criteria 1–3 — the design did not add anything to holding the asset.

**Verdict:** `EDGE` only if 1–4 all pass. `DRIFT-CAPTURE` per the explicit rule in
criterion 4. `NO EDGE` for any other failure, reported with the criterion that broke
it. Buy-and-hold itself is reported as the ceiling row and is never scored against
these four — it is not a candidate, it is what the candidates have to justify beating.

Any single failure → **NO EDGE** (or **DRIFT-CAPTURE** where criterion 4 explicitly
applies). This file is not edited after `test_exits.py` runs once — a bad result, or
"no exit beats holding," is reported exactly as it comes out.
