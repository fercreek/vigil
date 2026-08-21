"""Turn a `signals` row into the Telegram message the user trades from, send it.

Ports scalp_bot/alert_manager.py: safe_html (19-66, survived a real Telegram
400 -- "score 3/5 < 4" hit parse_mode=HTML unescaped in prod) and
send_telegram (136-191). NOT ported: alert() (204-258) -- its dedup is an
in-memory dict that resets on restart; schema.sql's ux_signal_dedup replaces it.

render() is pure: the row, plus the few live values that can't honestly come
from a row written when the signal fired. Not in the row, not passed in ->
not in the message. The legacy bot showed an `ai_analysis` never persisted:
0 of 92 rows kept it.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import requests

from instrument.position_hint import position_hint

_MINUS = "−"  # real minus sign, not a hyphen


def _field(row: dict | sqlite3.Row, key: str, default=None):
    """dict->KeyError, sqlite3.Row->IndexError on a miss; both, and NULL, -> default."""
    try:
        value = row[key]
    except (KeyError, IndexError):
        return default
    return default if value is None else value


def _json_field(row: dict | sqlite3.Row, key: str):
    value = _field(row, key)
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


def _signed(x: float, decimals: int = 2, suffix: str = "") -> str:
    return f"{'+' if x >= 0 else _MINUS}{abs(x):.{decimals}f}{suffix}"


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _format_remaining(td: timedelta) -> str:
    h, m = divmod(max(0, int(td.total_seconds() // 60)), 60)
    return f"{h}h {m}min" if h else f"{m}min"


def _geometry_lines(row) -> list[str]:
    entry, sl = _field(row, "entry_price"), _field(row, "sl_price")
    tp1, tp2 = _field(row, "tp1_price"), _field(row, "tp2_price")
    r_unit = _field(row, "r_unit")
    if None in (entry, sl, tp1, tp2, r_unit):
        return []
    sl_pct = (sl - entry) / entry * 100
    lines = [f"{'Entrada'.ljust(9)}{entry:.2f}",
             f"{'Stop'.ljust(9)}{sl:.2f}   ({_signed(sl_pct, 2, '%')})   1R = {r_unit:.2f}"]
    rr1, rr2 = _field(row, "rr_tp1"), _field(row, "rr_tp2")
    if rr1 is not None:
        lines.append(f"{'TP1'.ljust(9)}{tp1:.2f}   RR {rr1:.2f}")
    if rr2 is not None:
        lines.append(f"{'TP2'.ljust(9)}{tp2:.2f}   RR {rr2:.2f}")
    return lines


def _track_record_lines(row) -> list[str]:
    """One verdict line, not two raw numbers to subtract; a framing line says
    the stat is resolved trades, not this signal -- shown anyway, auditable."""
    breakeven = _field(row, "breakeven_wr")
    ruleset, n = _field(row, "ruleset_version"), _field(row, "ruleset_resolved_n")
    wr = _field(row, "ruleset_wr")
    wr_lo, wr_hi = _field(row, "ruleset_wr_lo"), _field(row, "ruleset_wr_hi")
    exp_r = _field(row, "ruleset_exp_r")
    if breakeven is None:
        return []
    if None in (ruleset, n, wr, wr_lo, wr_hi, exp_r):
        return [f"Necesita hasta {breakeven * 100:.1f}% de aciertos para no perder (mitad sale en TP1)."]
    verdict = "por debajo" if wr < breakeven else "por encima"
    return [
        f"Necesita hasta {breakeven * 100:.1f}% de aciertos; {ruleset} trae "
        f"{wr * 100:.0f}% en {n} señales resueltas (intervalo de confianza "
        f"{wr_lo * 100:.0f}-{wr_hi * 100:.0f}%) — {verdict} del umbral.",
        f"Esa cifra mide señales YA resueltas, no ésta — se manda igual para auditar "
        f"si {ruleset} mejora o se retira, exp {_signed(exp_r, 2, 'R')}.",
    ]


def _trigger_line(row) -> str | None:
    """trigger's raw RSI + gates_passed's human strings; no hardcoded gates."""
    trigger = _json_field(row, "trigger") or {}
    gates = _json_field(row, "gates_passed") or []
    parts = []
    rsi = trigger.get("rsi") if isinstance(trigger, dict) else None
    if rsi is not None:
        parts.append(f"RSI {float(rsi):.1f}")
    parts.extend(str(gate) for gate in gates)
    return "Disparo: " + " · ".join(parts) if parts else None


def _llm_line(row) -> str | None:
    """NULL llm_verdict -> no line: it annotates, never gates."""
    verdict = _json_field(row, "llm_verdict")
    if not verdict:
        return None
    side = verdict.get("side") or verdict.get("verdict") or "?"
    score, max_score = verdict.get("score"), verdict.get("max_score", 5)
    reason = verdict.get("reason") or verdict.get("note") or ""
    score_txt = f" {score}/{max_score}" if score is not None else ""
    return f'🤖 LLM: {side}{score_txt} — "{reason}" (no gatea, solo se registra)'


def _now_line(row, current_price: float | None, now: datetime | None) -> str | None:
    """Distance to the live quote + time to expiry -- inputs, the row can't know "now"."""
    parts = []
    entry = _field(row, "entry_price")
    if current_price is not None and entry:
        d = (current_price - entry) / entry * 100
        parts.append(f"Ahora: {current_price:.2f} ({_signed(d, 2, '%')} de la entrada)")
    expires_at = _field(row, "expires_at")
    if expires_at and now is not None:
        expiry = _parse_ts(expires_at)
        remaining = expiry - now
        if remaining.total_seconds() <= 0:
            parts.append("expiró — muerta")
        else:
            parts.append(f"quedan {_format_remaining(remaining)} "
                          f"(vence {expiry:%H:%M} UTC, después: muerta)")
    return " · ".join(parts) if parts else None


def render(signal_row: dict | sqlite3.Row, account_size: float = 1000.0,
           risk_pct: float = 0.01, current_price: float | None = None,
           now: datetime | None = None) -> str:
    """Same row + same optional live inputs -> same string, always."""
    header = [f"{_field(signal_row, 'symbol', '?')} {_field(signal_row, 'side', '?')} · "
              f"{_field(signal_row, 'timeframe', '?')} · señal #{_field(signal_row, 'id', '?')}"]
    header += _geometry_lines(signal_row)

    context = list(_track_record_lines(signal_row))
    trigger = _trigger_line(signal_row)
    context.append(trigger) if trigger else None
    bar_ts = _field(signal_row, "bar_ts")
    if bar_ts:
        context.append(f"Vela cerrada {_parse_ts(bar_ts):%Y-%m-%d %H:%M} UTC")
    hint = position_hint(signal_row, account_size, risk_pct)
    context.append(hint) if hint else None

    tail = [line for line in (_llm_line(signal_row),
                               _now_line(signal_row, current_price, now)) if line]
    sections = [s for s in (header, context, tail) if s]
    return "\n\n".join("\n".join(section) for section in sections)


def signal_keyboard(signal_id) -> dict:
    """TOMADA / PASO inline keyboard; callback_data carries signal_id."""
    return {"inline_keyboard": [[
        {"text": "✅ TOMADA", "callback_data": f"taken:{signal_id}"},
        {"text": "⏭️ PASO", "callback_data": f"pass:{signal_id}"},
    ]]}


_ACK_LABEL = {"taken": "✅ TOMADA", "pass": "⏭️ PASO"}


def acknowledge_text(rendered: str, choice: str, at: datetime | None = None) -> str:
    """Text to edit into after a tap; caller sets reply_markup=None too."""
    label = _ACK_LABEL.get(choice, choice)
    stamp = (at or datetime.now(timezone.utc)).strftime("%H:%M UTC")
    return f"{rendered}\n\n{label} · marcado {stamp}"


def safe_html(text: str) -> str:
    """Ported from alert_manager.py:19-66, trimmed to the escaping core --
    render() emits plain text, never the markdown/HTML the original also
    normalised (ul/li/h1-6/br/p), so those branches never fire here and
    stayed behind. What's kept is what mattered: an unescaped
    "score 3/5 < 4" 400'd a live message once; this is why it can't again."""
    if not text:
        return ""
    t = text
    allowed = ["b", "i", "u", "s", "code", "pre", "a"]
    for tag in allowed:
        t = re.sub(rf"<{tag}>", f"__LT__{tag}__GT__", t, flags=re.IGNORECASE)
        t = re.sub(rf"</{tag}>", f"__LT__/{tag}__GT__", t, flags=re.IGNORECASE)
    t = t.replace("<", "&lt;").replace(">", "&gt;")
    t = t.replace("__LT__", "<").replace("__GT__", ">")
    t = re.sub(r"&(?!(?:[a-zA-Z]+|#[0-9]+|#x[0-9a-fA-F]+);)", "&amp;", t)
    for tag in allowed:
        opens = len(re.findall(rf"<{tag}>", t, re.IGNORECASE))
        closes = len(re.findall(rf"</{tag}>", t, re.IGNORECASE))
        if opens > closes:
            t += f"</{tag}>" * (opens - closes)
        elif closes > opens:
            for _ in range(closes - opens):
                t = re.sub(rf"</{tag}>(?!.*</{tag}>)", "", t, count=1, flags=re.IGNORECASE)
    return t


TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
_TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def send_telegram(text: str, reply_markup: dict | None = None) -> str | None:
    """Ported from alert_manager.py:136-191, minus reply-to + config kill switch."""
    url = _TELEGRAM_API.format(token=TELEGRAM_TOKEN, method="sendMessage")
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    for attempt in range(3):
        try:
            response = requests.post(url, json=payload, timeout=10)
            result = response.json()
        except requests.RequestException as exc:
            print(f"[telegram] network error (try {attempt + 1}/3): {exc}")
            time.sleep(2 ** attempt)
            continue
        if result.get("ok"):
            return str(result["result"]["message_id"])
        if response.status_code == 429:
            time.sleep(result.get("parameters", {}).get("retry_after", 2) + 1)
            continue
        print(f"[telegram] {response.status_code}: {result.get('description')}")
        if response.status_code in (401, 403, 404):
            return None  # auth/routing errors: retrying fixes nothing
        time.sleep(2 ** attempt)
    print("[telegram] 3 attempts failed -- message lost")
    return None


def send_signal(signal_row: dict | sqlite3.Row, **render_kwargs) -> str | None:
    """Render + escape + send one signal, with its TOMADA/PASO keyboard."""
    text = safe_html(render(signal_row, **render_kwargs))
    return send_telegram(text, reply_markup=signal_keyboard(_field(signal_row, "id")))
