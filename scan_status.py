"""
scan_status.py — `/scan` command builder (v1.2.0).

Renders current state of every crypto symbol the bot watches:
- distance to entry triggers (RSI, EMA reclaim)
- active blockers (regime filter, kill switch, hour block, NO_SHORT list)
- open trades (entry, current PnL, TSL)

Goal: give Fernando certainty about WHY no alert fired.
"""

from __future__ import annotations

from datetime import datetime, timezone

from config import (
    SYMBOLS,
    RSI_LONG_ENTRY,
    RSI_SHORT_ENTRY,
    V1_SHORT_ENABLED,
)

# V1-LONG no tiene kill switch dedicado en config.py — siempre activo.
# Cambiar a False acá si llega a desactivarse.
V1_LONG_ENABLED = True


# Hours in UTC that the swing/scalp loops block (0% WR audit).
# Mirrors logic spread across strategies.py + swing_bot.py — keep in sync.
_BLOCKED_HOURS_UTC = {1, 4, 6, 10, 11, 14, 15, 16, 17, 20}


def _hour_status() -> tuple[str, bool]:
    h = datetime.now(timezone.utc).hour
    blocked = h in _BLOCKED_HOURS_UTC
    return f"{h:02d}h UTC", blocked


def _open_trades_lookup() -> dict[str, dict]:
    try:
        import tracker
        return {t["symbol"].upper(): t for t in tracker.get_open_trades()}
    except Exception:
        return {}


def _format_long_status(sym: str, prices: dict) -> str:
    p = prices.get(sym, 0.0)
    rsi = prices.get(f"{sym}_RSI", 50.0)
    ema = None
    try:
        import scalp_alert_bot as _sab
        ema = _sab.GLOBAL_CACHE["indicators"].get(sym, {}).get("ema_200")
    except Exception:
        ema = None

    needs = []
    if rsi > RSI_LONG_ENTRY:
        delta = rsi - RSI_LONG_ENTRY
        needs.append(f"RSI {rsi:.0f}→≤{RSI_LONG_ENTRY:.0f} (+{delta:.0f}pts arriba)")
    if ema and p < ema:
        gap_pct = (ema - p) / p * 100
        needs.append(f"reclaim EMA200 ${ema:,.2f} ({gap_pct:+.1f}%)")

    if not needs:
        return f"🟢 <b>{sym}</b> long armado · ${p:,.2f} · RSI {rsi:.0f}"
    return f"🟡 <b>{sym}</b> long pending · ${p:,.2f} · falta " + " · ".join(needs)


def _format_short_status(sym: str, prices: dict, no_short: set[str]) -> str | None:
    if sym in no_short or sym == "TAO":
        return f"⚫ <b>{sym}</b> short bloqueado · NO_SHORT list (WR<10%)"
    if not V1_SHORT_ENABLED:
        return None  # global kill — already shown in /params
    p = prices.get(sym, 0.0)
    rsi = prices.get(f"{sym}_RSI", 50.0)
    if rsi < RSI_SHORT_ENTRY:
        return f"🟠 <b>{sym}</b> short pending · RSI {rsi:.0f}→≥{RSI_SHORT_ENTRY:.0f} ({RSI_SHORT_ENTRY - rsi:+.0f}pts abajo)"
    return f"🔴 <b>{sym}</b> short armado · ${p:,.2f} · RSI {rsi:.0f}"


def build_scan_report(prices: dict | None) -> str:
    if prices is None:
        prices = {}

    hour_label, hour_blocked = _hour_status()
    hour_line = f"⏱️ <code>{hour_label}</code>" + (" 🚫 hora bloqueada (0% WR hist.)" if hour_blocked else " ✅")

    open_trades = _open_trades_lookup()

    # Pull NO_SHORT lazily (avoids importing swing_bot at top — heavy module)
    try:
        from swing_bot import NO_SHORT
        no_short = {s.split("/")[0] for s in NO_SHORT}
    except Exception:
        no_short = {"TAO"}

    lines = [
        "🔍 <b>SCAN — estado próximas alertas</b>",
        hour_line,
        "<code>━━━━━━━━━━━━━</code>",
    ]

    if open_trades:
        lines.append("<b>📂 Trades abiertos</b>")
        for sym, t in open_trades.items():
            entry = t.get("entry") or t.get("entry_price") or 0.0
            cur = prices.get(sym, entry)
            pnl_pct = ((cur - entry) / entry * 100) if entry else 0.0
            side = (t.get("side") or t.get("direction") or "?").upper()
            sign = "🟢" if pnl_pct >= 0 else "🔴"
            lines.append(f"  {sign} {sym} {side} @ ${entry:,.2f} → ${cur:,.2f} ({pnl_pct:+.2f}%)")
        lines.append("<code>━━━━━━━━━━━━━</code>")

    if V1_LONG_ENABLED:
        lines.append("<b>🟢 LONGS</b>")
        for sym in SYMBOLS:
            if sym in open_trades:
                continue
            lines.append("  " + _format_long_status(sym, prices))
    else:
        lines.append("⚠️ V1-LONG kill switch OFF — no longs hasta reactivar")

    lines.append("<b>🔴 SHORTS</b>")
    short_count = 0
    for sym in SYMBOLS:
        if sym in open_trades:
            continue
        ss = _format_short_status(sym, prices, no_short)
        if ss:
            lines.append("  " + ss)
            short_count += 1
    if short_count == 0:
        lines.append("  (todos bloqueados — V1_SHORT_ENABLED=False o NO_SHORT)")

    # PTS watchlist hook (read-only)
    try:
        import stock_watchlist
        wl = stock_watchlist.list_entries()
        if wl:
            lines.append("<code>━━━━━━━━━━━━━</code>")
            lines.append("<b>📊 PTS Watchlist</b> (manual)")
            for ticker, entry in wl.items():
                lines.append(f"  {ticker} {entry['side']} @ ${entry['entry']:.2f} stop ${entry['stop']:.2f} → {entry.get('targets','—')}")
    except Exception:
        pass

    return "\n".join(lines)
