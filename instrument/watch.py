"""watch.py — external liveness for the instrument.

The legacy bot was down 54 days across two incidents (30 in Apr-May, 24 in
May-Jun) and nobody noticed, because its watchdog restarted THREADS from
inside the process (thread_health.py) -- it could not detect the process
itself dying. This module exists to make that failure mode structurally
harder: state lives in the `heartbeats` table (never a file -- the legacy
`api_health.py:20` state file on ephemeral disk is the same reason
signal_episodes lost five months of telemetry), and `is_stale` is built to be
called by something OUTSIDE this process -- a cron, a systemd timer, another
service -- because the one thing an internal watchdog cannot see is its own
process dying.

Dedup-by-state-change is ported from scalp_bot/api_health.py's watchdog():
alert once per transition (healthy->broken or broken->healthy), never once
per tick.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from .store import beat

OK = "OK"
DOWN = "DOWN"
DEGRADED = "DEGRADED"
_HEALTHY = (OK, DEGRADED)

Check = Callable[[], dict[str, Any]]


def check_data_feed(fetch_prices: Callable[[], dict[str, float]]) -> dict[str, Any]:
    """fetch_prices() -> {symbol: last_price}. Injectable so tests never hit a
    real exchange. A price of zero is not "market closed" -- the legacy macro
    report published `SPY: $0.00 | TLT: $0.00 | BRI: 0 NEUTRAL` as if it were
    data, and that is exactly the shape of bug this check exists to catch."""
    try:
        prices = fetch_prices()
    except Exception as exc:  # border: fetch_prices is an arbitrary injected probe
        return {"name": "data_feed", "status": DOWN, "detail": type(exc).__name__}
    if not prices:
        return {"name": "data_feed", "status": DOWN, "detail": "empty feed"}
    zeroed = sorted(sym for sym, px in prices.items() if not px)
    if zeroed:
        return {"name": "data_feed", "status": DOWN, "detail": f"zero price: {', '.join(zeroed)}"}
    return {"name": "data_feed", "status": OK, "detail": f"{len(prices)} symbols live"}


def check_telegram(get_me: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """get_me() -> the getMe response body. Injectable for the same reason."""
    try:
        result = get_me()
    except Exception as exc:  # border: get_me is an arbitrary injected probe
        return {"name": "telegram", "status": DOWN, "detail": type(exc).__name__}
    if not result.get("ok"):
        return {"name": "telegram", "status": DOWN, "detail": "getMe not ok"}
    username = result.get("result", {}).get("username", "bot")
    return {"name": "telegram", "status": OK, "detail": f"@{username}"}


def _last_status(conn: sqlite3.Connection, component: str) -> str | None:
    row = conn.execute("SELECT detail FROM heartbeats WHERE component=?", (component,)).fetchone()
    if not row or not row["detail"]:
        return None
    try:
        return json.loads(row["detail"]).get("status")
    except (TypeError, ValueError):
        return None


def record(conn: sqlite3.Connection, component: str, status: str, detail: str,
           when: str | None = None) -> None:
    when = when or datetime.now(timezone.utc).isoformat()
    beat(conn, component, when, {"status": status, "detail": detail})


def watchdog(conn: sqlite3.Connection, checks: dict[str, Check], alert: Callable[[str], None]) -> bool:
    """Run each check, compare against the state PERSISTED IN heartbeats (not a
    file), and alert only on a transition. Returns True if anything was sent."""
    alerted = False
    for name, check in checks.items():
        result = check()
        prev = _last_status(conn, name)
        record(conn, name, result["status"], result["detail"])
        healthy_new = result["status"] in _HEALTHY
        healthy_old = prev in _HEALTHY or prev is None
        if not healthy_new and healthy_old:
            alert(f"DOWN: {name} — {result['detail']}")
            alerted = True
        elif healthy_new and prev is not None and not healthy_old:
            alert(f"RECOVERED: {name}")
            alerted = True
    return alerted


def _parse_ts(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def is_stale(conn: sqlite3.Connection, component: str, max_age_minutes: float,
             now: datetime | None = None) -> bool:
    """Dead-man check meant to be called from OUTSIDE this process (a cron, a
    systemd timer). True if `component` never beat, or its last beat is older
    than max_age_minutes. This is the check the legacy watchdog never had --
    it could restart a dead thread, but nothing outside it ever asked
    "when did this last actually run?". `now` is injectable so callers (and
    tests) can pin the clock instead of racing the real one."""
    row = conn.execute("SELECT last_beat FROM heartbeats WHERE component=?", (component,)).fetchone()
    if row is None:
        return True
    last_beat = _parse_ts(row["last_beat"])
    if last_beat is None:
        return True
    now = now or datetime.now(timezone.utc)
    return (now - last_beat) > timedelta(minutes=max_age_minutes)


def weekly_pulse(conn: sqlite3.Connection, component: str, max_age_minutes: float,
                  now: datetime | None = None, window_days: int = 7) -> dict[str, Any]:
    """Pure -- computes the weekly liveness pulse, sends nothing (that is the
    caller's job). Must be produced -- and sent -- on a fixed schedule every
    week EVEN WHEN there is nothing to report: at a couple of alerts a day, a
    dead process and a quiet market are both silent, which is exactly how 54
    days passed unnoticed. `last_signal_at` is the part that tells them apart
    on sight -- an old date is obvious immediately, an absent message never is."""
    now = now or datetime.now(timezone.utc)
    window_start = (now - timedelta(days=window_days)).isoformat()
    alerts_this_week = conn.execute(
        "SELECT COUNT(*) AS n FROM signals WHERE decision='SENT' AND emitted_at >= ?",
        (window_start,)).fetchone()["n"]
    last_signal_at = conn.execute(
        "SELECT MAX(emitted_at) AS last FROM signals WHERE decision='SENT'").fetchone()["last"]
    return {
        "status": "posible caída" if is_stale(conn, component, max_age_minutes, now) else "vivo",
        "alerts_this_week": alerts_this_week,
        "last_signal_at": last_signal_at,
        "generated_at": now.isoformat(),
    }


_STATUS_EMOJI = {"vivo": "🟢", "posible caída": "🟡"}


def format_weekly_pulse(pulse: dict[str, Any]) -> str:
    """Pure text render, no network -- e.g. '🟢 vivo · 0 alertas esta semana ·
    última señal: 2026-08-14'. Whoever sends this is a different function.

    'nunca' used to stand alone for last_signal_at, which reads as an error
    even when the honest reason is that the instrument just started -- this
    says that plainly instead of leaving it to sound like one."""
    alerts = pulse["alerts_this_week"]
    plural = "" if alerts == 1 else "s"
    if pulse["last_signal_at"]:
        last = f"última señal: {pulse['last_signal_at'][:10]}"
    else:
        last = "aún no manda ninguna señal"
    emoji = _STATUS_EMOJI.get(pulse["status"], "")
    return f"{emoji} {pulse['status']} · {alerts} alerta{plural} esta semana · {last}".strip()
