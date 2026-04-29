"""
voice_compactor.py — adapters that turn Cuadrilla Zenith verbose output
into compact Telegram messages (v1.2.0).

Two layers:
1. `compact_sentinel_prompt()` — returns a short prompt that asks Gemini for
   structured JSON (bias, score, voices: 8-word lines each, action).
2. `render_sentinel_compact()` — converts that JSON into 6-7 line Telegram
   format with emoji-prefixed voices.

Falls back to verbose if parsing fails (still sends, just longer).

Threshold + dedupe live here too so callers stay slim:
- `should_send_sentinel(symbol, bias, score)` — applies SENTINEL_MIN_SCORE_OF_5
  + SENTINEL_DEDUPE_MIN gating against in-memory dict.
"""

from __future__ import annotations

import json
import re
import time
from typing import Optional

from config import (
    SENTINEL_DEDUPE_MIN,
    SENTINEL_MIN_SCORE_OF_5,
)


# ───────────────────────── Dedupe state (in-memory) ──────────────────────────

# (symbol, bias) -> (score, ts_epoch)
_DEDUPE: dict[tuple[str, str], tuple[int, float]] = {}


def should_send_sentinel(symbol: str, bias: str, score: int) -> tuple[bool, str]:
    """Returns (should_send, reason). Reason useful for logging."""
    if score < SENTINEL_MIN_SCORE_OF_5:
        return False, f"score {score}/5 < {SENTINEL_MIN_SCORE_OF_5}"

    key = (symbol, bias)
    now = time.time()
    prev = _DEDUPE.get(key)
    if prev is not None:
        prev_score, prev_ts = prev
        age_min = (now - prev_ts) / 60.0
        if age_min < SENTINEL_DEDUPE_MIN and score <= prev_score:
            return False, f"dup {symbol}/{bias} {int(age_min)}min ago (score {prev_score}->{score})"

    _DEDUPE[key] = (score, now)
    return True, "ok"


def clear_dedupe() -> None:
    """Reset dedupe state — used by tests + /resume."""
    _DEDUPE.clear()


# ──────────────────────────────── Prompt ─────────────────────────────────────

def compact_sentinel_prompt(symbol: str, market_block: str, macro_block: str,
                            memory_ctx: str = "") -> str:
    """Build sentinel prompt that forces compact JSON output."""
    return f"""SENTINEL {symbol}

DATOS:
{market_block}

MACRO:
{macro_block}
{memory_ctx}

Devuelve SOLO un JSON válido (sin markdown, sin \\\\`\\\\`\\\\`):
{{
  "bias": "LONG | SHORT | NEUTRAL",
  "score": 1-5 (5 = setup impecable, 1 = tesis invalidada),
  "verdict": "ACUMULAR | ESPERAR | REDUCIR",
  "voices": {{
    "genesis":   "max 8 palabras — capital institucional / acumulacion",
    "exodo":     "max 8 palabras — narrativa / tecnología",
    "salmos":    "max 8 palabras — confluencia tecnica RSI/EMA/BB",
    "apocalipsis": "max 8 palabras — riesgo macro principal"
  }},
  "action": "max 12 palabras — qué hacer YA o esperar a qué nivel"
}}

Reglas estrictas:
- JSON en una sola linea o multilinea, pero PARSEABLE.
- NO uses comillas curvas, NO \\\\`\\\\`\\\\`json, NO comentarios.
- Cada voz: ≤8 palabras, sin nombrar al ticker (ya está en bias/score).
- action: con un nivel de precio si aplica."""


# ───────────────────────────── JSON parser ───────────────────────────────────

def parse_sentinel_json(raw: str) -> Optional[dict]:
    """Tries hard to extract dict from Gemini response, returns None if fails."""
    if not raw:
        return None

    text = raw.strip()
    # Strip ```json ... ``` fences if Gemini ignored instruction
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # First try direct parse
    try:
        data = json.loads(text)
        return _validate(data)
    except json.JSONDecodeError:
        pass

    # Try to find first {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            return _validate(data)
        except json.JSONDecodeError:
            pass

    # Fallback: regex-extract top-level scalar fields from truncated JSON.
    # Handles Gemini cutting off mid-string inside "voices" — we recover
    # bias/score/verdict which are sufficient for the renderer.
    return _repair_partial(text)


def _repair_partial(text: str) -> Optional[dict]:
    """Extract top-level scalar fields from truncated JSON via regex."""
    bias_m    = re.search(r'"bias"\s*:\s*"([^"]+)"', text)
    score_m   = re.search(r'"score"\s*:\s*(\d+)', text)
    verdict_m = re.search(r'"verdict"\s*:\s*"([^"]+)"', text)
    action_m  = re.search(r'"action"\s*:\s*"([^"]+)"', text)

    if not (bias_m and score_m):
        return None   # not enough data to build a useful result

    partial = {
        "bias":    bias_m.group(1),
        "score":   int(score_m.group(1)),
        "verdict": verdict_m.group(1) if verdict_m else "ESPERAR",
        "action":  action_m.group(1) if action_m else "—",
        "voices":  {},   # truncated — renderer shows "—" placeholders
    }
    return _validate(partial)


def _validate(data: dict) -> Optional[dict]:
    """Sanitize + ensure required keys exist."""
    if not isinstance(data, dict):
        return None
    bias = str(data.get("bias", "NEUTRAL")).upper()
    if bias not in ("LONG", "SHORT", "NEUTRAL"):
        bias = "NEUTRAL"
    try:
        score = int(data.get("score", 0))
    except (TypeError, ValueError):
        score = 0
    score = max(1, min(5, score))

    voices = data.get("voices", {})
    if not isinstance(voices, dict):
        voices = {}

    return {
        "bias": bias,
        "score": score,
        "verdict": str(data.get("verdict", "ESPERAR")).upper(),
        "voices": {
            "genesis": str(voices.get("genesis", "—"))[:120],
            "exodo": str(voices.get("exodo", "—"))[:120],
            "salmos": str(voices.get("salmos", "—"))[:120],
            "apocalipsis": str(voices.get("apocalipsis", "—"))[:120],
        },
        "action": str(data.get("action", "—"))[:160],
    }


# ────────────────────────────── Renderer ─────────────────────────────────────

_BIAS_EMOJI = {
    "LONG": "🟢",
    "SHORT": "🔴",
    "NEUTRAL": "⚪",
}

_VERDICT_EMOJI = {
    "ACUMULAR": "✅",
    "ESPERAR":  "⏳",
    "REDUCIR":  "❌",
}


def render_sentinel_compact(symbol: str, parsed: dict, price: float, rsi: float,
                            extra: str = "") -> str:
    """Build the 6-7 line Telegram message from parsed dict."""
    bias = parsed.get("bias", "NEUTRAL")
    score = parsed.get("score", 0)
    verdict = parsed.get("verdict", "ESPERAR")
    voices = parsed.get("voices", {})
    action = parsed.get("action", "—")

    bemoji = _BIAS_EMOJI.get(bias, "⚪")
    vemoji = _VERDICT_EMOJI.get(verdict, "⏳")

    lines = [
        f"{bemoji} <b>{symbol}</b> · {score}/5 {bias} · ${price:,.2f}",
    ]
    if extra:
        lines.append(f"<code>{extra}</code>")
    else:
        lines.append(f"<code>RSI {rsi:.0f}</code>")

    lines.extend([
        f"🎩 {voices.get('genesis', '—')}",
        f"⚡ {voices.get('exodo', '—')}",
        f"🌊 {voices.get('salmos', '—')}",
        f"💀 {voices.get('apocalipsis', '—')}",
        f"{vemoji} <b>{action}</b>",
    ])
    return "\n".join(lines)


# ──────────────────── Compact PANORAMA renderer ──────────────────────────────

def render_panorama_compact(ts: str, btc_p: float, btc_rsi: float,
                            tao_p: float, tao_rsi: float, usdt_d: float,
                            salmos_text: str, scalper_text: str,
                            eco_lines: Optional[list[str]] = None) -> str:
    """6-9 line panorama. Voices already trimmed to BIAS/CLAVE/ACCIÓN format."""
    lines = [
        f"🤖 <b>PANORAMA [{ts}]</b>",
        f"<code>BTC ${btc_p:,.0f} rsi{btc_rsi:.0f} · TAO ${tao_p:,.2f} rsi{tao_rsi:.0f} · USDT.D {usdt_d:.2f}%</code>",
        "━━━━━",
    ]
    if salmos_text:
        lines.append(f"🌊 {salmos_text.strip()}")
    if scalper_text:
        lines.append(f"⚡ {scalper_text.strip()}")
    if eco_lines:
        lines.append("━━━━━")
        lines.append("📡 <i>Eco 24h</i>")
        for ln in eco_lines[:5]:
            lines.append(ln)
    return "\n".join(lines)
