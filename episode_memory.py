"""episode_memory.py — Episodic memory for Zenith Trading Suite.

Every alert sent = one episode logged.
Outcomes (WIN/LOSS) are filled automatically when price crosses tp1/sl,
or manually by trade_monitor / stock_watchdog.
"""

import sqlite3
from datetime import datetime, timezone

DB_FILE = "trades.db"


def init_episode_table():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS signal_episodes (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            ts               TEXT,
            symbol           TEXT,
            strategy         TEXT,
            direction        TEXT,
            rsi              REAL,
            usdt_d           REAL,
            bb_pos           TEXT,
            ema_trend        TEXT,
            confluence       INTEGER,
            atr_pct          REAL,
            entry_price      REAL DEFAULT NULL,
            sl_price         REAL DEFAULT NULL,
            tp1_price        REAL DEFAULT NULL,
            source           TEXT DEFAULT 'CRYPTO',
            outcome          TEXT DEFAULT NULL,
            outcome_pnl      REAL DEFAULT NULL,
            outcome_filled_at TEXT DEFAULT NULL
        )
    """)
    # Migrate older tables that are missing the new columns
    existing = {row[1] for row in c.execute("PRAGMA table_info(signal_episodes)")}
    for col, definition in [
        ("entry_price",       "REAL DEFAULT NULL"),
        ("sl_price",          "REAL DEFAULT NULL"),
        ("tp1_price",         "REAL DEFAULT NULL"),
        ("source",            "TEXT DEFAULT 'CRYPTO'"),
    ]:
        if col not in existing:
            c.execute(f"ALTER TABLE signal_episodes ADD COLUMN {col} {definition}")
    conn.commit()
    conn.close()


# ── Core write functions ───────────────────────────────────────────────────────

def log_episode(symbol, strategy, direction, rsi, usdt_d, bb_pos, ema_trend,
                confluence, atr_pct):
    """Original insert (crypto V1-TECH). Returns inserted row id."""
    return _insert(symbol, strategy, direction, rsi, usdt_d, bb_pos, ema_trend,
                   confluence, atr_pct, None, None, None, "CRYPTO")


def log_alert_episode(symbol, strategy, direction, entry, sl, tp1,
                      rsi=None, confluence=None, source="CRYPTO"):
    """Universal entry point — called whenever an alert is sent.

    Args:
        symbol    : e.g. "TAO", "TSLA", "BTC"
        strategy  : "V1-TECH", "V3-REV", "V4-EMA", "V1-SHORT",
                    "V2-AI", "SALMOS", "STOCK", "WEBHOOK"
        direction : "LONG" | "SHORT" | "ESPERAR"
        entry     : entry price (float or None)
        sl        : stop-loss price (float or None)
        tp1       : first take-profit price (float or None)
        source    : "CRYPTO" | "STOCK" | "SALMOS" | "WEBHOOK"
    """
    return _insert(symbol, strategy, direction, rsi, None, None, None,
                   confluence, None, entry, sl, tp1, source)


def _insert(symbol, strategy, direction, rsi, usdt_d, bb_pos, ema_trend,
            confluence, atr_pct, entry_price, sl_price, tp1_price, source):
    ts = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO signal_episodes
            (ts, symbol, strategy, direction, rsi, usdt_d, bb_pos, ema_trend,
             confluence, atr_pct, entry_price, sl_price, tp1_price, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (ts, symbol, strategy, direction, rsi, usdt_d, bb_pos, ema_trend,
          confluence, atr_pct, entry_price, sl_price, tp1_price, source))
    episode_id = c.lastrowid
    conn.commit()
    conn.close()
    return episode_id


def fill_outcome(episode_id, outcome, pnl_pct):
    """Update outcome for a specific episode id."""
    _fill_where("id = ?", (episode_id,), outcome, pnl_pct)


def fill_outcome_by_symbol(symbol, strategy, outcome, pnl_pct):
    """Fill the most recent pending episode for a symbol+strategy."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT id FROM signal_episodes
        WHERE symbol = ? AND strategy = ? AND outcome IS NULL
        ORDER BY ts DESC LIMIT 1
    """, (symbol, strategy))
    row = c.fetchone()
    conn.close()
    if row:
        _fill_where("id = ?", (row[0],), outcome, pnl_pct)
        return row[0]
    return None


def _fill_where(where_clause, params, outcome, pnl_pct):
    filled_at = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(f"""
        UPDATE signal_episodes
        SET outcome = ?, outcome_pnl = ?, outcome_filled_at = ?
        WHERE {where_clause} AND outcome IS NULL
    """, (outcome, pnl_pct, filled_at) + params)
    conn.commit()
    conn.close()


# ── Auto-fill pending outcomes ─────────────────────────────────────────────────

def check_pending_outcomes(prices: dict):
    """Called from the main loop with live prices.

    For every pending episode that has entry+sl+tp1 stored,
    checks whether the current price has crossed tp1 (WIN) or sl (LOSS).
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT id, symbol, direction, entry_price, sl_price, tp1_price
        FROM signal_episodes
        WHERE outcome IS NULL
          AND entry_price IS NOT NULL
          AND sl_price    IS NOT NULL
          AND tp1_price   IS NOT NULL
    """)
    pending = c.fetchall()
    conn.close()

    filled = 0
    for row in pending:
        sym = row["symbol"]
        p   = prices.get(sym) or prices.get(f"{sym}/USDT")
        if not p:
            continue
        entry = row["entry_price"]
        sl    = row["sl_price"]
        tp1   = row["tp1_price"]
        direction = row["direction"]

        if direction == "LONG":
            if p >= tp1:
                pnl = (tp1 - entry) / entry * 100
                _fill_where("id = ?", (row["id"],), "WIN", round(pnl, 2))
                filled += 1
            elif p <= sl:
                pnl = (sl - entry) / entry * 100
                _fill_where("id = ?", (row["id"],), "LOSS", round(pnl, 2))
                filled += 1
        elif direction == "SHORT":
            if p <= tp1:
                pnl = (entry - tp1) / entry * 100
                _fill_where("id = ?", (row["id"],), "WIN", round(pnl, 2))
                filled += 1
            elif p >= sl:
                pnl = (entry - sl) / entry * 100
                _fill_where("id = ?", (row["id"],), "LOSS", round(pnl, 2))
                filled += 1

    return filled


# ── Win rate stats ─────────────────────────────────────────────────────────────

def get_winrate_stats(days: int = 30) -> dict:
    """Return win rate stats per strategy and overall for the last N days."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT strategy, direction, outcome, outcome_pnl
        FROM signal_episodes
        WHERE ts >= datetime('now', ?)
          AND direction != 'ESPERAR'
          AND direction != 'FILTERED'
    """, (f"-{days} days",))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    overall   = _calc_stats(rows)
    by_strat  = {}
    strategies = {r["strategy"] for r in rows}
    for strat in sorted(strategies):
        subset = [r for r in rows if r["strategy"] == strat]
        by_strat[strat] = _calc_stats(subset)

    return {"overall": overall, "by_strategy": by_strat, "days": days}


def _calc_stats(rows):
    total   = len(rows)
    wins    = sum(1 for r in rows if r["outcome"] == "WIN")
    losses  = sum(1 for r in rows if r["outcome"] == "LOSS")
    pending = sum(1 for r in rows if r["outcome"] is None)
    resolved = wins + losses
    wr      = (wins / resolved * 100) if resolved > 0 else 0.0
    pnls    = [r["outcome_pnl"] for r in rows if r["outcome_pnl"] is not None]
    avg_pnl = sum(pnls) / len(pnls) if pnls else 0.0
    return {
        "total": total, "wins": wins, "losses": losses,
        "pending": pending, "win_rate": round(wr, 1), "avg_pnl": round(avg_pnl, 2)
    }


def format_winrate_telegram(days: int = 30) -> str:
    """Ready-to-send HTML message for /winrate command."""
    stats = get_winrate_stats(days)
    ov    = stats["overall"]
    by_s  = stats["by_strategy"]

    wr_emoji = "🟢" if ov["win_rate"] >= 55 else "🟡" if ov["win_rate"] >= 45 else "🔴"

    lines = [
        f"📊 <b>WIN RATE — últimos {days} días</b>\n",
        f"{wr_emoji} <b>General: {ov['win_rate']}%</b>  "
        f"({ov['wins']}W / {ov['losses']}L / {ov['pending']} pendientes)",
        f"📈 PnL promedio: <b>{ov['avg_pnl']:+.2f}%</b>  |  Total señales: <b>{ov['total']}</b>",
        "",
        "<b>Por estrategia:</b>",
    ]

    emoji_map = {
        "V1-TECH":  "⚡", "V1-SHORT": "📉", "V3-REV":  "🔄",
        "V4-EMA":   "🎯", "V2-AI":    "🤖", "SALMOS":  "🔔",
        "STOCK":    "📈", "WEBHOOK":  "📡",
    }

    for strat, s in by_s.items():
        if s["total"] == 0:
            continue
        icon = emoji_map.get(strat, "•")
        wr_col = "✅" if s["win_rate"] >= 55 else "⚠️" if s["win_rate"] >= 45 else "❌"
        lines.append(
            f"{icon} <b>{strat}</b>: {wr_col} {s['win_rate']}%  "
            f"({s['wins']}W/{s['losses']}L)  avg {s['avg_pnl']:+.2f}%"
        )

    if not by_s:
        lines.append("Sin señales registradas aún.")

    lines += [
        "",
        "<i>Señales pendientes se resuelven automáticamente al tocar TP/SL.</i>",
    ]
    return "\n".join(lines)


# ── Read helpers ───────────────────────────────────────────────────────────────

def get_similar_episodes(symbol, rsi, usdt_d, n=5):
    """Return up to n completed episodes matching RSI ±8 and usdt_d ±0.5."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT ts, direction, rsi, usdt_d, outcome, outcome_pnl, confluence
        FROM signal_episodes
        WHERE symbol = ?
          AND rsi     BETWEEN ? AND ?
          AND usdt_d  BETWEEN ? AND ?
          AND outcome IS NOT NULL
        ORDER BY ts DESC
        LIMIT ?
    """, (symbol, rsi - 8, rsi + 8, usdt_d - 0.5, usdt_d + 0.5, n))
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


def format_for_prompt(symbol, rsi, usdt_d, n=5):
    """Formatted string of similar past episodes for AI prompt injection."""
    episodes = get_similar_episodes(symbol, rsi, usdt_d, n)
    header = f"PRECEDENTES ({symbol} — últimas {n} condiciones similares):"
    if not episodes:
        return f"{header}\nSin precedentes registrados aún."
    lines = [header]
    for ep in episodes:
        try:
            ts_short = ep["ts"][11:16]
        except (TypeError, IndexError):
            ts_short = "??"
        pnl = ep["outcome_pnl"]
        pnl_str = f"{pnl:+.1f}%" if pnl is not None else "n/a"
        lines.append(
            f"• [{ts_short}] RSI {ep['rsi']:.1f} USDT.D {ep['usdt_d']:.2f}%"
            f" → {ep['direction']} → {ep['outcome']} ({pnl_str})"
        )
    return "\n".join(lines)


# Initialize table on import
init_episode_table()
