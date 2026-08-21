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
        """Break-even hit rate IF the whole position exited at TP1.

        Kept as a reference figure only. It is NOT what the alert should quote,
        because no trade resolves that way: resolver.py takes half off at TP1 and
        runs the rest, so the real bar is the range below.
        """
        return 1.0 / (1.0 + self.rr_tp1)

    def breakeven_wr_range(self, partial_at_tp1: float = 0.5) -> tuple[float, float]:
        """(best, worst) break-even hit rate under the partial-exit scheme actually used.

        A winner pays `partial*rr_tp1 + (1-partial)*x`, where x is rr_tp2 when the
        runner reaches TP2 and 0 when it is stopped at breakeven. Those two ends bracket
        the truth; nothing in between is knowable before the fact.

        This exists because quoting the all-out number was wrong in both directions: at
        0.7R/1.3R it prints 58.8% while the real bar sits between 50.0% and 74.1%, and
        notify.py was comparing it against an empirical win rate produced by the partial
        scheme -- so the alert could say "you are ahead" against a floor 15 points too low.
        """
        won = partial_at_tp1 * self.rr_tp1
        best = 1.0 / (1.0 + won + (1.0 - partial_at_tp1) * self.rr_tp2)
        worst = 1.0 / (1.0 + won)
        return best, worst

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
