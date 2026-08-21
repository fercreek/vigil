"""Tests for knowledge/sources.py and knowledge/refresh.py. Every HTTP call
goes through an injected `http_get` stub -- nothing here touches the network.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from instrument.knowledge import cache, refresh, sources

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


def _router(responses: dict[str, str]):
    """url -> canned body, matched by prefix so query strings don't matter."""
    def _get(url: str) -> str:
        for prefix, body in responses.items():
            if url.startswith(prefix):
                return body
        raise AssertionError(f"unstubbed url: {url}")
    return _get


def _raiser(exc: BaseException):
    def _get(url: str) -> str:
        raise exc
    return _get


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    return c


# ---------- 1. each fetcher's valid_until matches its declared window ----------

def test_derivatives_window_is_6h():
    http_get = _router({
        "https://fapi.binance.com/fapi/v1/premiumIndex": json.dumps(
            {"markPrice": "45.5", "lastFundingRate": "0.0001", "nextFundingTime": 1755000000000}),
        "https://fapi.binance.com/fapi/v1/openInterest": json.dumps({"openInterest": "12345.6"}),
    })
    result = sources.fetch_derivatives("ZEC", http_get=http_get, now=NOW)
    assert result.ok
    assert result.value["mark_price"] == 45.5
    assert result.valid_until == (NOW + timedelta(hours=6)).isoformat()


def test_fear_greed_window_is_24h():
    http_get = _router({"https://api.alternative.me/fng": json.dumps(
        {"data": [{"value": "54", "value_classification": "Neutral", "timestamp": "1755000000"}]})})
    result = sources.fetch_fear_greed(http_get=http_get, now=NOW)
    assert result.ok
    assert result.value == {"available": True, "value": 54,
                            "classification": "Neutral", "as_of": "1755000000"}
    assert result.valid_until == (NOW + timedelta(hours=24)).isoformat()


def test_stablecoin_supply_window_is_24h():
    http_get = _router({"https://stablecoins.llama.fi/stablecoins": json.dumps({"peggedAssets": [
        {"circulating": {"peggedUSD": 100.0}, "circulatingPrevDay": {"peggedUSD": 90.0}},
        {"circulating": {"peggedUSD": 50.0}},
    ]})})
    result = sources.fetch_stablecoin_supply(http_get=http_get, now=NOW)
    assert result.ok
    assert result.value["total_usd"] == 150.0
    assert result.value["change_1d_usd"] == 60.0
    assert result.valid_until == (NOW + timedelta(hours=24)).isoformat()


def test_fomc_calendar_valid_until_is_the_meeting_date_html_path(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    html = (
        '<h4><a id="1">2026 FOMC Meetings</a></h4>'
        '<div class="fomc-meeting__month col"><strong>September</strong></div>'
        '<div class="fomc-meeting__date col">15-16*</div>'
    )
    http_get = _router({"https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm": html})
    result = sources.fetch_fomc_calendar(http_get=http_get, now=NOW)
    assert result.ok
    assert result.source == "fed_calendar_html"
    assert result.valid_until == result.value["next_meeting_date"]
    assert result.value["next_meeting_date"].startswith("2026-09-16")


def test_fomc_calendar_uses_fred_when_key_present():
    http_get = _router({"https://api.stlouisfed.org/fred/releases/dates": json.dumps(
        {"release_dates": [{"date": "2026-09-16"}]})})
    result = sources.fetch_fomc_calendar(http_get=http_get, now=NOW, fred_api_key="fake-key")
    assert result.ok
    assert result.source == "fred_releases_dates"
    assert result.valid_until == "2026-09-16"


def test_news_window_is_4h():
    rss = ('<rss><channel><item><title>ZEC rallies</title>'
           '<link>https://example.com/a</link>'
           '<pubDate>Fri, 21 Aug 2026 12:00:00 GMT</pubDate></item></channel></rss>')
    http_get = _router({"https://www.coindesk.com/arc/outboundfeeds/rss/": rss})
    result = sources.fetch_news(http_get=http_get, now=NOW)
    assert result.ok
    assert result.value["coindesk"][0]["title"] == "ZEC rallies"
    assert result.valid_until == (NOW + timedelta(hours=4)).isoformat()


# ---------- 2. missing credential is ok=True and DISTINGUISHABLE from "no data" ----------

def test_earnings_missing_credential_is_distinguishable(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    result = sources.fetch_earnings(["MSTR"], http_get=_raiser(AssertionError("must not be called")))
    assert result.ok  # a completed check, not a crash
    assert result.value["available"] is False
    assert result.value["reason"] == "missing_credential:FINNHUB_API_KEY"
    empty_but_checked = {"available": True, "window": {"from": "x", "to": "y"}, "by_ticker": {}}
    assert result.value != empty_but_checked  # not the same shape as "checked, nothing new"


def test_earnings_with_key_hits_finnhub():
    http_get = _router({"https://finnhub.io/api/v1/calendar/earnings": json.dumps(
        {"earningsCalendar": [{"date": "2026-08-25", "symbol": "MSTR"}]})})
    result = sources.fetch_earnings(["MSTR"], http_get=http_get, now=NOW, api_key="fake-key")
    assert result.ok
    assert result.value["available"] is True
    assert result.value["by_ticker"]["MSTR"][0]["symbol"] == "MSTR"


def test_news_flags_missing_cryptopanic_key_inline_not_as_silence(monkeypatch):
    monkeypatch.delenv("CRYPTOPANIC_API_KEY", raising=False)
    http_get = _router({"https://www.coindesk.com/arc/outboundfeeds/rss/": "<rss><channel></channel></rss>"})
    result = sources.fetch_news(http_get=http_get, now=NOW)
    assert result.value["available"] is True  # CoinDesk alone still counts as real data
    assert result.value["cryptopanic"] == {
        "available": False, "reason": "missing_credential:CRYPTOPANIC_API_KEY"}


# ---------- 3. one broken fetcher does not stop the others ----------

def test_refresh_isolates_one_broken_fetcher(conn):
    good_result = sources.FetchResult(True, {"available": True, "x": 1},
                                      "2099-01-01T00:00:00+00:00", "stub")
    registry = {
        "good_one": (lambda: good_result, True),
        "derivatives": (lambda: sources.fetch_derivatives(
            "ZEC", http_get=_raiser(ConnectionError("simulated down")), now=NOW), True),
    }
    report, problems = refresh.run(conn, registry=registry, now=NOW)
    assert cache.get(conn, "good_one") is not None
    assert cache.get(conn, "derivatives") is None
    assert any("derivatives" in p for p in problems)
    assert any(row["key"] == "good_one" for row in report)


def test_refresh_survives_a_registry_entry_that_raises_directly(conn):
    """Defence in depth: even a fetcher that forgot to catch its own network
    call must not take the rest of the run down with it."""
    good_result = sources.FetchResult(True, {"available": True}, "2099-01-01T00:00:00+00:00", "stub")
    registry = {
        "good_one": (lambda: good_result, True),
        "raises_directly": (lambda: (_ for _ in ()).throw(ValueError("boom")), True),
    }
    report, problems = refresh.run(conn, registry=registry, now=NOW)
    assert cache.get(conn, "good_one") is not None
    assert any("raises_directly" in p for p in problems)


# ---------- 4. refresh exits non-zero when a critical entry is missing ----------

def test_refresh_run_flags_critical_failure_for_nonzero_exit(conn):
    registry = {
        "critical_missing": (lambda: sources._failed("critical_missing", ConnectionError("down")), True),
        "noncritical_missing": (lambda: sources._failed("noncritical_missing", ConnectionError("down")), False),
    }
    _, problems = refresh.run(conn, registry=registry, now=NOW)
    assert (1 if problems else 0) != 0
    assert any("critical_missing" in p for p in problems)


def test_refresh_run_clean_when_everything_ok(conn):
    ok_result = sources.FetchResult(True, {"available": True},
                                    (NOW + timedelta(hours=1)).isoformat(), "stub")
    registry = {"k": (lambda: ok_result, True)}
    report, problems = refresh.run(conn, registry=registry, now=NOW)
    assert problems == []
    assert any(row["key"] == "k" and not row["expired"] for row in report)


def test_refresh_main_exit_code_nonzero_on_critical_failure(tmp_path, monkeypatch):
    db_path = str(tmp_path / "instrument.db")
    broken_registry = {"derivatives": (lambda: sources._failed("derivatives", ConnectionError("down")), True)}
    monkeypatch.setattr(refresh, "REGISTRY", broken_registry)
    assert refresh.main(["--db", db_path]) != 0


# ---------- 5. a malformed response is a registered fetcher failure, not a crash ----------

def test_malformed_json_is_a_registered_failure_not_a_crash():
    http_get = _router({
        # markPrice present, lastFundingRate missing -> KeyError inside the fetcher
        "https://fapi.binance.com/fapi/v1/premiumIndex": json.dumps({"markPrice": "45.5"}),
        "https://fapi.binance.com/fapi/v1/openInterest": json.dumps({"openInterest": "12345.6"}),
    })
    result = sources.fetch_derivatives("ZEC", http_get=http_get, now=NOW)
    assert result.ok is False
    assert result.value is None
    assert "lastFundingRate" in result.error


def test_malformed_xml_is_a_registered_failure_not_a_crash():
    http_get = _router({"https://www.coindesk.com/arc/outboundfeeds/rss/": "<rss><channel><item><title>oops"})
    result = sources.fetch_news(http_get=http_get, now=NOW)
    assert result.ok is False
    assert "ParseError" in result.error


def test_fomc_html_with_no_matching_meetings_is_a_failure_not_zero_upcoming():
    http_get = _router({
        "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm": "<html>redesigned, no hooks</html>",
    })
    result = sources.fetch_fomc_calendar(http_get=http_get, now=NOW)
    assert result.ok is False
    assert "fomccalendars" in result.error
