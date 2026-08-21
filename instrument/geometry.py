"""Trade geometry: entry/stop/targets, and the arithmetic that judges them.

The legacy bot advertised an R:R its own levels did not deliver. swing_bot.py:116
computed rr1 from the multipliers (ATR_TP1/ATR_SL = 1.25) while swing_bot.py:109
widened the stop with `max(atr*2.0, price*0.01)` and left TP1 at atr*2.5 -- so when
the 1% floor bound, the real ratio fell below the advertised one. Measured across
76 SWING trades the mean was 1.18, demanding a 45.8% hit rate against 17.1% actual.

Rule here: R:R is ALWAYS derived from the actual prices. There is no code path
that reports a ratio computed from a multiplier.
"""
from __future__ import annotations

from dataclasses import dataclass

LONG, SHORT = "LONG", "SHORT"


class InvalidGeometry(ValueError):
    """The levels do not describe a tradeable position."""


@dataclass(frozen=True)
class Geometry:
    side: str
    entry: float
    sl: float
    tp1: float
    tp2: float

    @property
    def r_unit(self) -> float:
        """One R, in price."""
        return abs(self.entry - self.sl)

    @property
    def rr_tp1(self) -> float:
        return abs(self.tp1 - self.entry) / self.r_unit

    @property
    def rr_tp2(self) -> float:
        return abs(self.tp2 - self.entry) / self.r_unit

    @property
    def breakeven_wr(self) -> float:
        """The hit rate this geometry needs just to break even, all-out at TP1.

        Printed on every alert. A 1.18 R:R needs 45.8%; saying so up front is the
        difference between a signal and a suggestion.
        """
        return 1.0 / (1.0 + self.rr_tp1)

    def r_at(self, price: float) -> float:
        """Signed R multiple of `price` relative to entry."""
        direction = 1.0 if self.side == LONG else -1.0
        return direction * (price - self.entry) / self.r_unit


def assert_geometry(side: str, entry: float, sl: float, tp1: float, tp2: float,
                    min_rr: float = 0.0) -> Geometry:
    """Build a Geometry or refuse. This is the code-side twin of the schema CHECKs.

    22 of the legacy bot's 92 rows would not survive this function.
    """
    if side not in (LONG, SHORT):
        raise InvalidGeometry(f"side must be LONG or SHORT, got {side!r}")
    for name, value in (("entry", entry), ("sl", sl), ("tp1", tp1), ("tp2", tp2)):
        if value is None or value <= 0:
            raise InvalidGeometry(f"{name} must be a positive price, got {value!r}")
    if entry == sl:
        raise InvalidGeometry("stop equals entry: risk is zero, the trade has no R")

    if side == LONG and not (sl < entry < tp1 <= tp2):
        raise InvalidGeometry(
            f"LONG needs sl < entry < tp1 <= tp2, got {sl} / {entry} / {tp1} / {tp2}")
    if side == SHORT and not (sl > entry > tp1 >= tp2):
        raise InvalidGeometry(
            f"SHORT needs sl > entry > tp1 >= tp2, got {sl} / {entry} / {tp1} / {tp2}")

    geometry = Geometry(side=side, entry=float(entry), sl=float(sl),
                        tp1=float(tp1), tp2=float(tp2))
    if min_rr and geometry.rr_tp1 < min_rr:
        raise InvalidGeometry(
            f"R:R to TP1 is {geometry.rr_tp1:.2f}, below the {min_rr:.2f} floor "
            f"(needs {geometry.breakeven_wr:.1%} hit rate)")
    return geometry
