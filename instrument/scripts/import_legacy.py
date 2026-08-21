"""Phase 1 acceptance test: replay the 92 legacy trades against the new schema.

The legacy rows go into legacy_trades verbatim (quarantine). Separately, each one
is offered to the live `signals` table as if it were a fresh signal. The schema
must reject exactly the rows whose geometry is impossible -- measured 2026-08-21
as 22 of 92 (ZEC 19, TAO 1, GOLD 2).

If this script rejects a different number, the schema is wrong, not the data.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from instrument import store  # noqa: E402

EXPECTED_REJECTS = 22
RULESET = "legacy-import"


def _rr(entry: float, sl: float, target: float) -> float | None:
    risk = abs(entry - sl)
    return None if risk == 0 else round(abs(target - entry) / risk, 3)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=str(Path.home() /
                        "Documents/ideas/vigil-legacy-backup/trades-20260821.db"))
    parser.add_argument("--db", default=":memory:")
    args = parser.parse_args()

    src = sqlite3.connect(f"file:{args.source}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    rows = src.execute(
        "SELECT id, symbol, type, entry_price, sl_price, tp1_price, tp2_price, "
        "status, open_time, close_time, strategy_version, conf_score, is_sim FROM trades"
    ).fetchall()

    accepted, rejected = 0, []
    with store.connect(args.db) as conn:
        for r in rows:
            entry, sl, tp1 = r["entry_price"], r["sl_price"], r["tp1_price"]
            side = "LONG" if (r["type"] or "").upper() == "LONG" else "SHORT"
            valid = None
            if None not in (entry, sl):
                valid = 1 if ((side == "LONG" and sl < entry) or
                              (side == "SHORT" and sl > entry)) else 0

            store.insert_legacy(
                conn, id=r["id"], symbol=r["symbol"], side=side, entry_price=entry,
                sl_price=sl, tp1_price=tp1, tp2_price=r["tp2_price"], status=r["status"],
                open_time=r["open_time"], close_time=r["close_time"],
                strategy=r["strategy_version"], conf_score=r["conf_score"],
                is_sim=r["is_sim"], sl_side_valid=valid,
                import_note="paper, 2026-03-30..2026-05-06, not comparable to live",
            )

            try:
                store.insert_signal(
                    conn,
                    ruleset_version=RULESET,
                    emitted_at=r["open_time"] or "1970-01-01T00:00:00Z",
                    bar_ts=r["open_time"] or f"1970-01-01T00:00:{r['id']:02d}Z",
                    symbol=r["symbol"], timeframe="legacy", side=side,
                    decision="SENT", decision_reason="legacy replay",
                    entry_price=entry, sl_price=sl, tp1_price=tp1, tp2_price=r["tp2_price"],
                    r_unit=abs(entry - sl) if None not in (entry, sl) else None,
                    rr_tp1=_rr(entry, sl, tp1) if None not in (entry, sl, tp1) else None,
                    breakeven_wr=None,
                    trigger={"legacy_id": r["id"], "strategy": r["strategy_version"]},
                )
                accepted += 1
            except store.RowRejected as exc:
                rejected.append((r["id"], r["symbol"], side, exc.constraint))
        conn.commit()

    by_constraint: dict[str, int] = {}
    by_symbol: dict[str, int] = {}
    for _, symbol, _, constraint in rejected:
        by_constraint[constraint] = by_constraint.get(constraint, 0) + 1
        by_symbol[symbol] = by_symbol.get(symbol, 0) + 1

    print(f"legacy rows read : {len(rows)}")
    print(f"accepted         : {accepted}")
    print(f"rejected         : {len(rejected)}  (expected {EXPECTED_REJECTS})")
    print(f"  by constraint  : {by_constraint}")
    print(f"  by symbol      : {by_symbol}")

    ok = len(rejected) == EXPECTED_REJECTS
    print("\nPHASE 1 ACCEPTANCE:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
