"""Position-sizing hint for a signal -- informational, the user executes by
hand. Split out of notify.py: sizing is a different job than notifying.
Loss-at-stop always equals the risked amount by construction (R-sizing),
so it needs no separate lookup.
"""
from __future__ import annotations

import sqlite3

_MINUS = "−"  # real minus sign, not a hyphen


def _field(row: dict | sqlite3.Row, key: str, default=None):
    try:
        value = row[key]
    except (KeyError, IndexError):
        return default
    return default if value is None else value


def _money(x: float) -> str:
    return f"{'' if x >= 0 else _MINUS}${abs(x):,.0f}"


def position_hint(row: dict | sqlite3.Row, account_size: float = 1000.0,
                   risk_pct: float = 0.01) -> str | None:
    entry, r_unit = _field(row, "entry_price"), _field(row, "r_unit")
    if not entry or not r_unit:
        return None
    symbol = _field(row, "symbol", "")
    risk = account_size * risk_pct
    units = risk / r_unit
    line = (f"💰 Riesgo {risk_pct * 100:.0f}% de {_money(account_size)} = {units:.1f} {symbol} "
            f"(~{_money(units * entry)})")
    sl = _field(row, "sl_price")
    if sl:
        line += f" · SL a {abs(sl - entry) / entry * 100:.2f}% = {_money(-risk)}"
    return line
