-- knowledge cache — canonical schema (PostgreSQL dialect).
-- cache.py translates this to SQLite using the same rules as store.py; there is
-- deliberately no second hand-maintained DDL for this table either.
--
-- Why this table exists: the legacy bot (scalp_bot) hardcoded facts with an
-- expiry date directly into config.py and never checked the date again.
--   config.py:340  FOMC_NEXT_MEETING       = "2026-07-28"  -- 24 days stale on 2026-08-21
--   config.py:348  EARNINGS_CALENDAR       TSLA/GOOGL "2026-07-22" -- 30 days stale
--   config.py:243  QUANTUM_SUPPRESSED_UNTIL = "2026-06-15" -- 67 days stale
--   commodities_bot.py:98  OPEC_MEETING_DATES = ["2026-05-05"] -- 108 days stale
-- All four gated signal suppression. None of them ever raised an alert when
-- they expired -- "the data exists" and "the data is still valid" were the
-- same question, answered once at write time and never asked again. This
-- table splits that into two columns (value vs valid_until) so the second
-- question has somewhere to live, plus manual_override so a hand-typed value
-- (exactly what the four constants above were) is visible as such forever,
-- not indistinguishable from a real feed once it's in the database.

CREATE TABLE IF NOT EXISTS knowledge (
  key              TEXT PRIMARY KEY,
  value            TEXT        NOT NULL,   -- JSON (put() serialises; get() parses back)
  source           TEXT        NOT NULL,   -- who/what populated this row
  fetched_at       TIMESTAMPTZ NOT NULL,
  valid_until      TIMESTAMPTZ NOT NULL,   -- after this, require() must not hand the value out
  manual_override  BOOLEAN     NOT NULL DEFAULT 0  -- set by hand -- degraded by definition,
                                                    -- see cache.py's stale_keys()
);
