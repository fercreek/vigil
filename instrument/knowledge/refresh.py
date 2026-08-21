"""knowledge/refresh.py — the cron entry point: run every fetcher in
sources.py, cache.put() the ones that succeeded, print a freshness report.

`run()` never lets one fetcher's failure stop the rest. Every fetcher in
sources.py already turns a network/parse failure into FetchResult(ok=False)
instead of raising (sources.py's FETCH_ERRORS is that border); the same
tuple wraps the call to `fetcher()` here too, as a second line of defence
against a registered callable that forgot its own border. Neither needs
`except Exception` -- see sources.py's docstring for why that stays off the
table. This loop's job is narrower: make sure a failure is never absent
from `problems`, so it shows up in the report instead of dropping silently.

Exit code: 1 if anything in `problems` touched a critical key -- a failed
fetch, a cache write that couldn't land, a missing credential, or a critical
entry that is still expired after this run. That last case is what the
legacy bot never had: `_LEARNING_LOG`-worthy modules ran with an expired
value for months because nothing ever asked "is this still good?" out loud.
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Callable

from ..store import connect
from . import cache, sources

logger = logging.getLogger(__name__)

DEFAULT_SYMBOL = "ZEC"
DEFAULT_TICKERS = ["MSTR", "COIN"]  # crypto-proxy equities the LLM note leans on

# key -> (fetcher, critical). `critical=True` means a failure or an expired
# value for this key must fail the cron's exit code, not just print a line.
REGISTRY: dict[str, tuple[Callable[[], sources.FetchResult], bool]] = {
    "derivatives": (lambda: sources.fetch_derivatives(DEFAULT_SYMBOL), True),
    "fear_greed": (sources.fetch_fear_greed, True),
    "stablecoin_supply": (sources.fetch_stablecoin_supply, True),
    "fomc_calendar": (sources.fetch_fomc_calendar, True),
    "earnings": (lambda: sources.fetch_earnings(DEFAULT_TICKERS), True),
    "news": (sources.fetch_news, True),
}

# cache.put()'s only realistic failure mode -- a locked/corrupt sqlite file.
# Specific, not `except Exception`: see sources.py's module docstring for why.
CACHE_ERRORS = (sqlite3.Error,)


def run(conn: sqlite3.Connection, only: list[str] | None = None,
        registry: dict[str, tuple[Callable[[], sources.FetchResult], bool]] | None = None,
        now: datetime | None = None) -> tuple[list[dict], list[str]]:
    """Refresh every key in `registry` (or just `only`). Returns
    (cache.freshness_report(conn), problems) -- problems is this RUN's own
    account of what went wrong, independent of freshness_report, because a
    key that has NEVER once succeeded has no row to report on yet."""
    registry = registry or REGISTRY
    now = now or datetime.now(timezone.utc)
    keys = only or list(registry)
    problems: list[str] = []
    for key in keys:
        if key not in registry:
            problems.append(f"{key}: not a registered knowledge key")
            continue
        fetcher, critical = registry[key]
        try:
            result = fetcher()
        except sources.FETCH_ERRORS as exc:  # a fetcher that forgot to catch its own border
            problems.append(f"{key}: fetcher raised -- {type(exc).__name__}: {exc}")
            continue
        if not result.ok:
            problems.append(f"{key}: fetch failed -- {result.error}")
            continue
        try:
            cache.put(conn, key, result.value, result.source, result.valid_until)
            conn.commit()
        except CACHE_ERRORS as exc:
            problems.append(f"{key}: cache write failed -- {exc}")
            continue
        if isinstance(result.value, dict) and result.value.get("available") is False and critical:
            problems.append(f"{key}: {result.value.get('reason', 'unavailable')}")

    report = cache.freshness_report(conn, now)
    expired_now = {row["key"] for row in report if row["expired"]}
    for key in keys:
        entry = registry.get(key)
        if entry and entry[1] and key in expired_now:
            msg = f"{key}: cached value is expired"
            if msg not in problems:
                problems.append(msg)
    return report, problems


def _print_report(report: list[dict], problems: list[str]) -> None:
    print("== knowledge freshness ==")
    for row in report:
        flag = "STALE" if row["expired"] else "fresh"
        manual = " (manual)" if row["is_manual"] else ""
        age = f"{row['age_hours']}h" if row["age_hours"] is not None else "?"
        print(f"  [{flag:5}] {row['key']:<20} age={age}{manual}")
    print("== problems this run ==" if problems else "== no problems this run ==")
    for problem in problems:
        print(f"  ! {problem}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh the fundamentals knowledge cache.")
    parser.add_argument("--db", default=None, help="path to the instrument sqlite db")
    parser.add_argument("--only", action="append", help="refresh only this key (repeatable)")
    args = parser.parse_args(argv)
    with connect(args.db) as conn:
        report, problems = run(conn, only=args.only)
    _print_report(report, problems)
    for problem in problems:
        logger.error(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
