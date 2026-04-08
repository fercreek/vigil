"""
signal_coordinator.py — Zenith Trading Suite

Sits between AI agents and Telegram. Agents submit signal intents here;
the coordinator resolves conflicts and decides what to send.
"""

import time
import logging
from typing import Callable

log = logging.getLogger(__name__)

WINDOW_SECS = 300  # 5-min collection window before resolving

ACTIONABLE = {"LONG", "SHORT"}
NEUTRAL = {"ESPERAR", "ACUMULAR", "REDUCIR"}

# In-memory state — resets on restart, no DB needed.
# {symbol: [{"source", "direction", "confidence", "ts", "msg"}, ...]}
_signals: dict = {}


def submit(source: str, symbol: str, direction: str, confidence: float, msg: str) -> None:
    """Register a signal intent without sending to Telegram.

    source    — "SALMOS" | "SENTINEL" | "V1-TECH" | "V2-AI"
    direction — "LONG" | "SHORT" | "ESPERAR" | "ACUMULAR" | "REDUCIR"
    confidence — 0.0–1.0
    msg       — full formatted message to send if approved
    """
    entry = {
        "source": source,
        "direction": direction.upper(),
        "confidence": float(confidence),
        "ts": time.time(),
        "msg": msg,
    }
    _signals.setdefault(symbol, []).append(entry)
    log.debug("[coordinator] %s submitted %s/%s (conf=%.2f)", source, symbol, direction, confidence)


def get_verdict(symbol: str) -> dict:
    """Evaluate collected signals for *symbol* and return a decision dict.

    Returns {"action": "SEND"|"HOLD"|"CONFLICT", "direction": str,
             "msg": str, "reason": str}
    """
    now = time.time()
    entries = [s for s in _signals.get(symbol, []) if now - s["ts"] <= WINDOW_SECS]

    if not entries:
        return {"action": "HOLD", "direction": "", "msg": "", "reason": "no signals"}

    directions = {e["direction"] for e in entries}
    oldest_age = now - min(e["ts"] for e in entries)

    # Only one source so far
    if len(entries) == 1:
        if oldest_age < WINDOW_SECS:
            return {"action": "HOLD", "direction": entries[0]["direction"],
                    "msg": entries[0]["msg"], "reason": "waiting for more signals"}
        # Window expired with a single signal — send it
        return {"action": "SEND", "direction": entries[0]["direction"],
                "msg": entries[0]["msg"], "reason": "single signal after window"}

    # All signals agree
    if len(directions) == 1:
        best = max(entries, key=lambda e: e["confidence"])
        return {"action": "SEND", "direction": best["direction"],
                "msg": best["msg"], "reason": "all sources agree"}

    # Conflict — directions disagree
    actionable = [e for e in entries if e["direction"] in ACTIONABLE]
    high_conf = [e for e in actionable if e["confidence"] >= 0.8]

    if high_conf:
        best = max(high_conf, key=lambda e: e["confidence"])
        conflicting = [e["source"] for e in entries if e["direction"] != best["direction"]]
        note = f"[⚠️ CONFLICTO: {', '.join(conflicting)} {'dicen' if len(conflicting) > 1 else 'dice'} {', '.join(e['direction'] for e in entries if e['source'] in conflicting)}]"
        return {"action": "SEND", "direction": best["direction"],
                "msg": best["msg"] + f"\n\n{note}", "reason": "conflict — high-confidence actionable wins"}

    return {"action": "CONFLICT", "direction": "", "msg": "",
            "reason": f"conflicting directions: {directions} — no high-confidence actionable signal"}


def resolve_and_send(symbol: str, send_fn: Callable[[str], None]) -> bool:
    """Evaluate verdict for *symbol*, call send_fn if approved, then clean up.

    Returns True if a message was sent.
    """
    verdict = get_verdict(symbol)
    action = verdict["action"]
    log.info("[coordinator] %s → %s (%s)", symbol, action, verdict["reason"])

    if action == "SEND":
        try:
            send_fn(verdict["msg"])
        except Exception as exc:
            log.error("[coordinator] send_fn failed for %s: %s", symbol, exc)
            return False
        _signals.pop(symbol, None)
        return True

    if action == "CONFLICT":
        log.warning("[coordinator] CONFLICT on %s — suppressed. %s", symbol, verdict["reason"])
        _signals.pop(symbol, None)

    return False


def cleanup_stale() -> None:
    """Remove signals older than WINDOW_SECS * 3 (15 min) to prevent memory leaks."""
    cutoff = time.time() - WINDOW_SECS * 3
    for symbol in list(_signals.keys()):
        _signals[symbol] = [s for s in _signals[symbol] if s["ts"] >= cutoff]
        if not _signals[symbol]:
            del _signals[symbol]
