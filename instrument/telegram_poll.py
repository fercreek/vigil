"""telegram_poll.py — reads Telegram getUpdates so the bot can answer.

Two jobs, both driven by taps on messages this process already sends: (1) the
persistent keyboard's report buttons -- only the three things the instrument
can honestly answer today (scoreboard, weekly pulse, knowledge freshness),
replacing the legacy six-button keyboard that answered nothing; (2) the
TOMADA/PASO callback notify.signal_keyboard() emits on every SENT signal --
unread before this module existed, so `manual_fills` stayed empty and
scoreboard.py's taken-rate gate never had data to unsuspend its conclusions.

Runs in its own thread with its own sqlite3 connection (see main.py's
run_forever) so a long-poll here never blocks the scan loop.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

import requests

from . import notify, scoreboard, watch
from .knowledge import cache
from .store import connect

logger = logging.getLogger(__name__)

_API = "https://api.telegram.org/bot{token}/{method}"
LONG_POLL_SECONDS = 25
GETUPDATES_RETRY_SECONDS = 5

# BTC as the reference symbol for "is the scanner alive": most liquid of the
# six, and any real feed/process outage shows up on it first.
PULSE_COMPONENT = "scan:BTC"
PULSE_MAX_AGE_MINUTES = 60


# Each value takes the poller's own connection and returns the message body.
# A new button needs a real handler here first -- growing this back toward
# the legacy bot's six is exactly the mistake this module exists to undo.
REPORT_BUTTONS: dict[str, Callable[[sqlite3.Connection], str]] = {
    "📊 Scoreboard": lambda conn: scoreboard.render_report(scoreboard.build_report(conn)),
    "💓 Pulso semanal": lambda conn: watch.format_weekly_pulse(
        watch.weekly_pulse(conn, PULSE_COMPONENT, PULSE_MAX_AGE_MINUTES)),
    "🗂 Frescura": lambda conn: _format_freshness(cache.freshness_report(conn)),
}


def keyboard_markup() -> dict:
    """The persistent reply keyboard for REPORT_BUTTONS' keys."""
    return {"keyboard": [[{"text": label}] for label in REPORT_BUTTONS],
            "resize_keyboard": True}


def _format_freshness(report: list[dict]) -> str:
    """'caché de conocimiento' reads as engineer-talk on a phone; 'los datos
    que uso' says the same thing. Each row translates its dict fields into a
    sentence -- never the dict itself."""
    if not report:
        return "🗂 Todavía no tengo datos guardados que revisar."
    lines = ["🗂 Datos que uso para las señales:"]
    for row in report:
        age = f"actualizado hace {row['age_hours']:.1f}h" if row["age_hours"] is not None else "edad desconocida"
        if row["expired"]:
            hours = row["expired_for_hours"]
            status = f"⚠️ vencido hace {hours:.1f}h" if hours is not None else "⚠️ sin vigencia registrada"
        else:
            status = "vigente"
        manual = " · cargado a mano" if row["is_manual"] else ""
        lines.append(f"- {row['key']}: {age}{manual} · {status}")
    return "\n".join(lines)


def _api_call(token: str, method: str, **payload: Any) -> dict:
    url = _API.format(token=token, method=method)
    response = requests.post(url, json=payload, timeout=LONG_POLL_SECONDS + 10)
    return response.json()


def _fetch_updates(token: str, offset: int) -> list[dict]:
    result = _api_call(token, "getUpdates", offset=offset, timeout=LONG_POLL_SECONDS)
    if not result.get("ok"):
        logger.error("getUpdates not ok: %s", result)
        return []
    return result.get("result", [])


def _handle_text(conn: sqlite3.Connection, token: str, chat_id: Any, text: str) -> None:
    handler = REPORT_BUTTONS.get((text or "").strip())
    if handler is None or chat_id is None:
        return
    body = handler(conn)
    _api_call(token, "sendMessage", chat_id=chat_id, text=notify.safe_html(body),
              parse_mode="HTML")


def _handle_callback(conn: sqlite3.Connection, token: str, callback: dict) -> None:
    """TOMADA/PASO tap -> one manual_fills row, then the message is edited so
    the mark is visible and can't be tapped again (empty inline_keyboard)."""
    choice, _, raw_id = callback.get("data", "").partition(":")
    if choice not in ("taken", "pass"):
        return
    signal_id = int(raw_id)
    now = datetime.now(timezone.utc)
    conn.execute(
        "INSERT INTO manual_fills (signal_id, taken, filled_at) VALUES (?, ?, ?)",
        (signal_id, 1 if choice == "taken" else 0, now.isoformat()),
    )
    conn.commit()

    message = callback.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    message_id = message.get("message_id")
    if chat_id is not None and message_id is not None:
        edited = notify.acknowledge_text(message.get("text", ""), choice, now)
        _api_call(token, "editMessageText", chat_id=chat_id, message_id=message_id,
                  text=notify.safe_html(edited), parse_mode="HTML",
                  reply_markup={"inline_keyboard": []})

    callback_id = callback.get("id")
    if callback_id is not None:
        _api_call(token, "answerCallbackQuery", callback_query_id=callback_id)


def poll_once(conn: sqlite3.Connection, token: str, offset: int) -> int:
    """Fetch and handle one batch of updates, return the next offset. Each
    update is guarded individually so one bad callback can't stop the rest
    of the batch or get retried forever -- offset always advances past it."""
    for update in _fetch_updates(token, offset):
        offset = update["update_id"] + 1
        try:
            if "callback_query" in update:
                _handle_callback(conn, token, update["callback_query"])
            elif "message" in update:
                message = update["message"]
                _handle_text(conn, token, (message.get("chat") or {}).get("id"),
                             message.get("text", ""))
        except (requests.RequestException, sqlite3.IntegrityError, ValueError, KeyError) as exc:
            logger.error("update %s failed: %s: %s", update.get("update_id"),
                         type(exc).__name__, exc)
    return offset


def poll_forever(token: str, db_path: str | None, stop: threading.Event) -> None:
    """Long-poll until `stop` is set, on its own connection (see module docstring)."""
    offset = 0
    with connect(db_path) as conn:
        while not stop.is_set():
            try:
                offset = poll_once(conn, token, offset)
            except requests.RequestException as exc:
                logger.error("getUpdates failed: %s", exc)
                time.sleep(GETUPDATES_RETRY_SECONDS)


def start_background(token: str, db_path: str | None) -> tuple[threading.Thread, threading.Event]:
    """Starts the poller as a daemon thread; returns (thread, stop_event) for a clean shutdown."""
    stop = threading.Event()
    thread = threading.Thread(target=poll_forever, args=(token, db_path, stop), daemon=True)
    thread.start()
    return thread, stop
