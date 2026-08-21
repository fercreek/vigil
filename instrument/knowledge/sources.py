"""knowledge/sources.py — fetchers for the fundamentals knowledge base.

Every fetcher takes an injectable `http_get(url) -> str` (like llm_note's
`client`): tests inject a stub, nothing touches the network. Each owns its
own valid_until -- a funding rate and a FOMC date are not stale on the same
clock. Returns FetchResult(ok, value, valid_until, source, error);
refresh.py cache.put()s only when ok=True.

A missing credential is ok=True with value={"available": False, "reason":
"missing_credential:X"} -- a completed check, never confused with "checked,
nothing new" (legacy config.py:340/348 hardcoded FOMC_NEXT_MEETING /
EARNINGS_CALENDAR and neither ever admitted "I no longer know this").
Exceptions are caught by TYPE, never `except Exception` (.limits.json's
ratchet is 4/4); FETCH_ERRORS below is the border instead.
"""
from __future__ import annotations

import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, NamedTuple
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

HttpGet = Callable[[str], str]

# Network failure (requests' hierarchy or a raw connection OSError), HTTP
# error status, or a malformed/short/wrong-shaped response.
FETCH_ERRORS = (
    requests.RequestException, OSError, ValueError, LookupError, TypeError,
    AttributeError, ET.ParseError,
)


class FetchResult(NamedTuple):
    ok: bool
    value: dict[str, Any] | None
    valid_until: str | None
    source: str
    error: str | None = None


def _default_http_get(url: str) -> str:
    response = requests.get(url, timeout=10, headers={"User-Agent": "vigil-instrument/1.0"})
    response.raise_for_status()
    return response.text


def _until(hours: float, now: datetime | None = None) -> str:
    return ((now or datetime.now(timezone.utc)) + timedelta(hours=hours)).isoformat()


def _failed(fetcher: str, exc: BaseException) -> FetchResult:
    logger.error("%s: fetch failed -- %s: %s", fetcher, type(exc).__name__, exc)
    return FetchResult(False, None, None, fetcher, f"{type(exc).__name__}: {exc}")


def _missing_credential(fetcher: str, env_var: str) -> FetchResult:
    logger.warning("%s: %s not set -- flagged, not skipped", fetcher, env_var)
    value = {"available": False, "reason": f"missing_credential:{env_var}"}
    return FetchResult(True, value, _until(24), f"{fetcher}:missing_credential")


def fetch_derivatives(symbol: str, http_get: HttpGet = _default_http_get,
                       now: datetime | None = None) -> FetchResult:
    """Binance Futures funding + open interest, no key. Settles every 8h -- 6h catches a stale read."""
    pair = f"{symbol.upper()}USDT"
    base = "https://fapi.binance.com/fapi/v1"
    try:
        premium = json.loads(http_get(f"{base}/premiumIndex?{urlencode({'symbol': pair})}"))
        oi = json.loads(http_get(f"{base}/openInterest?{urlencode({'symbol': pair})}"))
        value = {
            "available": True,
            "symbol": pair,
            "mark_price": float(premium["markPrice"]),
            "last_funding_rate": float(premium["lastFundingRate"]),
            "next_funding_time": premium["nextFundingTime"],
            "open_interest": float(oi["openInterest"]),
        }
    except FETCH_ERRORS as exc:
        return _failed("derivatives", exc)
    return FetchResult(True, value, _until(6, now), "binance_futures")


def fetch_fear_greed(http_get: HttpGet = _default_http_get, now: datetime | None = None) -> FetchResult:
    """alternative.me publishes once a day; 24h matches the source's own cadence."""
    try:
        payload = json.loads(http_get("https://api.alternative.me/fng/?limit=1"))
        point = payload["data"][0]
        value = {
            "available": True,
            "value": int(point["value"]),
            "classification": point["value_classification"],
            "as_of": point["timestamp"],
        }
    except FETCH_ERRORS as exc:
        return _failed("fear_greed", exc)
    return FetchResult(True, value, _until(24, now), "alternative.me")


def fetch_stablecoin_supply(http_get: HttpGet = _default_http_get,
                             now: datetime | None = None) -> FetchResult:
    """DefiLlama aggregate stablecoin supply, a liquidity proxy. Daily; 24h."""
    try:
        payload = json.loads(http_get("https://stablecoins.llama.fi/stablecoins?includePrices=false"))
        assets = payload["peggedAssets"]
        total = sum(a["circulating"].get("peggedUSD", 0) for a in assets if a.get("circulating"))
        prev = sum(a.get("circulatingPrevDay", {}).get("peggedUSD", 0)
                   for a in assets if a.get("circulatingPrevDay"))
        value = {
            "available": True,
            "total_usd": total,
            "change_1d_usd": (total - prev) if prev else None,
            "asset_count": len(assets),
        }
    except FETCH_ERRORS as exc:
        return _failed("stablecoin_supply", exc)
    return FetchResult(True, value, _until(24, now), "defillama")


_MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}
_YEAR_HEADER_RE = re.compile(r'id="\d+">(\d{4}) FOMC Meetings</a>')
_ENTRY_RE = re.compile(
    r'fomc-meeting__month[^"]*"><strong>([A-Za-z]+)</strong>.{0,400}?'
    r'fomc-meeting__date[^"]*">([^<]+)<', re.S)


def _parse_fomc_html(html: str, now: datetime) -> tuple[str, str] | None:
    """(iso_date, label) for the NEXT meeting, or None -- never a silent '0 upcoming'."""
    headers = list(_YEAR_HEADER_RE.finditer(html))
    dates: dict[datetime, str] = {}
    for idx, header in enumerate(headers):
        year = int(header.group(1))
        end = headers[idx + 1].start() if idx + 1 < len(headers) else len(html)
        for month_name, days in _ENTRY_RE.findall(html[header.end():end]):
            month = _MONTHS.get(month_name)
            digits = re.findall(r"\d+", days)
            if month is None or not digits:
                continue
            try:
                meeting_date = datetime(year, month, int(digits[-1]), 18, 0, tzinfo=timezone.utc)
            except ValueError:
                continue
            dates[meeting_date] = f"{month_name} {days.strip()}, {year}"
    upcoming = sorted(d for d in dates if d >= now)
    return (upcoming[0].isoformat(), dates[upcoming[0]]) if upcoming else None


def _fetch_fomc_from_fred(http_get: HttpGet, api_key: str, now: datetime) -> FetchResult:
    """release_id=101 is the FOMC Meeting Announcements release."""
    today = now.date().isoformat()
    params = urlencode({"release_id": 101, "api_key": api_key, "file_type": "json",
                         "sort_order": "asc", "realtime_start": today})
    try:
        payload = json.loads(http_get(f"https://api.stlouisfed.org/fred/releases/dates?{params}"))
        upcoming = next((d["date"] for d in payload["release_dates"] if d["date"] >= today), None)
    except FETCH_ERRORS as exc:
        return _failed("fomc_calendar", exc)
    if upcoming is None:
        return _failed("fomc_calendar", ValueError("FRED returned no future release date"))
    value = {"available": True, "next_meeting_date": upcoming, "label": upcoming}
    return FetchResult(True, value, upcoming, "fred_releases_dates")


def fetch_fomc_calendar(http_get: HttpGet = _default_http_get, now: datetime | None = None,
                         fred_api_key: str | None = None) -> FetchResult:
    """Next FOMC meeting date. FRED_API_KEY unset today -> SCRAPES HTML
    instead (fomccalendars.htm, confirmed present 2026-08-21) -- fragile by
    nature, not an API; a redesign becomes a logged failure via
    `_parse_fomc_html` returning None, never a wrong date. valid_until is
    the meeting's own date: the fix for config.py:340's FOMC_NEXT_MEETING
    sitting 24 days stale."""
    now = now or datetime.now(timezone.utc)
    fred_api_key = fred_api_key or os.getenv("FRED_API_KEY")
    if fred_api_key:
        return _fetch_fomc_from_fred(http_get, fred_api_key, now)
    fomc_url = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
    try:
        parsed = _parse_fomc_html(http_get(fomc_url), now)
    except FETCH_ERRORS as exc:
        return _failed("fomc_calendar", exc)
    if parsed is None:
        return _failed("fomc_calendar", ValueError("no meeting date matched in fomccalendars.htm"))
    iso_date, label = parsed
    value = {"available": True, "next_meeting_date": iso_date, "label": label}
    return FetchResult(True, value, iso_date, "fed_calendar_html")


def fetch_earnings(tickers: list[str], http_get: HttpGet = _default_http_get,
                    now: datetime | None = None, api_key: str | None = None) -> FetchResult:
    """Finnhub /calendar/earnings, one call per ticker (free tier takes a
    single `symbol`, not a list). 24h window, next 14 days."""
    api_key = api_key or os.getenv("FINNHUB_API_KEY")
    if not api_key:
        return _missing_credential("earnings", "FINNHUB_API_KEY")
    now = now or datetime.now(timezone.utc)
    start, end = now.date().isoformat(), (now + timedelta(days=14)).date().isoformat()
    results: dict[str, Any] = {}
    try:
        for ticker in tickers:
            params = urlencode({"symbol": ticker, "from": start, "to": end, "token": api_key})
            payload = json.loads(http_get(f"https://finnhub.io/api/v1/calendar/earnings?{params}"))
            results[ticker] = payload["earningsCalendar"]
    except FETCH_ERRORS as exc:
        return _failed("earnings", exc)
    value = {"available": True, "window": {"from": start, "to": end}, "by_ticker": results}
    return FetchResult(True, value, _until(24, now), "finnhub")


def _parse_rss(xml_text: str, limit: int = 10) -> list[dict[str, str]]:
    root = ET.fromstring(xml_text)
    return [
        {"title": (item.findtext("title") or "").strip(),
         "link": (item.findtext("link") or "").strip(),
         "pub_date": (item.findtext("pubDate") or "").strip()}
        for item in root.findall("./channel/item")[:limit]
    ]


def fetch_news(http_get: HttpGet = _default_http_get, now: datetime | None = None,
                cryptopanic_key: str | None = None) -> FetchResult:
    """CoinDesk RSS is keyless and always attempted. CryptoPanic is a second
    leg when a key exists; its absence is flagged INLINE under
    value['cryptopanic'], not by silently shipping CoinDesk alone."""
    now = now or datetime.now(timezone.utc)
    try:
        coindesk = _parse_rss(http_get("https://www.coindesk.com/arc/outboundfeeds/rss/"))
    except FETCH_ERRORS as exc:
        return _failed("news", exc)
    value: dict[str, Any] = {"available": True, "coindesk": coindesk}
    cryptopanic_key = cryptopanic_key or os.getenv("CRYPTOPANIC_API_KEY")
    if not cryptopanic_key:
        value["cryptopanic"] = {"available": False, "reason": "missing_credential:CRYPTOPANIC_API_KEY"}
    else:
        try:
            params = urlencode({"auth_token": cryptopanic_key, "public": "true"})
            payload = json.loads(http_get(f"https://cryptopanic.com/api/v1/posts/?{params}"))
            value["cryptopanic"] = {"available": True, "items": payload["results"]}
        except FETCH_ERRORS as exc:
            logger.error("news: cryptopanic leg failed -- %s", exc)
            value["cryptopanic"] = {"available": False, "reason": f"fetch_failed:{exc}"}
    return FetchResult(True, value, _until(4, now), "coindesk_rss+cryptopanic")
