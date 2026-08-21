"""Keeping the knowledge base current from inside the running loop.

Split out of main.py to keep both files inside the 250-line ceiling, and because
"when do we refresh" is its own concern: `make knowledge-refresh` existed for hours
and never ran once, since this host has no crontab and the schedule depended on
somebody installing one. A schedule nobody installs is the same defect as a date
nobody edits -- which is the bug the knowledge module exists to kill.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import watch
from .knowledge import refresh

REFRESH_EVERY = timedelta(hours=6)
_last_refresh: datetime | None = None




def refresh_if_due(conn, now_iso: str) -> str:
    """Keep the knowledge base current from inside the loop.

    There is no crontab on this host, so `make knowledge-refresh` existed and
    nothing ever called it -- the cache was still empty in production hours after
    the module shipped. A schedule that depends on someone remembering to install
    it is the same failure as a date that depends on someone remembering to edit
    it, which is the bug this whole module exists to kill.
    """
    global _last_refresh
    now = datetime.now(timezone.utc)
    if _last_refresh and now - _last_refresh < REFRESH_EVERY:
        return "skipped"
    _last_refresh = now
    report, problems = refresh.run(conn)
    if problems:
        watch.record(conn, "knowledge", "degraded", "; ".join(problems)[:200], now_iso)
    conn.commit()
    return f"{len(report)} entries, {len(problems)} problems"
