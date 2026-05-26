"""
dashboard_metrics.py — Spec 015 Live Metrics Dashboard

Funciones reutilizables para consultar trades.db y producir métricas que el
panel HTML (`/dashboard/live`) y los endpoints JSON renderizan.

Diseño:
- SQL aislado del layer Flask (testeable / reutilizable).
- Conexión efímera por llamada (SQLite + threads de Flask = evitar shared cursor).
- Cada función envuelta en try/except → retorna dict / list vacíos en error.
  Razón: dashboard nunca debe tirar 500 por DB temporalmente locked.
- LIMIT en todas las queries (anticipando >10k rows futuros).
- DB path resuelto contra __file__ (consistente con fix Spec 002 ai_budget.py).
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Any

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trades.db')

# Statuses considerados ganadores / perdedores en tabla `trades`
WIN_STATUSES = ('FULL_WON', 'WON', 'PARTIAL_CLOSED')
LOSS_STATUSES = ('LOST',)


@contextmanager
def _conn():
    """Conexión sqlite efímera. Read-only mode (uri=True) para safety."""
    conn = None
    try:
        if not os.path.exists(DB_PATH):
            yield None
            return
        conn = sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True, timeout=2.0)
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _wr_pct(wins: int, losses: int) -> float:
    total = wins + losses
    if total == 0:
        return 0.0
    return round((wins / total) * 100, 1)


def compute_global_wr() -> Dict[str, Any]:
    """Win rate global sobre tabla trades."""
    try:
        with _conn() as c:
            if c is None:
                return {'global_wr': 0.0, 'wins': 0, 'losses': 0, 'total': 0, 'error': 'db_missing'}
            cur = c.execute(
                "SELECT status, COUNT(*) AS n FROM trades GROUP BY status"
            )
            counts = {row['status']: row['n'] for row in cur.fetchall()}
            wins = sum(counts.get(s, 0) for s in WIN_STATUSES)
            losses = sum(counts.get(s, 0) for s in LOSS_STATUSES)
            total = sum(counts.values())
            return {
                'global_wr': _wr_pct(wins, losses),
                'wins': wins,
                'losses': losses,
                'total': total,
                'open': total - wins - losses,
            }
    except Exception as e:
        return {'global_wr': 0.0, 'wins': 0, 'losses': 0, 'total': 0, 'error': str(e)}


def compute_wr_by_symbol() -> Dict[str, Dict[str, Any]]:
    """WR + last trade date por símbolo. Retorna dict {symbol: {...}}."""
    try:
        with _conn() as c:
            if c is None:
                return {}
            cur = c.execute("""
                SELECT
                    symbol,
                    SUM(CASE WHEN status IN ('FULL_WON','WON','PARTIAL_CLOSED') THEN 1 ELSE 0 END) AS wins,
                    SUM(CASE WHEN status='LOST' THEN 1 ELSE 0 END) AS losses,
                    COUNT(*) AS total,
                    MAX(open_time) AS last_trade
                FROM trades
                WHERE symbol IS NOT NULL AND symbol != ''
                GROUP BY symbol
                ORDER BY total DESC
                LIMIT 50
            """)
            out = {}
            for row in cur.fetchall():
                sym = row['symbol']
                wins, losses = row['wins'] or 0, row['losses'] or 0
                out[sym] = {
                    'wins': wins,
                    'losses': losses,
                    'total': row['total'] or 0,
                    'wr': _wr_pct(wins, losses),
                    'last_trade': row['last_trade'] or '',
                }
            return out
    except Exception as e:
        return {'_error': str(e)}


def compute_wr_by_strategy() -> Dict[str, Dict[str, Any]]:
    """WR por strategy_version (V1-TECH, V2-AI, SWING, COMMODITY, MANUAL...)."""
    try:
        with _conn() as c:
            if c is None:
                return {}
            cur = c.execute("""
                SELECT
                    COALESCE(strategy_version, 'UNKNOWN') AS strat,
                    SUM(CASE WHEN status IN ('FULL_WON','WON','PARTIAL_CLOSED') THEN 1 ELSE 0 END) AS wins,
                    SUM(CASE WHEN status='LOST' THEN 1 ELSE 0 END) AS losses,
                    COUNT(*) AS total,
                    MAX(open_time) AS last_trade
                FROM trades
                GROUP BY strat
                ORDER BY total DESC
                LIMIT 20
            """)
            out = {}
            for row in cur.fetchall():
                strat = row['strat']
                wins, losses = row['wins'] or 0, row['losses'] or 0
                out[strat] = {
                    'wins': wins,
                    'losses': losses,
                    'total': row['total'] or 0,
                    'wr': _wr_pct(wins, losses),
                    'last_trade': row['last_trade'] or '',
                }
            return out
    except Exception as e:
        return {'_error': str(e)}


def get_recent_trades(n: int = 20) -> List[Dict[str, Any]]:
    """Últimos n trades ordenados por open_time DESC."""
    try:
        with _conn() as c:
            if c is None:
                return []
            n = max(1, min(int(n), 200))
            cur = c.execute("""
                SELECT id, symbol, type, entry_price, status, strategy_version,
                       open_time, close_time, conf_score, alert_type, is_manual
                FROM trades
                ORDER BY id DESC
                LIMIT ?
            """, (n,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        return [{'_error': str(e)}]


def get_signal_episodes_summary() -> Dict[str, Any]:
    """
    Summary de signal_episodes (Spec 002 — alertas huérfanas / sin outcome).
    outcome NULL = huérfana (alerta emitida, jamás vinculada a trade).
    """
    try:
        with _conn() as c:
            if c is None:
                return {'total': 0, 'outcome_breakdown': {}, 'by_source': {}, 'orphans': 0}
            # Breakdown por outcome
            cur = c.execute("""
                SELECT COALESCE(outcome, 'NONE') AS outcome, COUNT(*) AS n
                FROM signal_episodes
                GROUP BY outcome
            """)
            outcome_breakdown = {row['outcome']: row['n'] for row in cur.fetchall()}

            # Breakdown por source
            cur = c.execute("""
                SELECT COALESCE(source, 'UNKNOWN') AS source, COUNT(*) AS n
                FROM signal_episodes
                GROUP BY source
                ORDER BY n DESC
                LIMIT 20
            """)
            by_source = {row['source']: row['n'] for row in cur.fetchall()}

            total = sum(outcome_breakdown.values())
            orphans = outcome_breakdown.get('NONE', 0)
            return {
                'total': total,
                'outcome_breakdown': outcome_breakdown,
                'by_source': by_source,
                'orphans': orphans,
            }
    except Exception as e:
        return {'total': 0, 'outcome_breakdown': {}, 'by_source': {}, 'orphans': 0, 'error': str(e)}


def compute_wr_over_time(days: int = 30) -> List[Dict[str, Any]]:
    """Spec 020.6: WR diario para últimos `days` días.

    Agrupa trades cerrados (WIN/LOST) por DATE(open_time) y calcula WR diario.
    Días sin trades NO aparecen en el resultado (gaps en línea aceptables).

    Returns: list of dicts ordenado ASC por fecha:
        [{'date': 'YYYY-MM-DD', 'wr': 50.0, 'total': 4, 'wins': 2}, ...]
    """
    try:
        with _conn() as c:
            if c is None:
                return []
            days = max(1, min(int(days), 365))  # hard cap 1 año
            cur = c.execute("""
                SELECT
                    DATE(open_time) AS day,
                    SUM(CASE WHEN status IN ('FULL_WON','WON','PARTIAL_CLOSED') THEN 1 ELSE 0 END) AS wins,
                    SUM(CASE WHEN status='LOST' THEN 1 ELSE 0 END) AS losses,
                    COUNT(*) AS total
                FROM trades
                WHERE open_time IS NOT NULL
                  AND open_time >= date('now', ?)
                GROUP BY day
                ORDER BY day ASC
                LIMIT 60
            """, (f'-{days} days',))
            out = []
            for row in cur.fetchall():
                wins = row['wins'] or 0
                losses = row['losses'] or 0
                total = row['total'] or 0
                # WR sobre cerrados (wins+losses), no total — open trades no aportan.
                closed = wins + losses
                wr = _wr_pct(wins, losses) if closed > 0 else 0.0
                out.append({
                    'date': row['day'],
                    'wr': wr,
                    'total': total,
                    'wins': wins,
                    'losses': losses,
                })
            return out
    except Exception as e:
        return [{'_error': str(e)}]


def get_dashboard_snapshot() -> Dict[str, Any]:
    """Helper agregado — todo lo que el HTML server-side render necesita."""
    return {
        'wr': compute_global_wr(),
        'by_symbol': compute_wr_by_symbol(),
        'by_strategy': compute_wr_by_strategy(),
        'recent': get_recent_trades(20),
        'episodes': get_signal_episodes_summary(),
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


if __name__ == '__main__':
    # Smoke test directo
    import json
    print(json.dumps(get_dashboard_snapshot(), indent=2, default=str))
