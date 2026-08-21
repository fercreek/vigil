# instrument/knowledge/

The fundamentals knowledge cache — see `cache.py`'s module docstring for why it
exists (four hand-typed calendar constants in the legacy bot, up to 108 days
stale, none of them ever raised an alert).

- `cache.py` — the store: `put`/`get`/`is_stale`/`require`/`stale_keys`/`freshness_report`.
  `require(conn, key, on_stale)` is the asymmetric core: `on_stale="open"` means a
  stale or missing key must **stop** suppressing, never keep suppressing forever.
- `sources.py` — one fetcher per key (`fetch_derivatives`, `fetch_fear_greed`,
  `fetch_stablecoin_supply`, `fetch_fomc_calendar`, `fetch_earnings`, `fetch_news`).
  Every fetcher takes an injectable `http_get`, never touches the network in tests,
  and turns a failure into `FetchResult(ok=False)` instead of raising.
- `refresh.py` — the cron entry point. Runs every fetcher in `REGISTRY`,
  `cache.put()`s the ones that succeeded, prints a freshness report, and exits 1
  if anything critical failed or is still expired.

## Wiring into the decision path

`rules.evaluate()` stays pure — no database, no network. `main.py` is the only
caller that reads the cache: `scan_once()` calls `cache.require(conn,
"fomc_calendar", on_stale="open")` once per scan and turns a **fresh** entry
inside the +/-24h meeting window into a `suppressions` dict it passes to
`rules.evaluate()`. A **stale** or **missing** entry produces an empty
`suppressions` dict (fail-open — the signal is NOT suppressed) and is logged to
`heartbeats` via `watch.record("knowledge:fomc_calendar", ...)` so the miss is
visible instead of silently passing.

## Running the refresh

```bash
make knowledge-refresh
```

This is `python -m instrument.knowledge.refresh` under the hood (see the
`Makefile` at the repo root) — no systemd, no Docker, just the interpreter.

### Cron

The knowledge cache needs to be refreshed on its own schedule, independent of
the scan loop. A plain crontab line is enough — pick a cadence shorter than the
tightest `valid_until` window that matters to you (`derivatives` is 6h,
`fear_greed`/`stablecoin_supply`/`earnings` are 24h, `news` is 4h; `fomc_calendar`
is valid until the meeting itself). Hourly comfortably covers all of them:

```cron
0 * * * * cd /Users/fernandocastaneda/Documents/ideas/vigil-instrument && make knowledge-refresh >> logs/knowledge_refresh.log 2>&1
```

Install it with `crontab -e`. `refresh.main()` exits 1 on any critical problem
(failed fetch, cache write failure, or a critical key still expired after the
run) — a cron mailer or a log-watching alert on that exit code is what turns a
run into something someone actually sees.
