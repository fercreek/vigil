"""llm_note.py — the LLM annotates, it does not decide.

Product decision, already made (instrument/schema.sql:38, `llm_verdict`): the
deterministic rule in rules.py fires; the LLM opines alongside it; the verdict
is stored but never gates the signal. That is what makes the A/B free -- at N
cases you can tell whether the LLM added anything, or only cost money.

The legacy bot had 8 rate-limit incidents (429s from Groq and Gemini). The
root cause was never fixed: ThreadPoolExecutor(max_workers=4) fanned four
concurrent calls out over one synchronous HTTP client with no throttle. This
module makes that shape of bug structurally impossible here -- `annotate` is
single-call, single-signal, no concurrency, no retries, and enforces the
timeout itself (in a lone worker) rather than trusting an injected client to
respect the `timeout` argument it is handed.

No provider is wired in. `client` is any `Callable[[dict, float], Any]` the
caller supplies, so tests never touch the network and a real deployment can
point this at Groq, Gemini, Anthropic, or a stub without editing this file.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

DEFAULT_TIMEOUT_SECONDS = 8.0

LLMClient = Callable[[dict[str, Any], float], Any]


def annotate(signal: dict[str, Any], client: LLMClient | None,
             timeout: float = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any] | None:
    """Ask `client` for an opinion on `signal`. Returns the JSON-able dict to
    store in signals.llm_verdict, or None on ANY failure -- a crashing client,
    a client that hangs past `timeout`, or a response that cannot be turned
    into a dict. The caller's SENT/SUPPRESSED decision already happened before
    this runs; this function has no way to change it even if it tried, because
    it returns data, not a verdict on whether to emit.

    One worker, one submit, one hard deadline: this is what "no retries" and
    "the timeout is enforced, not requested" look like in code, and it is the
    direct fix for the ThreadPoolExecutor(max_workers=4) root cause above.
    Deliberately NOT a `with ThreadPoolExecutor(...)` block -- that form calls
    shutdown(wait=True) on exit and would block on a hung client until it
    finally returns, which is the exact failure a hard timeout exists to
    avoid. shutdown(wait=False) lets annotate() return the moment the
    deadline passes, leaving the lone stuck worker to die on its own.
    """
    if client is None:
        return None
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        raw = pool.submit(client, signal, timeout).result(timeout=timeout)
    except Exception:  # border: client is an arbitrary injected provider call
        return None
    finally:
        pool.shutdown(wait=False)
    return _coerce(raw)


def _coerce(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except ValueError:
            return {"note": raw}
        return parsed if isinstance(parsed, dict) else {"note": raw}
    return None
