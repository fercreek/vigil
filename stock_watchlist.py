"""
stock_watchlist.py — manual PTS watchlist persisted to JSON (v1.2.0).

Backs the `/stocks` Telegram command. Stores entry / stop / targets
extracted from PTS reports so Fernando can:
- query state of pending entries
- see which prices are close to triggers
- track which positions are open via the same DB

Persisted at `data/stock_watchlist.json` (gitignored runtime data).

Usage from Telegram:
  /stocks                                 # list all
  /stocks add SYM SIDE ENTRY STOP T1[,T2,T3]
  /stocks remove SYM
  /stocks status SYM   (alias: just SYM)
"""

from __future__ import annotations

import json
import os
import threading
from typing import Optional

_PATH = "data/stock_watchlist.json"
_LOCK = threading.Lock()


def _load() -> dict:
    if not os.path.exists(_PATH):
        return {}
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(_PATH), exist_ok=True)
    with _LOCK:
        with open(_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def list_entries() -> dict:
    return _load()


def add_entry(ticker: str, side: str, entry: float, stop: float,
              targets: list[float], be: Optional[float] = None,
              note: str = "") -> str:
    ticker = ticker.upper()
    side = side.upper()
    if side not in ("LONG", "SHORT"):
        return "❌ side debe ser LONG o SHORT"
    data = _load()
    data[ticker] = {
        "side": side,
        "entry": float(entry),
        "stop": float(stop),
        "targets": ",".join(f"{t:g}" for t in targets),
        "be": float(be) if be is not None else None,
        "note": note,
    }
    _save(data)
    return f"✅ {ticker} {side} agregado · entry ${entry:g} stop ${stop:g} targets {data[ticker]['targets']}"


def remove_entry(ticker: str) -> str:
    ticker = ticker.upper()
    data = _load()
    if ticker not in data:
        return f"⚠️ {ticker} no está en watchlist"
    del data[ticker]
    _save(data)
    return f"🗑️ {ticker} removido"


def _fetch_price(ticker: str) -> Optional[float]:
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).fast_info
        for key in ("last_price", "regular_market_price", "previous_close"):
            val = getattr(info, key, None) or (info.get(key) if hasattr(info, "get") else None)
            if val:
                return float(val)
    except Exception:
        pass
    return None


def _entry_status(ticker: str, e: dict) -> str:
    side = e["side"]
    entry = e["entry"]
    stop = e["stop"]
    targets = e.get("targets", "")
    cur = _fetch_price(ticker)

    if cur is None:
        return f"  {ticker} {side} @ ${entry:g} stop ${stop:g} targets {targets}  · 📉 sin precio live"

    if side == "LONG":
        pct = (cur - entry) / entry * 100
        triggered = cur >= entry
    else:
        pct = (entry - cur) / entry * 100
        triggered = cur <= entry

    badge = "🟢" if triggered else "⏳"
    return (
        f"  {badge} {ticker} {side} · entry ${entry:g} → cur ${cur:g} "
        f"({pct:+.1f}%) · stop ${stop:g} · targets {targets}"
    )


def status_all() -> str:
    data = _load()
    if not data:
        return "📊 Watchlist vacía. Agrega con:\n<code>/stocks add SYM LONG 22.77 19.60 28,31,35</code>"
    lines = ["📊 <b>PTS Watchlist</b>"]
    for ticker, e in sorted(data.items()):
        lines.append(_entry_status(ticker, e))
    lines.append("\n<code>/stocks add SYM SIDE ENTRY STOP T1,T2,T3</code>")
    return "\n".join(lines)


def status_one(ticker: str) -> str:
    ticker = ticker.upper()
    data = _load()
    if ticker not in data:
        return f"⚠️ {ticker} no está en watchlist. Agrega con /stocks add"
    e = data[ticker]
    body = _entry_status(ticker, e)
    note = e.get("note", "")
    extra = f"\n📝 {note}" if note else ""
    return f"📊 <b>{ticker}</b>\n{body}{extra}"


# ──────────────────────── Command dispatcher ─────────────────────────────────

def handle_command(args: str) -> str:
    """Parse `/stocks` arguments and route to the right handler."""
    parts = args.split() if args else []
    if not parts:
        return status_all()

    sub = parts[0].lower()

    if sub == "add":
        # /stocks add SYM SIDE ENTRY STOP T1[,T2,T3] [BE] [note...]
        if len(parts) < 5:
            return ("Uso: <code>/stocks add SYM SIDE ENTRY STOP T1,T2,T3 [BE] [nota]</code>\n"
                    "Ej: <code>/stocks add UUUU LONG 22.77 19.60 28,31,35 25</code>")
        try:
            ticker = parts[1]
            side = parts[2]
            entry = float(parts[3])
            stop = float(parts[4])
            targets_raw = parts[5] if len(parts) > 5 else ""
            targets = [float(x) for x in targets_raw.split(",") if x.strip()]
            be = float(parts[6]) if len(parts) > 6 and parts[6].replace(".", "").isdigit() else None
            note_idx = 7 if be is not None else 6
            note = " ".join(parts[note_idx:]) if len(parts) > note_idx else ""
            return add_entry(ticker, side, entry, stop, targets, be=be, note=note)
        except (ValueError, IndexError) as e:
            return f"❌ Error parseando args: {e}"

    if sub in ("rm", "remove", "del", "delete"):
        if len(parts) < 2:
            return "Uso: <code>/stocks remove SYM</code>"
        return remove_entry(parts[1])

    if sub in ("status", "info", "show"):
        if len(parts) < 2:
            return status_all()
        return status_one(parts[1])

    if sub == "list":
        return status_all()

    # Treat first arg as ticker shortcut: `/stocks UUUU`
    return status_one(parts[0])
