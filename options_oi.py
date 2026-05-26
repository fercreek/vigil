"""
options_oi.py — Spec 023.6 · Options Open Interest Volume Profile (stocks)

Proxy de positioning institucional via yfinance options chain. Agrega Open Interest
(OI) de calls vs puts a través de las primeras N expirations. El ratio call/put OI
es señal de sesgo institucional / dark pool (PTS metodologia: institucionales
acumulan options antes de moves grandes).

Justificación (NotebookLM 4 backlog Spec 023.6):
- Stocks no tienen tape público comparable a Binance trades (CVD segmented cripto).
- yfinance expone options chain con OI por strike por expiration.
- Sum calls OI vs puts OI por expiration → proxy positioning institucional.
- Wire como tag stock_analyzer ENTRY_ALERT: `📈 Options OI: CALL_HEAVY (ratio 2.3x)`
- Complementa cuádruple confluencia: Priority + Social + EXPLOSIVE + HMM + Options OI.

Patrón cache TTL 30min — mismo que cvd_segmented y otros módulos institucionales.
Lazy import yfinance con flag, graceful degradation sin la lib (dev local).

Signal classification:
    CALL_HEAVY    — ratio >= 2.0  (calls 2x+ puts = bullish positioning)
    PUT_HEAVY     — ratio <= 0.5  (puts 2x+ calls = bearish hedging)
    BALANCED      — entre 0.5 y 2.0 (no edge, no tag emitido por caller)
"""

from __future__ import annotations

import time
from typing import Optional

# Spec 023.6 (2026-05-26): yfinance lazy import — mismo pattern Spec 023.5.
# Bot principal corre en Railway con yfinance instalado; dev local puede no tenerlo.
try:
    import yfinance as _yf  # type: ignore
    _YFINANCE_AVAILABLE = True
except ImportError:
    _YFINANCE_AVAILABLE = False
    _yf = None  # type: ignore


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

# Thresholds de signal classification.
# Ratio = total_call_oi / max(total_put_oi, 1)
CALL_HEAVY_THRESHOLD = 2.0   # calls 2x más que puts = sesgo bullish
PUT_HEAVY_THRESHOLD = 0.5    # puts 2x más que calls = sesgo bearish (1/2 = 0.5)

# Cache TTL — OI no cambia tan rápido (positioning institucional acumula días).
# 30min razonable: stock_watchdog corre ~1x/min, esto significa 1 fetch/30min/ticker.
# ~16 stocks watchlist × 2 fetch/h = 32 calls/h — bien debajo del Yahoo limit.
OI_CACHE_TTL = 1800  # 30 min en segundos


# ═══════════════════════════════════════════════════════════════════════════════
# CACHE (module-level — patrón regime_hmm + cvd_segmented)
# ═══════════════════════════════════════════════════════════════════════════════

_CACHE: dict = {}
_CACHE_MAX_ENTRIES = 32


def _cache_get(key: tuple) -> Optional[dict]:
    entry = _CACHE.get(key)
    if entry is None:
        return None
    if time.time() - entry["ts"] > OI_CACHE_TTL:
        del _CACHE[key]
        return None
    return entry["data"]


def _cache_set(key: tuple, data: dict):
    _CACHE[key] = {"ts": time.time(), "data": data}
    # Cleanup: max 32 entries (LRU-ish via oldest ts eviction).
    if len(_CACHE) > _CACHE_MAX_ENTRIES:
        oldest = sorted(_CACHE.items(), key=lambda x: x[1]["ts"])[:4]
        for k, _ in oldest:
            del _CACHE[k]


# ═══════════════════════════════════════════════════════════════════════════════
# SIGNAL CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

def _classify_signal(call_put_ratio: float) -> str:
    """Mapea ratio a label discreto.

    >>> _classify_signal(2.5)
    'CALL_HEAVY'
    >>> _classify_signal(0.4)
    'PUT_HEAVY'
    >>> _classify_signal(1.2)
    'BALANCED'
    """
    if call_put_ratio >= CALL_HEAVY_THRESHOLD:
        return "CALL_HEAVY"
    if call_put_ratio <= PUT_HEAVY_THRESHOLD:
        return "PUT_HEAVY"
    return "BALANCED"


# ═══════════════════════════════════════════════════════════════════════════════
# CORE API
# ═══════════════════════════════════════════════════════════════════════════════

def get_options_oi_ratio(ticker: str, expirations_lookback: int = 2) -> dict:
    """Calcula ratio total call OI / total put OI sobre las primeras N expirations.

    Args:
        ticker: stock ticker e.g. "NVDA", "TSLA", "OKLO"
        expirations_lookback: cuántas expirations cercanas agregar (default 2)

    Returns:
        {
            "ticker": str,
            "total_call_oi": int,
            "total_put_oi": int,
            "call_put_ratio": float,        # total_call_oi / max(total_put_oi, 1)
            "signal": "CALL_HEAVY" | "PUT_HEAVY" | "BALANCED",
            "expirations_analyzed": list[str],   # fechas YYYY-MM-DD
            "last_update_ts": int,           # unix seconds
        }
        Empty dict {} si falla (caller decide fallback — e.g. no tag).
    """
    if not _YFINANCE_AVAILABLE:
        print(f"[OPTIONS_OI] yfinance no instalado — skip {ticker}")
        return {}

    ticker_upper = ticker.upper()
    cache_key = (ticker_upper, expirations_lookback)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        tk = _yf.Ticker(ticker_upper)
        # yfinance .options retorna tupla de fechas string YYYY-MM-DD
        try:
            available_expirations = tk.options
        except Exception as e:
            print(f"[OPTIONS_OI] {ticker_upper}: no options chain disponible ({e})")
            return {}

        if not available_expirations:
            print(f"[OPTIONS_OI] {ticker_upper}: lista de expirations vacía")
            return {}

        # Tomar las primeras N (más cercanas en tiempo)
        target_exps = list(available_expirations[:expirations_lookback])

        total_call_oi = 0
        total_put_oi = 0
        exps_processed = []

        for exp_date in target_exps:
            try:
                chain = tk.option_chain(exp_date)
            except Exception as e:
                print(f"[OPTIONS_OI] {ticker_upper}/{exp_date}: chain fetch failed ({e})")
                continue

            # chain.calls / chain.puts son DataFrames con cols incluyendo openInterest
            try:
                calls_df = getattr(chain, "calls", None)
                puts_df = getattr(chain, "puts", None)

                if calls_df is not None and "openInterest" in calls_df.columns:
                    # fillna(0) por strikes nuevos sin OI
                    call_oi = int(calls_df["openInterest"].fillna(0).sum())
                    total_call_oi += call_oi

                if puts_df is not None and "openInterest" in puts_df.columns:
                    put_oi = int(puts_df["openInterest"].fillna(0).sum())
                    total_put_oi += put_oi

                exps_processed.append(exp_date)
            except Exception as e:
                print(f"[OPTIONS_OI] {ticker_upper}/{exp_date}: parse error ({e})")
                continue

        if not exps_processed:
            print(f"[OPTIONS_OI] {ticker_upper}: ninguna expiration procesada")
            return {}

        # Ratio con guard contra div by zero
        call_put_ratio = total_call_oi / max(total_put_oi, 1)
        signal = _classify_signal(call_put_ratio)

        result = {
            "ticker": ticker_upper,
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
            "call_put_ratio": float(call_put_ratio),
            "signal": signal,
            "expirations_analyzed": exps_processed,
            "last_update_ts": int(time.time()),
        }

        _cache_set(cache_key, result)
        return result

    except Exception as e:
        print(f"[OPTIONS_OI ERROR] {ticker_upper}: {e}")
        return {}
