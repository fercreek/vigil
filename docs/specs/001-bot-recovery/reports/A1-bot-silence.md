# A1 — Bot Silence Investigation

> Today: 2026-05-22 · Last trade in DB: 2026-04-22 13:24 (OIL LONG) · Last `bot.log` line: 2026-04-22 12:53.

## Root cause hypothesis (ranked)

### 1. **Bot process is DEAD (Railway / local)** — primary cause of S1

Evidence:
- `logs/bot.log` last entry `2026-04-22 12:53:33` — no heartbeat for 30 days.
- `logs/bot.pid` = `99086`, but `ps aux | grep` returns **no matching process** locally.
- `trades.db` last `open_time` = `2026-04-22 13:24:55` (id 91, OIL commodity). No CRYPTO trade rows after Apr 22.
- `logs/app.log` size = **0 bytes** since Apr 26.
- All other suspects below are *latent* — they would suppress signals once the bot is restarted, but they are not what stopped it.

The bot is not "silent because filters block it." It is silent because **it stopped running**. Railway watchdog (`railway.toml:6` `restartPolicyType="ALWAYS"`, max 10 retries) likely exhausted retries on a crash loop ~Apr 22. Local copy was never restarted.

### 2. **Once restarted, only V3-REVERSAL + V4-EMA + V2-AI fragments are reachable** — sustained silence risk (S1 chronic)

The kill switches in `config.py:227-230` (commit `f99ea27`, 2026-05-09) leave the strategy matrix extremely thin:

- `V1_SHORT_ENABLED=False`, `V1_LONG_ENABLED=False`, `V5_ENABLED=False`, `V4_BLOCKLIST=["ETH","ZEC"]`.
- `strategies.py:528` — V1-LONG block is `elif V1_LONG_ENABLED and ...` → always False → skipped.
- `strategies.py:603-661` — **V2-AI EXEC path is nested INSIDE the dead V1-LONG branch** (`if decision == "CONFIRM"` inside the `elif V1_LONG_ENABLED:` block). It is unreachable.
- The independent V2-AI block at `strategies.py:723-780` (`if rsi <= 40`) requires `p > ema_200` (line 732). Crypto is largely below EMA200 → rarely fires.
- V3-REVERSAL is the only realistic source of crypto longs (`strategies.py:465`), gated by `regime in ("VOLATILE","TRENDING_DOWN")` + per-symbol RSI ≤ 28-32. Tight.
- V4-EMA chain (`strategies.py:666`) is `elif` of V1-LONG → only reachable when V3 condition is false AND V1-LONG `elif` falls through (V1 disabled, so it does). Requires `TRENDING_UP` + not in `["ETH","ZEC"]`.

### 3. **Hour filter `_BLOCKED_HOURS` permanent dead-window** — minor amplifier

`strategies.py:217` blocks UTC hours `{4, 6, 10, 11, 15, 16, 17, 20}` → 8/24 hours = 33% of clock dead. Combined with FOMC and regime filters, real signal window is small. Current UTC hour at investigation time = **20** (BLOCKED).

### 4. **FOMC suppressor is NOT active** — ruled out

`FOMC_NEXT_MEETING = "2026-06-17"`, today 2026-05-22 → 26 days out, well outside the 24h window in `strategies.py:31`. Not a factor.

### 5. **Paused flag** — ruled out

`runtime_state.is_paused()` is loaded into `GLOBAL_CACHE["paused"]` (`scalp_alert_bot.py:52,59`) but **no code path actually gates `check_strategies()` on it**. Grep confirms zero usage in the main loop or strategies. So a /pause command cannot explain silence.

### 6. **TradingView webhook auth** — ruled out as silence cause

`webhook_security.py:30` defaults `ENFORCE_HMAC=false`. Only rate limit + idempotency active. Even if misconfigured, webhook is an *additional* signal channel, not the source of internal V2/V3 strategy fires.

## Active strategy matrix (post kill-switches)

After Apr 22 kill switches, with default `phase=LONG` (from `phase.txt`), `regime` per symbol:

| Symbol | V1-LONG | V1-SHORT | V2-AI (728 block) | V3-REVERSAL | V4-EMA | V5 |
|--------|---------|----------|-------------------|-------------|--------|----|
| ZEC    | OFF     | OFF      | conditional¹      | ON (RSI≤30)  | **OFF (blocklist)** | OFF |
| TAO    | OFF     | OFF      | conditional¹      | ON (RSI≤28)  | ON³    | OFF |
| BTC    | OFF     | OFF      | conditional¹      | ON (RSI≤32)  | ON³    | OFF |
| ETH    | OFF     | OFF      | conditional¹      | ON (RSI≤32)  | **OFF (blocklist)** | OFF |
| SOL    | OFF     | OFF      | conditional¹      | ON (RSI≤30)  | ON³    | OFF |
| HBAR   | OFF     | OFF      | conditional¹      | ON (RSI≤30)  | ON³    | OFF |
| DOGE   | OFF     | OFF      | conditional¹      | ON (RSI≤30)  | ON³    | OFF |
| TON    | OFF     | OFF      | conditional¹      | ON (RSI≤30)  | ON³    | OFF |

¹ V2-AI inner exec block (`strategies.py:603-661`) is dead (nested inside dead V1-LONG `elif`). Standalone V2 block (`strategies.py:723`) requires `rsi ≤ 40` **AND** `p > ema_200` (line 732 `is_valid_trend`) — rarely both true in current bear regime.
² All long branches additionally require `phase=LONG` (true), `regime != RANGING`, hour NOT in `{4,6,10,11,15,16,17,20}`, no 3-loss-streak cooldown, not in `_BLOCKED_HOURS`, FOMC OK (it is), and `is_position_open(sym, side)` False.
³ V4-EMA fires only on `regime == TRENDING_UP` + price within `[1.005, 1.02-1.03]` of EMA200 (proximity gate). In a bear/ranging market this rarely fires.

Net: realistic source of new alerts = **V3-REVERSAL only**, gated by RSI ≤ 28-32 + `regime in ("VOLATILE","TRENDING_DOWN")` + 1D bias filter + loss-streak guard.

## Suspicious config / commits since Apr 20

| Commit | Date | What it touched | Risk to S1 |
|--------|------|-----------------|------------|
| `f99ea27` | 2026-05-09 | `feat(strategies): kill switches` → set `V1_LONG_ENABLED=False`, `V5_ENABLED=False`, expand `V4_BLOCKLIST` (`config.py:227-230`) | **HIGH** — removes 3 of 5 strategies system-wide |
| `9d1c485` | 2026-05-09 | ronda 4 per-symbol RSI thresholds (`config.py:204-209`) — TAO 32→28, ZEC kept 30 | MED — tighter thresholds, fewer fires |
| `d915e5b` / `22d1565` | 2026-05-09 | strategy tuning via backtest | MED — confluence + RSI tightening |
| `597fead` | 2026-05-09 | multi-TF filter `MTF_RSI_4H_MAX=50` (`config.py:213`) — extra V3 LONG gate | MED — blocks V3 when 4H RSI > 50 |
| `688deb4` | 2026-05-12 | hour filter (`strategies.py:217`) — `_BLOCKED_HOURS` set of 8 UTC hours | MED — 33% of day dead |
| `8f485b5` | 2026-05-13 | desactivar 3 threads (`main.py:36-39` commented out: commodities_bot, manual_positions_monitor, scalper_shorts_bot) | HIGH for *commodity* alerts — explains why no GOLD/OIL post Apr 22. Crypto loop unaffected. |
| `eb6b2a1` | 2026-05-13 | TTL hikes (`config.py:259-262`) — `TTL_INDICATORS=120`, `TTL_MACRO=900` | LOW — may slow refresh but does not block |

None of these commits **alone** kill ALL signals, but stacked they reduce the live surface to a thin V3 + standalone V2-AI path. The original *crash* on Apr 22 happened BEFORE most of these landed → suspect a pre-`f99ea27` runtime error (the truncated traceback in `bot.log` ends with `commodities_bot.py:180` `logger.info("... LOST (SL hit) @ %.{dec}f", ...)` — bad format string `%.{dec}f`, repeated logs/exceptions could have cascaded into watchdog death).

Format-string bug in `commodities_bot.py:180`:

```
logger.info("    %s LOST (SL hit) @ %.{dec}f", key, price)
```

`%.{dec}f` is not valid `%`-style formatting; it raises every time a commodity SL hits. Visible in `bot.log` just before silence.

## Recommended fix (proposed only — do NOT apply)

**Step 1 — restart and observe (5 min):** confirm the process is actually dead in Railway:
- `railway logs` (or dashboard) — check for crashloop on Apr 22.
- Redeploy. Verify heartbeat in `bot.log`.

**Step 2 — make V2-AI exec block independent of V1-LONG kill switch.** Top hypothesis #2.

```diff
--- a/strategies.py
+++ b/strategies.py
@@
-        elif V1_LONG_ENABLED and phase == "LONG" and p > ema_200 and regime in ("TRENDING_UP", "VOLATILE"):
+        # V1-LONG body (legacy); V2-AI exec lives below and must run independent of V1_LONG_ENABLED.
+        v1_long_gate = (phase == "LONG" and p > ema_200 and regime in ("TRENDING_UP", "VOLATILE"))
+        if V1_LONG_ENABLED and v1_long_gate:
             entry_rsi = 49.0 if sym == "ZEC" else 47.0
             if rsi <= entry_rsi:
                 ...  # (V1 fire path)
+
+        # V2-AI exec path — un-nested from V1_LONG kill switch
+        if v1_long_gate and rsi <= 47.0:
+            # ... existing V2-AI CONFIRM block ...
```

Also flip the `elif` chain (`strategies.py:465, 528, 666`) into independent `if` blocks so V4-EMA and V3-REVERSAL no longer hinge on V1-LONG ever being true.

**Step 3 — fix `commodities_bot.py:180` format string** even if thread is currently off (when re-enabled it will crash again):

```diff
- logger.info("    %s LOST (SL hit) @ %.{dec}f", key, price)
+ logger.info("    %s LOST (SL hit) @ %.4f", key, price)
```

**Step 4 — add a startup self-test** that logs the active strategy matrix per symbol (mirrors the table above) on every boot, so future silence is visible in line 1 of the log.

## Confidence level

**High** for hypothesis #1 (process dead) — direct evidence in `bot.log`, `bot.pid`, `trades.db`.
**High** for hypothesis #2 (V2-AI exec orphaned by kill switch) — code structure verified `strategies.py:528 → 604 → 661` all sit inside `elif V1_LONG_ENABLED`.
**Medium** for hypothesis #3 — hour filter is *additive*, not the root cause but worsens the recovery surface.

Other A-track agents should validate by (a) checking Railway deploy history around Apr 22 and (b) running `python -c "import strategies; strategies.check_strategies(get_prices())"` with a debug breakpoint to confirm V2-AI dead-branch behavior end-to-end.
