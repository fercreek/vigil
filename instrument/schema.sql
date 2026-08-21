-- Zenith instrument — canonical schema (PostgreSQL dialect).
-- store.py translates this to SQLite for local/replay runs. ONE source of truth:
-- never hand-maintain a second dialect of this file.
--
-- Design rule: the database refuses to store a row it cannot later analyse.
-- Every CHECK here maps to a specific defect measured in the legacy bot
-- (see docs/DIAGNOSIS.md): 22/92 rows had the stop on the wrong side of entry,
-- and 0/92 rows recorded why the signal fired.

-- ── signals: every EVALUATION, not only the ones that fired. This is the denominator.
CREATE TABLE IF NOT EXISTS signals (
  id               BIGSERIAL PRIMARY KEY,
  ruleset_version  TEXT        NOT NULL,   -- sha of rules.py + geometry.py
  emitted_at       TIMESTAMPTZ NOT NULL,   -- when the bot decided
  bar_ts           TIMESTAMPTZ NOT NULL,   -- the CLOSED candle that triggered it
  symbol           TEXT        NOT NULL,
  timeframe        TEXT        NOT NULL,
  side             TEXT        NOT NULL CHECK (side IN ('LONG','SHORT')),

  decision         TEXT        NOT NULL CHECK (decision IN ('SENT','SUPPRESSED','BLOCKED','ERROR')),
  decision_reason  TEXT        NOT NULL,

  -- geometry — required when decision='SENT'
  entry_price   NUMERIC(20,8),
  sl_price      NUMERIC(20,8),
  tp1_price     NUMERIC(20,8),
  tp2_price     NUMERIC(20,8),
  r_unit        NUMERIC(20,8),   -- |entry - sl| in price. One R.
  rr_tp1        NUMERIC(8,3),    -- DERIVED from the real prices, never from a multiplier
  rr_tp2        NUMERIC(8,3),
  breakeven_wr  NUMERIC(6,4),    -- the hit rate this geometry demands: 1/(1+rr_tp1)

  -- why it fired — machine readable, never empty
  trigger       TEXT NOT NULL,   -- JSON: {"rsi":18.4,"bb_pctb":-0.02,"ema200":211.4}
  gates_passed  TEXT NOT NULL,   -- JSON array
  gates_failed  TEXT NOT NULL,   -- JSON array

  -- the LLM annotates, it does NOT gate (decision 2, 2026-08-21)
  llm_verdict   TEXT,            -- JSON or NULL

  regime        TEXT,
  atr_pct       NUMERIC(8,4),
  expires_at    TIMESTAMPTZ,     -- after this the signal is dead, not late
  notified_at   TIMESTAMPTZ,
  telegram_msg_id TEXT,

  CONSTRAINT sent_needs_geometry CHECK (
    decision <> 'SENT' OR (
      entry_price IS NOT NULL AND sl_price IS NOT NULL
      AND tp1_price IS NOT NULL AND r_unit IS NOT NULL AND r_unit > 0)),

  -- the 22/92 defect: a stop on the wrong side of entry is not a trade, it is a typo
  CONSTRAINT stop_on_right_side CHECK (
    decision <> 'SENT' OR
    (side = 'LONG'  AND sl_price < entry_price AND tp1_price > entry_price) OR
    (side = 'SHORT' AND sl_price > entry_price AND tp1_price < entry_price)),

  -- the 0/92 defect: a signal that cannot say why it fired cannot be audited
  CONSTRAINT trigger_not_empty CHECK (
    decision <> 'SENT' OR (trigger <> '' AND trigger <> '{}'))
);

-- dedupe survives restarts, unlike the in-memory dict the legacy bot used
CREATE UNIQUE INDEX IF NOT EXISTS ux_signal_dedup
  ON signals (symbol, ruleset_version, bar_ts);

-- ── resolutions: the outcome. One row per SENT signal, written by resolver.py.
CREATE TABLE IF NOT EXISTS resolutions (
  signal_id        BIGINT      PRIMARY KEY REFERENCES signals(id),
  resolver_version TEXT        NOT NULL,
  resolved_at      TIMESTAMPTZ NOT NULL,

  outcome     TEXT NOT NULL CHECK (outcome IN
                ('TP2','TP1_THEN_TP2','TP1_THEN_BE','SL','TIMEOUT','VOID')),
  exit_price  NUMERIC(20,8) NOT NULL,
  exit_bar_ts TIMESTAMPTZ   NOT NULL,   -- a real candle, NOT the script's clock
  bars_held   INTEGER       NOT NULL,

  tp1_hit     BOOLEAN     NOT NULL,
  tp1_bar_ts  TIMESTAMPTZ,

  mae_r NUMERIC(8,3) NOT NULL,   -- worst excursion in R: was the stop close?
  mfe_r NUMERIC(8,3) NOT NULL,   -- best excursion in R: was the target reachable?

  r_realized      NUMERIC(8,3) NOT NULL,
  r_if_tp1_only   NUMERIC(8,3) NOT NULL,  -- counterfactual: all out at TP1
  r_if_no_partial NUMERIC(8,3) NOT NULL,  -- counterfactual: let it all run

  same_bar_ambiguous BOOLEAN NOT NULL,    -- TP and SL in one candle: flagged, not guessed
  resolution_source  TEXT    NOT NULL CHECK (resolution_source IN ('BARS','MANUAL','FORCED'))
);

-- ── manual_fills: he trades by hand. Without this, a bad signal and a bad fill look alike.
CREATE TABLE IF NOT EXISTS manual_fills (
  id          BIGSERIAL PRIMARY KEY,
  signal_id   BIGINT REFERENCES signals(id),
  taken       BOOLEAN NOT NULL,
  skip_reason TEXT,
  filled_at   TIMESTAMPTZ,
  fill_price  NUMERIC(20,8),
  size_r      NUMERIC(8,3),
  closed_at   TIMESTAMPTZ,
  close_price NUMERIC(20,8),
  r_realized_human NUMERIC(8,3),
  note        TEXT
);

-- ── heartbeats: the 54 days of undetected downtime.
CREATE TABLE IF NOT EXISTS heartbeats (
  component TEXT PRIMARY KEY,
  last_beat TIMESTAMPTZ NOT NULL,
  detail    TEXT
);

-- ── legacy_trades: the old 92 rows, raw, quarantined. No constraints on purpose —
-- this is evidence, not data we stand behind. Never joined into the live denominator.
CREATE TABLE IF NOT EXISTS legacy_trades (
  id            BIGINT PRIMARY KEY,
  symbol        TEXT,
  side          TEXT,
  entry_price   NUMERIC(20,8),
  sl_price      NUMERIC(20,8),
  tp1_price     NUMERIC(20,8),
  tp2_price     NUMERIC(20,8),
  status        TEXT,
  open_time     TEXT,
  close_time    TEXT,
  strategy      TEXT,
  conf_score    NUMERIC(8,3),
  is_sim        INTEGER,
  sl_side_valid INTEGER,   -- 0 = would be rejected by stop_on_right_side
  import_note   TEXT
);
