"""episode_memory.py — Episodic memory for Zenith Trading Suite."""

import sqlite3
from datetime import datetime, timezone

DB_FILE = "trades.db"


def init_episode_table():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS signal_episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            symbol TEXT,
            strategy TEXT,
            direction TEXT,
            rsi REAL,
            usdt_d REAL,
            bb_pos TEXT,
            ema_trend TEXT,
            confluence INTEGER,
            atr_pct REAL,
            outcome TEXT DEFAULT NULL,
            outcome_pnl REAL DEFAULT NULL,
            outcome_filled_at TEXT DEFAULT NULL
        )
    """)
    conn.commit()
    conn.close()


def log_episode(symbol, strategy, direction, rsi, usdt_d, bb_pos, ema_trend, confluence, atr_pct):
    """Insert one episode row. Returns the inserted row id."""
    ts = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO signal_episodes
            (ts, symbol, strategy, direction, rsi, usdt_d, bb_pos, ema_trend, confluence, atr_pct)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (ts, symbol, strategy, direction, rsi, usdt_d, bb_pos, ema_trend, confluence, atr_pct),
    )
    episode_id = c.lastrowid
    conn.commit()
    conn.close()
    return episode_id


def fill_outcome(episode_id, outcome, pnl_pct):
    """Update outcome fields for a previously logged episode."""
    filled_at = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        """
        UPDATE signal_episodes
        SET outcome = ?, outcome_pnl = ?, outcome_filled_at = ?
        WHERE id = ?
        """,
        (outcome, pnl_pct, filled_at, episode_id),
    )
    conn.commit()
    conn.close()


def get_similar_episodes(symbol, rsi, usdt_d, n=5):
    """Return up to n completed episodes matching RSI ±8 and usdt_d ±0.5, newest first."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """
        SELECT ts, direction, rsi, usdt_d, outcome, outcome_pnl, confluence
        FROM signal_episodes
        WHERE symbol = ?
          AND rsi BETWEEN ? AND ?
          AND usdt_d BETWEEN ? AND ?
          AND outcome IS NOT NULL
        ORDER BY ts DESC
        LIMIT ?
        """,
        (symbol, rsi - 8, rsi + 8, usdt_d - 0.5, usdt_d + 0.5, n),
    )
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


def format_for_prompt(symbol, rsi, usdt_d, n=5):
    """Return a formatted string of similar past episodes for AI prompt injection."""
    episodes = get_similar_episodes(symbol, rsi, usdt_d, n)
    header = f"PRECEDENTES ({symbol} — últimas {n} condiciones similares):"
    if not episodes:
        return f"{header}\nSin precedentes registrados aún."

    lines = [header]
    for ep in episodes:
        try:
            ts_short = ep["ts"][11:16]  # HH:MM from ISO string
        except (TypeError, IndexError):
            ts_short = "??"
        pnl = ep["outcome_pnl"]
        pnl_str = f"{pnl:+.1f}%" if pnl is not None else "n/a"
        lines.append(
            f"• [{ts_short}] RSI {ep['rsi']:.1f} USDT.D {ep['usdt_d']:.2f}%"
            f" → {ep['direction']} → {ep['outcome']} ({pnl_str})"
        )
    return "\n".join(lines)


# Initialize table on import (mirrors tracker.py pattern)
init_episode_table()
