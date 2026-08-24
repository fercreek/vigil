"""Lo que cambia cuando el instrumento cotiza en una bolsa y no en un exchange.

Tres diferencias, y las tres muerden si se ignoran:

  1. El reloj. Una vela horaria de cripto tarda una hora de reloj; una de acciones
     tarda una hora SOLO mientras el mercado esta abierto -- 6.5 al dia, cinco dias
     de siete. `cooldown_hours` traduce velas a horas de reloj por mercado, porque
     main.py::_in_cooldown compara timestamps y no cuenta barras. Sin esa
     traduccion, 72 velas de enfriamiento se vuelven 14 en acciones y la misma
     subida se avisa cinco veces.
  2. El lado. Medido sobre 730 dias y 29 tickers (ver EQUITIES.md): LONG +0.216R
     con n=138 y el IC entero sobre cero; SHORT -0.012R con n=130. En cripto la
     muestra por lado es n=26 y no alcanza para recortar nada, asi que la
     restriccion se aplica SOLO a acciones.
  3. El feed. yfinance en vez de la cadena de exchanges; lo resuelve feed.py.

Este modulo no decide senales. rules.py sigue siendo el unico que las emite, puro
y sin saber en que mercado esta -- igual que no sabe de calendarios FOMC.
"""
from __future__ import annotations

# El universo medido en EQUITIES.md. No se eligio por rendimiento pasado: rankear
# tickers con n=5 por ticker es el cherry-picking que este repo ya pago caro una vez.
# El criterio es cobertura -- que el conjunto produzca muestra suficiente (~1.3
# senales LONG por semana entre los 29) para que la kill-rule pueda dispararse algun dia.
EQUITY_SYMBOLS = [
    "NVDA", "TSLA", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "AVGO", "AMD", "PLTR",
    "COIN", "HOOD", "SOFI", "MSTR", "IONQ", "RGTI", "SOUN",
    "OKLO", "SMR", "UUUU", "VST", "IREN", "CRWV", "CLSK",
    "RKLB", "ASTS", "MP", "XLE", "XOM",
]
_EQUITY_SET = frozenset(EQUITY_SYMBOLS)

# Sesion regular de NYSE/Nasdaq: 09:30-16:00 ET son 6.5 horas, cinco dias de siete.
BARS_PER_SESSION = 6.5
SESSIONS_PER_WEEK = 5
DAYS_PER_WEEK = 7


def is_equity(symbol: str) -> bool:
    return symbol.upper() in _EQUITY_SET


def cooldown_hours(symbol: str, bars: int) -> float:
    """Horas de RELOJ que ocupan `bars` velas horarias en el mercado de `symbol`.

    Cripto cotiza continuo: una vela, una hora. Acciones no, y la diferencia no es
    menor -- 72 velas son 15.5 dias naturales, no tres.
    """
    if not is_equity(symbol):
        return float(bars)
    sessions = bars / BARS_PER_SESSION
    return sessions * (DAYS_PER_WEEK / SESSIONS_PER_WEEK) * 24.0


def universe_of(symbol: str) -> str:
    """El nombre que usan scoreboard.py y kill_rule.py. Vive aqui para que la
    pertenencia a un universo se decida en un solo sitio."""
    return "equities" if is_equity(symbol) else "crypto"


def side_allowed(symbol: str, side: str) -> bool:
    """False solo para el caso que la medicion descarto: SHORT en acciones."""
    return not (is_equity(symbol) and side == "SHORT")


def side_rejection_reason(symbol: str, side: str) -> str:
    return (f"lado no operado en acciones: SHORT midio -0.012R con n=130 "
            f"sobre 730 dias (LONG: +0.216R, n=138) -- ver EQUITIES.md")
