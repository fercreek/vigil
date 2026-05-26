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


def detect_regime(symbol: str, timeframe: str = "1h", lookback: int = 200) -> dict:
    """Detecta régimen actual via HMM 3-state sobre OHLCV.

    Args:
        symbol: e.g. "BTC/USDT"
        timeframe: e.g. "1h" (default)
        lookback: candles a usar para entrenar HMM (default 200)

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
        # Lazy import para que el módulo sea importable sin ccxt local
        from indicators import get_df

        # Pedimos lookback+50 para tener margen tras dropna de features
        df = get_df(symbol, timeframe=timeframe, limit=lookback + 50)
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
