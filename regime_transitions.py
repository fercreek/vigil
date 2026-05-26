"""regime_transitions.py — Spec 002 (NotebookLM 4 Prompt 5) state machine régimen SP500.

Detecta transiciones de régimen (VERDE_BULL / AMARILLA_INDECISA / NARANJA_BEAR) y
expone helpers para los filtros NotebookLM-recommended:

- **EXPLOSIVE_CORRECTION**: cuando macro transiciona AMARILLA → VERDE, boost alerts
  long de explosive sectors (RKLB, HOOD, ASTS, IONQ-tier). Patrón histórico: tickers
  beta-alta de corrección recientemente recuperan vertical post-confirmación BULL.

- **BARRIDA_OPPORTUNITY**: cuando VIX<22 + SP500>7000 + caída intradía en cluster
  ai_infra/nuclear → NO filtrar por stops rígidos, alertar como oportunidad de compra.
  Patrón NotebookLM: barridas en VERDE_BULL_DORMANT son re-entradas, no breaks.

Persistencia: state previous escrito a `data/macro_state.json` para detectar cambios
entre ciclos del bot. Sobrevive restarts Railway.

Spec 002.5 backlog:
- Wire to strategies.py:V3-REVERSAL (relax funding threshold en BARRIDA_OPPORTUNITY)
- Boost confluence Spec 021 cuando EXPLOSIVE_CORRECTION + boost_explosive ticker
- Métricas en /api/metrics/regime_transitions
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Optional

try:
    from logger_core import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

try:
    from config import (
        SP500_VERDE_THRESHOLD,
        SP500_NARANJA_THRESHOLD,
        VIX_DORMANT_THRESHOLD,
    )
except ImportError:
    SP500_VERDE_THRESHOLD = 7000.0
    SP500_NARANJA_THRESHOLD = 6800.0
    VIX_DORMANT_THRESHOLD = 22.0


# Tickers considerados "explosivos" por NotebookLM 4 Prompt 5 (corrección + recovery vertical).
# Subset de DEFENSIVE_SECTORS que tienen beta alta + cobertura histórica de mover +30%/sem
# tras macro confirmation.
EXPLOSIVE_TICKERS = {
    "RKLB", "HOOD", "ASTS", "IONQ", "RGTI", "OKLO", "SMR", "UUUU",
    "CRWV", "IREN", "CORZ", "CIFR", "COIN", "MP",
}

# Sector clusters que se beneficiaron históricamente de BARRIDA_OPPORTUNITY (NotebookLM 4)
BARRIDA_CLUSTERS = {"ai_infra", "nuclear"}

# Archivo de estado persistente (sobrevive restart Railway)
_STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data",
    "macro_state.json"
)


def _ensure_state_dir():
    os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)


def get_current_macro_state(sp500_price: float, vix: float = 0.0) -> str:
    """Clasifica el régimen actual según SP500 + VIX.

    Returns:
        "VERDE_BULL"            — SP500 > 7000 + (VIX < 22 o sin info)
        "VERDE_BULL_DORMANT"    — SP500 > 7000 + VIX < 22 (barridas son oportunidad)
        "AMARILLA_INDECISA"     — SP500 entre 6800 y 7000
        "NARANJA_BEAR"          — SP500 < 6800
        "UNKNOWN"               — sin datos válidos
    """
    if not sp500_price or sp500_price <= 0:
        return "UNKNOWN"

    if sp500_price < SP500_NARANJA_THRESHOLD:
        return "NARANJA_BEAR"
    if sp500_price < SP500_VERDE_THRESHOLD:
        return "AMARILLA_INDECISA"
    # SP500 > 7000
    if vix > 0 and vix < VIX_DORMANT_THRESHOLD:
        return "VERDE_BULL_DORMANT"
    return "VERDE_BULL"


def _load_previous_state() -> dict:
    """Carga estado previo de macro_state.json."""
    if not os.path.exists(_STATE_FILE):
        return {}
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"[regime_transitions] load state failed: {e}")
        return {}


def _save_current_state(state: dict):
    """Persiste estado actual + previous."""
    _ensure_state_dir()
    try:
        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"[regime_transitions] save state failed: {e}")


def detect_transition(sp500_price: float, vix: float = 0.0) -> dict:
    """Detecta transición de régimen desde la última invocación.

    Returns dict:
        {
            "current": str,         # régimen actual
            "previous": str | None, # régimen previo (None si primera vez)
            "transition": str | None, # tipo transición (e.g. "AMARILLA_TO_VERDE") o None
            "is_bullish_transition": bool,  # AMARILLA → VERDE (EXPLOSIVE_CORRECTION trigger)
            "is_bearish_transition": bool,  # VERDE → AMARILLA o AMARILLA → NARANJA
            "since_ts": int,        # unix timestamp del cambio (o última grabación)
        }
    """
    current = get_current_macro_state(sp500_price, vix)
    prev_state = _load_previous_state()
    previous = prev_state.get("current")
    since_ts = prev_state.get("since_ts", int(time.time()))

    transition = None
    is_bullish_transition = False
    is_bearish_transition = False

    if previous and previous != current:
        transition = f"{previous}_TO_{current}"

        # Bullish: regresar a VERDE desde estados inferiores
        if previous in ("AMARILLA_INDECISA", "NARANJA_BEAR") and current.startswith("VERDE"):
            is_bullish_transition = True

        # Bearish: degradación
        if previous.startswith("VERDE") and current in ("AMARILLA_INDECISA", "NARANJA_BEAR"):
            is_bearish_transition = True
        if previous == "AMARILLA_INDECISA" and current == "NARANJA_BEAR":
            is_bearish_transition = True

        since_ts = int(time.time())
        logger.info(f"[regime_transitions] {transition} detectado (SP500=${sp500_price:.2f}, VIX={vix:.1f})")

    # Persistir
    _save_current_state({
        "current": current,
        "previous": previous,
        "since_ts": since_ts,
        "last_check_ts": int(time.time()),
        "sp500_price": sp500_price,
        "vix": vix,
    })

    return {
        "current": current,
        "previous": previous,
        "transition": transition,
        "is_bullish_transition": is_bullish_transition,
        "is_bearish_transition": is_bearish_transition,
        "since_ts": since_ts,
    }


def is_explosive_correction_setup(ticker: str, sp500_price: float, vix: float = 0.0) -> bool:
    """True si EXPLOSIVE_CORRECTION está activo para este ticker.

    Conditions:
        1. Macro transitioned bullish recently (AMARILLA → VERDE o similar)
        2. Ticker está en EXPLOSIVE_TICKERS set
        3. Transición es reciente (<24h desde el cambio)

    Llamado desde stock_analyzer / strategies para boost score.
    """
    if ticker.upper() not in EXPLOSIVE_TICKERS:
        return False

    t = detect_transition(sp500_price, vix)
    if not t["is_bullish_transition"]:
        return False

    # Solo "fresco" — <24h desde transition
    age_seconds = int(time.time()) - t["since_ts"]
    return age_seconds < 86400


def is_barrida_opportunity(symbol_cluster: Optional[str], sp500_price: float, vix: float = 0.0,
                          intraday_drop_pct: float = 0.0) -> bool:
    """True si BARRIDA_OPPORTUNITY conditions match.

    NotebookLM 4 Prompt 5: en VERDE_BULL_DORMANT (VIX<22 + SP500>7000), caídas
    intradía en clusters ai_infra/nuclear son re-entradas, no breaks.

    Args:
        symbol_cluster: e.g. "ai_infra" o "nuclear" (None = no aplica)
        sp500_price: precio actual SP500
        vix: VIX actual
        intraday_drop_pct: % de caída intradía (positivo = caída, ej 3.5 = -3.5%)

    Returns:
        True si conditions activas (caller decide no filtrar/no skip).
    """
    if symbol_cluster not in BARRIDA_CLUSTERS:
        return False
    if sp500_price < SP500_VERDE_THRESHOLD:
        return False
    if vix <= 0 or vix >= VIX_DORMANT_THRESHOLD:
        return False
    if intraday_drop_pct < 2.0:  # Mínimo 2% caída para considerar "barrida"
        return False
    return True


def get_state_summary() -> dict:
    """Helper para dashboard/telemetría: estado actual + transition history."""
    state = _load_previous_state()
    if not state:
        return {"status": "no_data"}
    return {
        "current_regime": state.get("current"),
        "previous_regime": state.get("previous"),
        "since_ts": state.get("since_ts"),
        "since_iso": datetime.fromtimestamp(state.get("since_ts", 0)).isoformat() if state.get("since_ts") else None,
        "last_check_iso": datetime.fromtimestamp(state.get("last_check_ts", 0)).isoformat() if state.get("last_check_ts") else None,
        "sp500_price": state.get("sp500_price"),
        "vix": state.get("vix"),
    }
