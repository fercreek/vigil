"""
social_quant.py — Spec 013 · Social Sentiment Quant (voz Exodo narrativa)

Cuantifica sentimiento Reddit + Google Trends para anticipar cambios de régimen
irracionales antes de que el precio reaccione. Voz Exodo (narrativa) en la
Cuadrilla Zenith de gemini_analyzer.py — pendiente Spec 013.5.

Origen:
- NotebookLM 4 Prompt 1 strategy #3 — Social sentiment quant
- NotebookLM 4 Prompt 6 Spec 014 — Reddit + Trends señal de euphoria/fear
- WR esperado: +6-7pp sobre baseline cuando se confirma euphoria/fear

Diseño:
- Cache 30min (praw/pytrends son lentos: 2-5s cada uno)
- Empty dict {} en cualquier fallo → caller decide fallback
- Graceful degradation: si praw/pytrends/vader ausentes → empty dict + log
- Reddit auth vía env vars (NO hardcoded credentials)
- VADER over transformer NLP: 10x más rápido, suficiente para títulos de Reddit
  (transformers requieren ~500MB descarga + GPU para latencia razonable)

Hooks pendientes (Spec 013.5):
- Inyectar `signal` a voz Exodo en gemini_analyzer.py:get_ai_consensus
- Gate de tamaño en strategies.py: EUPHORIA → reducir posición 50% (contrarian)
- Comando Telegram /social SYMBOL para inspect manual
"""

from __future__ import annotations

import os
import time
from typing import Optional

# ── Graceful import flags ─────────────────────────────────────────────────────
try:
    import praw  # type: ignore
    _PRAW_AVAILABLE = True
except ImportError:
    _PRAW_AVAILABLE = False
    praw = None  # type: ignore

try:
    from pytrends.request import TrendReq  # type: ignore
    _PYTRENDS_AVAILABLE = True
except ImportError:
    _PYTRENDS_AVAILABLE = False
    TrendReq = None  # type: ignore

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # type: ignore
    _VADER_AVAILABLE = True
except ImportError:
    _VADER_AVAILABLE = False
    SentimentIntensityAnalyzer = None  # type: ignore


# ── Constants (documented in module, NOT config.py) ───────────────────────────
SOCIAL_EUPHORIA_THRESHOLD = 0.5       # reddit_compound > 0.5 + trends_delta > 30% → EUPHORIA
SOCIAL_FEAR_THRESHOLD = -0.3          # reddit_compound < -0.3 + trends_delta > 30% → FEAR
SOCIAL_TRENDS_DELTA_THRESHOLD = 30.0  # % delta last hour vs prior hours
SOCIAL_CACHE_TTL = 1800               # 30min — praw/pytrends son lentos

# ── Subreddits per symbol ─────────────────────────────────────────────────────
# Default fallback usa los crypto generalistas + wallstreetbets para retail euphoria
_DEFAULT_SUBREDDITS = ["CryptoCurrency", "Bitcoin", "ethereum", "wallstreetbets"]

_SUBREDDITS_BY_SYMBOL: dict[str, list[str]] = {
    # Cripto
    "BTC":  ["CryptoCurrency", "Bitcoin", "wallstreetbets"],
    "ETH":  ["CryptoCurrency", "ethereum", "wallstreetbets"],
    "SOL":  ["CryptoCurrency", "solana", "wallstreetbets"],
    "TAO":  ["TaoBittensor"],
    "ZEC":  ["zec"],
    # Spec 023 (2026-05-26): stocks NYSE/NASDAQ — usar wallstreetbets + stocks generalistas
    "NVDA": ["wallstreetbets", "stocks", "investing"],
    "TSLA": ["wallstreetbets", "stocks", "teslainvestorsclub"],
    "PLTR": ["wallstreetbets", "PLTR", "stocks"],
    "SIL":  ["wallstreetbets", "Wallstreetsilver"],
    "HOOD": ["wallstreetbets", "stocks"],
    "COIN": ["wallstreetbets", "CryptoCurrency", "stocks"],
    "RKLB": ["wallstreetbets", "RocketLab", "SpaceXMasterrace"],
    "XBI":  ["wallstreetbets", "biotech_stocks"],
    "OKLO": ["wallstreetbets", "nuclear", "stocks"],
    "SMR":  ["wallstreetbets", "nuclear", "stocks"],
    "UUUU": ["wallstreetbets", "uraniumsqueeze"],
    "IONQ": ["wallstreetbets", "stocks"],
    "MP":   ["wallstreetbets", "stocks"],
    "SOFI": ["wallstreetbets", "sofi_stock"],
    "CRWV": ["wallstreetbets", "stocks"],
    "IREN": ["wallstreetbets", "stocks", "CryptoCurrency"],
}

_REDDIT_POSTS_PER_SUB = 10           # limit per subreddit
_VADER_TEXT_TRUNCATE = 500           # selftext truncated to first 500 chars

# ── Module-level cache ────────────────────────────────────────────────────────
# Pattern same as market_intel._CACHE
_CACHE: dict[str, dict] = {}  # {symbol: {"data": {...}, "last_update": float}}

# ── VADER analyzer singleton (init lazily) ────────────────────────────────────
_vader_analyzer: Optional["SentimentIntensityAnalyzer"] = None


def _get_vader() -> Optional["SentimentIntensityAnalyzer"]:
    """Lazy init de VADER analyzer. None si VADER no disponible."""
    global _vader_analyzer
    if not _VADER_AVAILABLE:
        return None
    if _vader_analyzer is None:
        try:
            _vader_analyzer = SentimentIntensityAnalyzer()
        except Exception as e:
            print(f"[SOCIAL VADER INIT ERROR] {e}")
            return None
    return _vader_analyzer


def _get_reddit_client():
    """Build praw.Reddit client from env vars. Returns None if missing creds."""
    if not _PRAW_AVAILABLE:
        return None

    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "scalp_bot/0.1")

    if not client_id or not client_secret:
        print("[SOCIAL] REDDIT_CLIENT_ID/SECRET no configurados — Reddit skip")
        return None

    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            check_for_async=False,
        )
        # Read-only mode (no user auth needed)
        reddit.read_only = True
        return reddit
    except Exception as e:
        print(f"[SOCIAL REDDIT INIT ERROR] {e}")
        return None


def _scan_reddit(symbol: str, lookback_hours: int) -> dict:
    """Scan subreddits relevantes para `symbol`. Returns dict con:
        {
            "compound": float (avg VADER compound),
            "post_count": int,
            "top_3_titles": list[str],
        }
    Empty dict on failure.
    """
    reddit = _get_reddit_client()
    if reddit is None:
        return {}

    vader = _get_vader()
    if vader is None:
        return {}

    subreddits = _SUBREDDITS_BY_SYMBOL.get(symbol.upper(), _DEFAULT_SUBREDDITS)
    cutoff_ts = time.time() - (lookback_hours * 3600)

    all_compounds: list[float] = []
    sample_posts: list[tuple[float, str]] = []  # (created_utc, title)
    symbol_lower = symbol.lower()

    try:
        for sub_name in subreddits:
            try:
                sub = reddit.subreddit(sub_name)
                # Use .new() para sort por tiempo (más reciente primero)
                for post in sub.new(limit=_REDDIT_POSTS_PER_SUB):
                    if post.created_utc < cutoff_ts:
                        continue

                    title = post.title or ""
                    selftext = (post.selftext or "")[:_VADER_TEXT_TRUNCATE]

                    # Filtrar por mención del símbolo (excepto subreddits dedicados)
                    is_dedicated = sub_name.lower() in (
                        "taobittensor", "zec", "bitcoin", "ethereum", "solana"
                    )
                    text_lower = (title + " " + selftext).lower()
                    if not is_dedicated and symbol_lower not in text_lower:
                        continue

                    combined = f"{title}. {selftext}".strip()
                    if not combined:
                        continue

                    try:
                        scores = vader.polarity_scores(combined)
                        compound = float(scores.get("compound", 0.0))
                    except Exception as v_err:
                        print(f"[SOCIAL VADER ERROR] {v_err}")
                        continue

                    all_compounds.append(compound)
                    sample_posts.append((post.created_utc, title))
            except Exception as sub_err:
                print(f"[SOCIAL REDDIT SUB ERROR] r/{sub_name}: {sub_err}")
                continue
    except Exception as e:
        print(f"[SOCIAL REDDIT SCAN ERROR] {symbol}: {e}")
        return {}

    if not all_compounds:
        return {
            "compound": 0.0,
            "post_count": 0,
            "top_3_titles": [],
        }

    # Top 3 = más recientes (sample_posts ordenado por created_utc desc)
    sample_posts.sort(key=lambda x: x[0], reverse=True)
    top_3 = [t for _, t in sample_posts[:3]]

    avg_compound = sum(all_compounds) / len(all_compounds)
    return {
        "compound": float(avg_compound),
        "post_count": len(all_compounds),
        "top_3_titles": top_3,
    }


def _scan_google_trends(symbol: str) -> dict:
    """Scan Google Trends for `symbol` over last 1 day.
    Returns:
        {
            "score": int 0-100 (interest_over_time del último período),
            "delta": float (% change vs prior period),
        }
    Empty dict on failure.
    """
    if not _PYTRENDS_AVAILABLE:
        return {}

    try:
        # hl=en-US, tz=0 UTC — pytrends defaults razonables
        pytrends = TrendReq(hl="en-US", tz=0, timeout=(5, 15))
        pytrends.build_payload([symbol], timeframe="now 1-d")
        df = pytrends.interest_over_time()

        if df is None or df.empty or symbol not in df.columns:
            return {}

        # df indexed by datetime; valores 0-100
        series = df[symbol].astype(float)
        if len(series) < 4:
            return {}

        # Split: last hour avg vs prior periods avg
        # "now 1-d" devuelve ~24 puntos (cada 8min) o así
        # Tomamos último quartil vs primeros 3 quartiles
        split_idx = max(1, int(len(series) * 0.75))
        prior = series.iloc[:split_idx]
        recent = series.iloc[split_idx:]

        recent_avg = float(recent.mean())
        prior_avg = float(prior.mean())

        if prior_avg <= 0:
            # Avoid div by zero — si previo era 0, cualquier interés actual es "infinito"
            delta_pct = 100.0 if recent_avg > 0 else 0.0
        else:
            delta_pct = ((recent_avg - prior_avg) / prior_avg) * 100.0

        return {
            "score": int(round(recent_avg)),
            "delta": float(delta_pct),
        }
    except Exception as e:
        print(f"[SOCIAL TRENDS ERROR] {symbol}: {e}")
        return {}


def _classify_signal(reddit_compound: float, trends_delta: float) -> str:
    """Classify EUPHORIA / FEAR / NEUTRAL desde sentiment + attention spike."""
    if trends_delta > SOCIAL_TRENDS_DELTA_THRESHOLD:
        if reddit_compound > SOCIAL_EUPHORIA_THRESHOLD:
            return "EUPHORIA"
        if reddit_compound < SOCIAL_FEAR_THRESHOLD:
            return "FEAR"
    return "NEUTRAL"


def get_social_sentiment(symbol: str, lookback_hours: int = 24) -> dict:
    """Quantify Reddit + Google Trends sentiment for a crypto symbol.

    Args:
        symbol: e.g. "BTC", "ETH", "TAO", "ZEC". Sin "/USDT" suffix.
        lookback_hours: ventana Reddit (default 24h). Trends fijo "now 1-d".

    Returns dict:
        {
            "symbol": str,
            "lookback_hours": int,
            "reddit_compound": float,        # avg VADER compound -1..1
            "reddit_post_count": int,
            "reddit_top_3_titles": list[str],
            "google_trends_score": int,      # 0-100
            "google_trends_delta": float,    # % vs prior period
            "signal": "EUPHORIA" | "FEAR" | "NEUTRAL",
            "last_update_ts": int,
        }
        Empty dict {} on failure (caller decide fallback).
    """
    # Graceful degradation: at least one of Reddit/Trends must work + VADER required
    if not _VADER_AVAILABLE:
        print("[SOCIAL] vaderSentiment no instalado — pip install vaderSentiment>=3.3.2")
        return {}
    if not _PRAW_AVAILABLE and not _PYTRENDS_AVAILABLE:
        print("[SOCIAL] praw + pytrends ambos ausentes — pip install praw pytrends")
        return {}

    sym_key = symbol.upper()
    cache_key = f"{sym_key}:{lookback_hours}"
    now = time.time()

    # Cache hit
    cached = _CACHE.get(cache_key)
    if cached and (now - cached.get("last_update", 0)) < SOCIAL_CACHE_TTL:
        return cached["data"]

    # Scan Reddit
    reddit_data = _scan_reddit(sym_key, lookback_hours) if _PRAW_AVAILABLE else {}
    reddit_compound = float(reddit_data.get("compound", 0.0))
    reddit_post_count = int(reddit_data.get("post_count", 0))
    reddit_top_3 = reddit_data.get("top_3_titles", [])

    # Scan Google Trends
    trends_data = _scan_google_trends(sym_key) if _PYTRENDS_AVAILABLE else {}
    trends_score = int(trends_data.get("score", 0))
    trends_delta = float(trends_data.get("delta", 0.0))

    # Si ambos vacíos → fallo total
    if not reddit_data and not trends_data:
        return {}

    signal = _classify_signal(reddit_compound, trends_delta)

    result = {
        "symbol": sym_key,
        "lookback_hours": int(lookback_hours),
        "reddit_compound": reddit_compound,
        "reddit_post_count": reddit_post_count,
        "reddit_top_3_titles": reddit_top_3,
        "google_trends_score": trends_score,
        "google_trends_delta": trends_delta,
        "signal": signal,
        "last_update_ts": int(now),
    }

    # Cache it
    _CACHE[cache_key] = {"data": result, "last_update": now}
    return result
