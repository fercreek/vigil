# A3 — Symbol Health Report

**Scope:** real trades only (`is_sim=0`), n=91, window 2026-03-30 → 2026-04-22.
**Win = status IN ('WON','FULL_WON','PARTIAL_CLOSED').**

---

## TL;DR

- **TAO:** 1/32 (3.1%). The single "win" is the seed trade (`id=1`, MANUAL, no strategy). Bot-generated TAO = **0/31 (0.0%)**. Kill switch recommended.
- **ZEC:** 13/44 (29.5%). WR by quartile = **36% / 82% / 0% / 0%** — collapse after Apr-9 when entry prices jumped +31% (chasing the top). Already in `V4_BLOCKLIST`; remaining SWING channel still active and lost 0/22. Block from SWING too.
- **SHORT:** 2/24 (8.3%). 18/24 = TAO shorts (0 wins). Remaining 6 = commodities (2/6 wins, 33%). The problem is TAO-SHORT specifically.
- **conf_score=5:** 0/7. 6/7 are GOLD-LONG, 1/7 is TAO-LONG. Both are symbols already flagged as dead.

---

## 1. TAO autopsy

### By strategy_version

| version  | n  | wins |
|----------|----|------|
| SWING    | 29 | 0    |
| MANUAL   | 3  | 1    |

### By alert_type

| alert_type           | n  | wins |
|----------------------|----|------|
| swing_institutional  | 29 | 0    |
| unknown (manual)     | 2  | 1    |
| manual_long          | 1  | 0    |

### By direction

| type  | n  | wins |
|-------|----|------|
| LONG  | 14 | 1    |
| SHORT | 18 | 0    |

### The 1 "win"

```
id=1  TAO LONG entry=313.9  status=WON  open_time=2026-03-30 20:45
strategy=MANUAL  rsi_entry=50 (placeholder)  conf_score=0
```

It is the **manual seed trade** Fernando opened himself. Has no `close_time`, no `ai_analysis`, no `macro_bias`. **It is not a bot win.**

→ **Bot-generated TAO record: 0/31 (0.0%) since Mar-30.**

All 29 SWING trades fired with `rsi_entry=50.0` placeholder — i.e. the bot is **not actually reading RSI for TAO entries**. `macro_bias` is empty across all 32. Filter pipeline degenerate.

---

## 2. ZEC degradation timeline

Quartiles of 11 trades each, sorted by `open_time`:

| quartile | n  | wins | WR    | date range                  |
|----------|----|------|-------|------------------------------|
| Q1       | 11 | 4    | 36.4% | Apr 01 → Apr 07              |
| Q2       | 11 | 9    | **81.8%** | Apr 07 → Apr 09         |
| Q3       | 11 | 0    | **0.0%**  | Apr 09 → Apr 11         |
| Q4       | 11 | 0    | **0.0%**  | Apr 11 → Apr 14         |

**Root cause: bot chased the top.** Average entry price:

| period      | min   | max   | avg   |
|-------------|-------|-------|-------|
| pre-Apr-9   | 244.8 | 333.0 | **278.2** |
| post-Apr-9  | 313.7 | 379.0 | **364.1** |

Bot fired 22 LONG signals in a row at +31% higher prices. All lost. ZEC's RSI/BB confluence filter cannot detect overextension at higher TF — it just keeps firing the same alert.

ZEC is in `V4_BLOCKLIST` but **44/44 trades come from SWING channel, not V4** → blocklist doesn't apply. SWING channel ignored the kill.

---

## 3. SHORT breakdown

24 shorts total. **75% = TAO-SHORT, all losers.**

| symbol | strategy   | n  | wins | alert_type             |
|--------|------------|----|------|------------------------|
| TAO    | SWING      | 18 | 0    | swing_institutional    |
| OIL    | COMMODITY  | 4  | 1    | commodity_conservative |
| GOLD   | COMMODITY  | 1  | 1    | commodity_conservative |
| SOL    | SWING      | 1  | 0    | swing_institutional    |

Non-TAO shorts: **2/6 = 33%**, marginal small sample.
TAO shorts: **0/18 = 0.0%**.

Entry prices on TAO shorts cluster $253–272 between Apr-10 → Apr-14 — same window as ZEC's collapse. Bot was shorting TAO into the same rally it was longing ZEC into. **Both directions losing simultaneously** = filter not reading macro/HTF at all.

`rsi_entry=50.0` on every TAO-SHORT row confirms the indicator pipeline is broken for TAO.

---

## 4. MAE/MFE

`events_json` is **NULL on all 91 trades**. `be_moved=0` and `partial_pct=0` across all rows. **There is no trade-management telemetry captured.** Cannot answer "did losers reach TP1 first?". This is a separate gap (S2/A2 territory).

---

## 5. Cross-cut: conf_score=5 by symbol

| symbol | type | n | wins |
|--------|------|---|------|
| GOLD   | LONG | 6 | 0    |
| TAO    | LONG | 1 | 0    |

All 7 conf_score=5 losers are in symbols already known to be dead. **conf_score=5 has no GOLD-/TAO-independent signal** — kill those symbols and the 0%-WR-at-max-confidence problem (S2) goes away.

Full distribution:

| conf_score | n  | WR    |
|------------|----|-------|
| 0 (manual) | 2  | 50.0% |
| 3          | 1  | 0.0%  |
| 4          | 81 | 19.8% |
| 5          | 7  | 0.0%  |

Note: conf_score=4 dominates (89% of trades) so the score is barely discriminating — separate issue for A2.

---

## 6. Recommended config changes

```python
# config.py

# --- Kill switches ---

# A3-1: TAO dead since inception. 0/31 bot trades. Indicator pipeline broken
# (rsi_entry=50.0 placeholder on every row). Reactivation requires diagnosing
# why RSI/macro_bias aren't being populated for TAO before re-enable.
TAO_TRADING_ENABLED = False   # was True

# A3-2: ZEC SWING channel must respect V4_BLOCKLIST. Either expand blocklist
# semantics or add explicit SWING block. Simplest: add SWING_BLOCKLIST.
SWING_BLOCKLIST = ["TAO", "ZEC"]   # new — wire into strategies.py SWING path

# A3-3: Block SHORTS in VERDE_BULL regime (SP500 > SP500_VERDE_THRESHOLD).
# TAO-SHORT shorted into uptrend across all 18 attempts.
SHORT_BLOCKED_IN_VERDE_BULL = True   # new — wire into macro gate

# A3-4: Block all SHORTS for TAO regardless of regime (separate from above
# in case bull regime gate isn't ready). Belt + suspenders.
TAO_SHORT_ENABLED = False   # new
```

**Wire-up required (not config-only):**
- `strategies.py` SWING entry path must consult `SWING_BLOCKLIST` before firing.
- Macro gate must check `SHORT_BLOCKED_IN_VERDE_BULL` before any short alert.
- Add `rsi_entry` actual write path for TAO/cripto SWING — currently 50.0 placeholder. (Pipeline bug, not just config.)

---

## 7. Risk per recommendation

| change | what we lose | mitigation |
|--------|--------------|------------|
| `TAO_TRADING_ENABLED=False` | future TAO recovery if rally resumes | re-enable after fixing rsi_entry=50 bug + 10-trade paper validation |
| `SWING_BLOCKLIST=[TAO,ZEC]` | ZEC long mean-reversion if it returns | re-evaluate after 30 days of SWING activity on other symbols |
| `SHORT_BLOCKED_IN_VERDE_BULL` | shorts into legit rejection at ZR resistance | commodity SHORTS (OIL/GOLD) excluded — they're descorrelacionado, keep enabled |
| `TAO_SHORT_ENABLED=False` | none — 0/18 record | re-enable only with diagnostic backtest |

**Total trade-channel impact:** removes ~58 of past 91 trades from future generation (64%). Bot will be quieter — feature, not bug, given current WR.

---

## 8. Confidence per recommendation

| recommendation | confidence | reasoning |
|----------------|-----------|-----------|
| TAO kill switch | **HIGH** | 0/31 bot trades, broken indicator pipeline confirmed |
| SWING blocklist for ZEC | **HIGH** | 0/22 in Q3+Q4, root cause (chase top) understood |
| TAO_SHORT_ENABLED=False | **HIGH** | 0/18, redundant with TAO_TRADING_ENABLED but cheap |
| Shorts blocked in VERDE_BULL | **MEDIUM** | Sample n=18 SHORT losses are all TAO; non-TAO shorts only 6 trades — need more data. Safer as macro gate rule than full block |
| Keep COMMODITY shorts (OIL/GOLD) | **MEDIUM** | 2/5 = 40%, small sample but per CLAUDE.md sec 8c they are descorrelacionados |

---

## 9. Open questions for A2 / future work

1. **Why is `rsi_entry=50.0` on 91/91 rows?** Either column never populated, or default-placeholder bug in `tracker.py` insert path. Blocks A3 from validating any RSI filter claim.
2. **Why is `events_json=NULL` everywhere?** No MAE/MFE = can't tell entry-quality from management-quality. Block on trade postmortem until this is fixed.
3. **Why does ZEC SWING bypass `V4_BLOCKLIST`?** Blocklist appears version-scoped only. Needs naming clarification (`V4_BLOCKLIST` ≠ `SYMBOL_BLOCKLIST`).
