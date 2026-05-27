"""
signal_logger.py — Log centralizado de decisiones de señal.

Escribe logs/signals.jsonl con cada evaluación:
  SENT | SUPPRESSED | BLOCKED | ERROR
+ razón + condiciones de mercado.

Uso:
    from signal_logger import log_signal
    log_signal("ZEC", "SWING", "SUPPRESSED", "Sin consenso: BEAR vs ACCUMULATION",
               price=58.3, rsi=44.1, bias="ACCUMULATION", kumo="BEAR")

Query:
    from signal_logger import get_recent_signals
    signals = get_recent_signals(n=50)
"""
import json
import os
from datetime import datetime

_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "signals.jsonl")


def log_signal(
    symbol: str,
    strategy: str,
    decision: str,       # SENT | SUPPRESSED | BLOCKED | ERROR
    reason: str,
    **conditions,        # price, rsi, bias, kumo, score, etc.
):
    record = {
        "ts": datetime.utcnow().isoformat(),
        "symbol": symbol,
        "strategy": strategy,
        "decision": decision,
        "reason": reason,
        **conditions,
    }
    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception:
        pass


def get_recent_signals(n: int = 50, symbol: str = None, decision: str = None) -> list:
    """Lee las últimas n entradas del signal log, con filtros opcionales."""
    if not os.path.exists(_LOG_FILE):
        return []
    rows = []
    try:
        with open(_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    if symbol and r.get("symbol") != symbol:
                        continue
                    if decision and r.get("decision") != decision:
                        continue
                    rows.append(r)
                except Exception:
                    pass
    except Exception:
        pass
    return rows[-n:]


def get_signal_summary(hours: int = 24) -> dict:
    """Resumen de señales de las últimas N horas."""
    from datetime import timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = get_recent_signals(n=10000)
    summary = {"SENT": 0, "SUPPRESSED": 0, "BLOCKED": 0, "ERROR": 0}
    by_reason: dict = {}
    by_symbol: dict = {}
    for r in rows:
        try:
            ts = datetime.fromisoformat(r["ts"].replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts < cutoff:
                continue
        except Exception:
            continue
        d = r.get("decision", "UNKNOWN")
        summary[d] = summary.get(d, 0) + 1
        reason = r.get("reason", "?")
        by_reason[reason] = by_reason.get(reason, 0) + 1
        sym = r.get("symbol", "?")
        by_symbol[sym] = by_symbol.get(sym, 0) + 1
    return {
        "hours": hours,
        "totals": summary,
        "top_reasons": sorted(by_reason.items(), key=lambda x: -x[1])[:10],
        "by_symbol": by_symbol,
    }
