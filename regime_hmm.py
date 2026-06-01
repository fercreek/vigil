"""
regime_hmm.py — Spec 009 · HMM Regime Classifier (Salmos semáforo maestro)

Hidden Markov Model 3-state sobre features OHLCV (log returns, volatilidad rolling,
high-low range pct). Mapea estados latentes a regímenes operativos:

    STRONG_TREND    — state con mayor mean return (impulso alcista/bajista limpio)
    RANGE           — state con mean return intermedio (lateralización)
    VOLATILE_SQUEEZE — state con menor mean return / mayor volatilidad (squeeze, chop)

Justificación (NotebookLM 4 Prompt 4):
- HMM ganó vs Random Forest / SVM / LSTM puro para detección de régimen.
- NHHMM tiene RMSE volatilidad 0.015.
- Bot deja de predecir precio → predice condición de mercado.
- V3-Reversal debería bloquearse en STRONG_TREND (reversiones fallan en trending).
- SCALPER debería preferir RANGE.

Hooks pendientes (Spec 009.5):
- strategies.py:V3-REVERSAL gate por regime != STRONG_TREND
- gemini_analyzer.py:FOMC_CONTEXT inyectar regime actual a Salmos
"""

from __future__ import annotations

import time
import numpy as np
import pandas as pd

try:
    from hmmlearn.hmm import GaussianHMM
    _HMMLEARN_AVAILABLE = True
except ImportError:
    _HMMLEARN_AVAILABLE = False
    GaussianHMM = None  # type: ignore

# Spec 023.5 (2026-05-26): yfinance lazy import para stocks regime detection.
# Bot principal corre en Railway con yfinance instalado; dev local puede no tenerlo.
try:
    import yfinance as _yf  # type: ignore
    _YFINANCE_AVAILABLE = True
except ImportError:
    _YFINANCE_AVAILABLE = False
    _yf = None  # type: ignore


REGIME_LABELS = ("STRONG_TREND", "RANGE", "VOLATILE_SQUEEZE")

# Spec 009.6 (2026-05-26): TTL cache para detect_regime.
# HMM fit toma 100-500ms. Spec 017.5 llama 4x por símbolo por ciclo (sin cache = ~2s/sym).
# Cache 15min: 1 fit/15min/sym/tf. Significantes savings cuando bot loop corre c/5-10min.
_CACHE: dict = {}
HMM_CACHE_TTL = 900  # 15 min en segundos


def _cache_get(key: tuple) -> dict | None:
    entry = _CACHE.get(key)
    if entry is None:
        return None
    if time.time() - entry["ts"] > HMM_CACHE_TTL:
        del _CACHE[key]
        return None
    return entry["data"]


def _cache_set(key: tuple, data: dict):
    _CACHE[key] = {"ts": time.time(), "data": data}
    # Cleanup: max 64 entries (LRU-ish via oldest ts eviction)
    if len(_CACHE) > 64:
        oldest = sorted(_CACHE.items(), key=lambda x: x[1]["ts"])[:8]
        for k, _ in oldest:
            del _CACHE[k]


def _build_features(df: pd.DataFrame) -> np.ndarray | None:
    """Construye matriz de features (N, 3) desde OHLCV:
        col 0: log returns
        col 1: rolling std de returns (window=10)
        col 2: (high - low) / close — range pct
    Filtra NaN. Retorna None si features insuficientes.
    """
    try:
        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)

        log_ret = np.log(close / close.shift(1))
        vol = log_ret.rolling(window=10).std()
        rng_pct = (high - low) / close

        feat = pd.concat([log_ret, vol, rng_pct], axis=1)
        feat.columns = ["log_ret", "vol", "rng_pct"]
        feat = feat.dropna()

        if len(feat) < 30:
            return None

        return feat.values
    except Exception as e:
        print(f"[HMM FEATURES ERROR] {e}")
        return None


def _map_states_to_regimes(model: "GaussianHMM", features: np.ndarray, states: np.ndarray) -> dict:
    """Mapea state indices (0..n-1) a labels de régimen por mean return.

    - State con mayor mean log_ret (col 0) → STRONG_TREND
    - State con menor mean log_ret O mayor mean vol (col 1) → VOLATILE_SQUEEZE
    - El restante → RANGE

    Retorna dict {state_idx: regime_label}.
    """
    n_states = model.n_components
    # mean log return por estado
    log_ret_by_state = {}
    vol_by_state = {}
    for s in range(n_states):
        mask = states == s
        if mask.sum() == 0:
            log_ret_by_state[s] = 0.0
            vol_by_state[s] = 0.0
        else:
            log_ret_by_state[s] = float(features[mask, 0].mean())
            vol_by_state[s] = float(features[mask, 1].mean())

    # state con mayor return → STRONG_TREND
    trend_state = max(log_ret_by_state, key=lambda k: log_ret_by_state[k])
    # state con mayor volatilidad (excluido trend) → VOLATILE_SQUEEZE
    candidates_vol = {k: v for k, v in vol_by_state.items() if k != trend_state}
    if candidates_vol:
        squeeze_state = max(candidates_vol, key=lambda k: candidates_vol[k])
    else:
        squeeze_state = trend_state  # fallback degenerate

    mapping = {}
    for s in range(n_states):
        if s == trend_state:
            mapping[s] = "STRONG_TREND"
        elif s == squeeze_state:
            mapping[s] = "VOLATILE_SQUEEZE"
        else:
            mapping[s] = "RANGE"
    return mapping


def _yf_interval_period(timeframe: str, lookback: int) -> tuple[str, str]:
    """Mapea timeframe ccxt + lookback a (interval, period) yfinance.

    yfinance limits:
        - intervals "1m"/"2m"/"5m"/"15m"/"30m"/"60m"/"1h"/"1d"/"1wk"/"1mo"
        - "1h"/"60m": max 730 días history
        - "1d": sin límite real
    Para HMM stocks usamos típicamente "1h" + lookback 100 candles ≈ 14 trading days.
    """
    tf_map = {
        "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
        "1h": "1h", "60m": "1h", "4h": "1h",  # 4h no soportado nativo, usar 1h
        "1d": "1d", "1day": "1d", "1w": "1wk", "1wk": "1wk",
    }
    interval = tf_map.get(timeframe, "1h")

    # period must cover lookback candles. trading hours: ~6.5h/day NYSE.
    if interval in ("1m", "5m", "15m", "30m"):
        # intraday short: usar días
        days_needed = max(2, lookback // 13 + 2)  # ~13 candles intraday/day a 30m
        period = f"{min(days_needed, 60)}d"
    elif interval == "1h":
        # ~7 candles/day stocks NYSE → lookback 100 ≈ 15 días
        days_needed = max(5, lookback // 6 + 5)
        period = f"{min(days_needed, 730)}d"
    elif interval == "1d":
        days_needed = max(30, lookback + 10)
        period = f"{min(days_needed, 3650)}d"
    else:
        period = "60d"
    return interval, period


def _fetch_ohlcv_stock(ticker: str, timeframe: str = "1h", lookback_candles: int = 200) -> pd.DataFrame | None:
    """Spec 023.5: descarga OHLCV stock vía yfinance, retorna DataFrame columnas
    open/high/low/close/volume normalizadas (lowercase, mismo schema que indicators.get_df).

    Returns None si falla o data insuficiente.
    """
    if not _YFINANCE_AVAILABLE:
        print(f"[HMM YFINANCE] yfinance no instalado — skip stock regime para {ticker}")
        return None
    try:
        interval, period = _yf_interval_period(timeframe, lookback_candles)
        hist = _yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
        if hist is None or hist.empty:
            print(f"[HMM YFINANCE] history vacía para {ticker}/{interval}/{period}")
            return None
        # Normalizar columnas a lowercase para matchar indicators.get_df schema
        df = hist.rename(columns={
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume",
        })
        cols_needed = ["open", "high", "low", "close", "volume"]
        missing = [c for c in cols_needed if c not in df.columns]
        if missing:
            print(f"[HMM YFINANCE] columnas faltantes {missing} para {ticker}")
            return None
        df = df[cols_needed].dropna()
        if len(df) < 50:
            print(f"[HMM YFINANCE] data insuficiente {len(df)} candles para {ticker}")
            return None
        return df
    except Exception as e:
        print(f"[HMM YFINANCE ERROR] {ticker}/{timeframe}: {e}")
        return None


def detect_regime(symbol: str, timeframe: str = "1h", lookback: int = 200) -> dict:
    """Detecta régimen actual via HMM 3-state sobre OHLCV.

    Spec 023.5 (2026-05-26): symbol routing:
        - Si contiene "/" → cripto vía indicators.get_df (ccxt Binance)
        - Si NO contiene "/" → stock vía _fetch_ohlcv_stock (yfinance)

    Args:
        symbol: e.g. "BTC/USDT" (cripto) o "NVDA" (stock)
        timeframe: e.g. "1h" (default)
        lookback: candles a usar para entrenar HMM (default 200; stocks suele usar 100)

    Returns:
        {
            "regime": "STRONG_TREND" | "RANGE" | "VOLATILE_SQUEEZE",
            "confidence": float 0-1,
            "current_state": int 0-2,
            "training_loss": float | None,  # log-likelihood del fit
            "regime_history_last_10": list[str],
        }
        Empty dict {} si falla (caller decide fallback — e.g. no filtrar).
    """
    if not _HMMLEARN_AVAILABLE:
        print("[HMM ERROR] hmmlearn no instalado. pip install hmmlearn>=0.3.0")
        return {}

    # Spec 009.6: cache TTL 15min por (symbol, timeframe, lookback)
    _key = (symbol, timeframe, lookback)
    _cached = _cache_get(_key)
    if _cached is not None:
        return _cached

    try:
        # Spec 023.5 + fix 2026-06-01: branch source por cripto-detección robusta.
        # "ZEC/USDT" → crypto. "ZEC" (bare) también si está en config.SYMBOLS (cripto monitoreada).
        # Antes: bare "ZEC" caía a yfinance → history vacía → régimen UNKNOWN.
        base = symbol.split("/")[0].upper()
        is_crypto = "/" in symbol
        if not is_crypto:
            try:
                import config
                if base in getattr(config, "SYMBOLS", []):
                    is_crypto = True
            except Exception:
                pass

        if is_crypto:
            # Lazy import para que el módulo sea importable sin ccxt local.
            # get_df espera symbol BARE (construye {base}/USDT vía fallback OKX→…→Binance).
            from indicators import get_df
            # Pedimos lookback+50 para tener margen tras dropna de features
            df = get_df(base, timeframe=timeframe, limit=lookback + 50)
        else:
            # Stock vía yfinance
            df = _fetch_ohlcv_stock(symbol, timeframe=timeframe, lookback_candles=lookback + 50)

        if df is None or df.empty or len(df) < 50:
            print(f"[HMM ERROR] DataFrame insuficiente para {symbol}/{timeframe}")
            return {}

        features = _build_features(df)
        if features is None:
            print(f"[HMM ERROR] Features insuficientes para {symbol}/{timeframe}")
            return {}

        # Recortar a lookback más reciente
        if len(features) > lookback:
            features = features[-lookback:]

        # Entrenar HMM 3-state
        try:
            model = GaussianHMM(
                n_components=3,
                covariance_type="diag",
                n_iter=100,
                random_state=42,
            )
            model.fit(features)
        except Exception as fit_err:
            print(f"[HMM FIT ERROR] {symbol}/{timeframe}: {fit_err}")
            return {}

        # Predict states + posteriors
        try:
            states = model.predict(features)
            posteriors = model.predict_proba(features)
            training_loss = float(model.score(features))  # log-likelihood
        except Exception as pred_err:
            print(f"[HMM PREDICT ERROR] {symbol}/{timeframe}: {pred_err}")
            return {}

        # Mapeo state → regime
        mapping = _map_states_to_regimes(model, features, states)

        current_state = int(states[-1])
        current_regime = mapping[current_state]
        confidence = float(posteriors[-1, current_state])

        # Historia últimos 10
        history = [mapping[int(s)] for s in states[-10:]]

        result = {
            "regime": current_regime,
            "confidence": confidence,
            "current_state": current_state,
            "training_loss": training_loss,
            "regime_history_last_10": history,
        }
        # Spec 009.6: cachear resultado exitoso
        _cache_set(_key, result)
        return result

    except Exception as e:
        print(f"[HMM ERROR] {symbol}/{timeframe}: {e}")
        return {}
