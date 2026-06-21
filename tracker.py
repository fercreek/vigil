import sqlite3
from datetime import datetime
import os

DB_FILE = os.getenv("TRACKER_DB", "trades.db")

# Plan Fénix F0.1 — persistencia. En Railway montar Volume en /data y setear
# TRACKER_DB=/data/trades.db para que el histórico sobreviva redeploys.
# Garantizar que el directorio del path exista (sqlite no crea dirs).
_db_dir = os.path.dirname(DB_FILE)
if _db_dir and not os.path.exists(_db_dir):
    os.makedirs(_db_dir, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            type TEXT,
            entry_price REAL,
            tp1_price REAL,
            tp2_price REAL,
            sl_price REAL,
            status TEXT,
            msg_id TEXT,
            open_time TEXT,
            close_time TEXT,
            strategy_version TEXT DEFAULT 'V1-TECH',
            rsi_entry REAL,
            bb_status TEXT,
            atr REAL,
            elliott_wave TEXT,
            conf_score INTEGER
        )
    ''')
    # Migrate: add columns if missing
    columns = [
        ("strategy_version", "TEXT DEFAULT 'V1-TECH'"),
        ("rsi_entry", "REAL"),
        ("bb_status", "TEXT"),
        ("atr", "REAL"),
        ("elliott_wave", "TEXT"),
        ("conf_score", "INTEGER"),
        ("ai_analysis", "TEXT"),
        ("macro_bias", "TEXT"),
        ("inst_score", "INTEGER"),
        ("alert_type", "TEXT DEFAULT 'unknown'"),
        ("trigger_conditions", "TEXT DEFAULT NULL"),
        ("is_manual", "INTEGER DEFAULT 0"),
        ("is_sim", "INTEGER DEFAULT 0"),
        ("be_moved", "INTEGER DEFAULT 0"),
        ("partial_pct", "INTEGER DEFAULT 0"),
        ("events_json", "TEXT DEFAULT NULL"),
        ("note", "TEXT DEFAULT NULL"),
    ]
    for col, type_def in columns:
        try:
            c.execute(f"ALTER TABLE trades ADD COLUMN {col} {type_def}")
        except Exception:
            pass
    conn.commit()

    # Tabla de sesiones de backtesting (resultados persistidos por día)
    c.execute('''
        CREATE TABLE IF NOT EXISTS backtest_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            version TEXT,
            symbol TEXT,
            type TEXT,
            entry_price REAL,
            close_price REAL,
            sl REAL,
            tp1 REAL,
            tp2 REAL,
            result TEXT,
            pnl_usd REAL,
            pnl_pct REAL,
            rsi_entry REAL,
            bb_status TEXT,
            alert_reason TEXT,
            conf_score INTEGER,
            open_time TEXT,
            close_time TEXT,
            duration_min INTEGER,
            pivot_r1 REAL,
            pivot_s1 REAL,
            balance_before REAL,
            balance_after REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            elliott_wave TEXT DEFAULT 'Analizando...'
        )
    ''')
    try:
        c.execute("ALTER TABLE backtest_sessions ADD COLUMN elliott_wave TEXT DEFAULT 'Analizando...'")
    except:
        pass

    # Spec 022 (2026-05-26): A/B test framework para gates + boost intel.
    # Captura datos por cada alert enviada para correlacionar con outcome posterior.
    c.execute('''
        CREATE TABLE IF NOT EXISTS intel_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT DEFAULT CURRENT_TIMESTAMP,
            alert_id INTEGER,
            symbol TEXT,
            strategy TEXT,
            side TEXT,
            intel_json TEXT,
            gates_blocked_json TEXT,
            boost_applied REAL DEFAULT 0.0,
            boost_reasons TEXT,
            conf_score_pre REAL,
            conf_score_post REAL,
            entry_price REAL,
            sl_price REAL,
            tp1_price REAL,
            outcome TEXT DEFAULT NULL,
            outcome_pnl REAL DEFAULT NULL,
            outcome_filled_at TEXT DEFAULT NULL
        )
    ''')
    conn.commit()
    conn.close()


def log_intel_event(alert_id: int, symbol: str, strategy: str, side: str,
                    intel: dict, boost_applied: float = 0.0, boost_reasons: list | None = None,
                    conf_score_pre: float = 0.0, conf_score_post: float = 0.0,
                    entry: float = 0.0, sl: float = 0.0, tp1: float = 0.0,
                    gates_blocked: list | None = None) -> int | None:
    """Spec 022 (2026-05-26): registra evento de intel para A/B testing.

    Llamado POST gates (alert pasó) o cuando un gate bloqueó (gates_blocked != []).
    Outcome se rellena posteriormente via update_intel_outcome cuando trade cierra.

    Args:
        alert_id: ID del alert (msg_id Telegram o id de signal_episodes)
        symbol: e.g. "BTC/USDT"
        strategy: e.g. "v3_reversal", "v4", "swing"
        side: "LONG" / "SHORT"
        intel: dict completo del _extra_intel (HMM/CVD/Social/Whale)
        boost_applied: total boost aplicado al confluence (Spec 021)
        boost_reasons: lista de strings con razones del boost
        conf_score_pre: score antes del boost
        conf_score_post: score post boost
        entry/sl/tp1: niveles del trade
        gates_blocked: lista de nombres de gates que bloquearon (si la alerta no se envió)

    Returns:
        intel_outcomes.id si OK, None si error.
    """
    import json
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO intel_outcomes
            (alert_id, symbol, strategy, side, intel_json, gates_blocked_json,
             boost_applied, boost_reasons, conf_score_pre, conf_score_post,
             entry_price, sl_price, tp1_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            alert_id, symbol, strategy, side,
            json.dumps(intel or {}, ensure_ascii=False),
            json.dumps(gates_blocked or [], ensure_ascii=False),
            float(boost_applied or 0.0),
            ", ".join(boost_reasons or []),
            float(conf_score_pre or 0.0),
            float(conf_score_post or 0.0),
            float(entry or 0.0), float(sl or 0.0), float(tp1 or 0.0),
        ))
        new_id = c.lastrowid
        conn.commit()
        conn.close()
        return new_id
    except Exception as e:
        print(f"[intel_outcomes ERROR] {e}")
        return None


def _compute_pnl_pct(entry: float | None, sl: float | None, tp1: float | None,
                     outcome: str, side: str | None) -> float | None:
    """Spec 022.6 (2026-05-26): pure compute pnl_pct% según outcome/side.

    Estimación conservadora (no requiere close_price real):
      - WIN     → close = tp1            (asume hit TP1)
      - LOSS    → close = sl             (asume hit SL)
      - PARTIAL → close = midpoint(entry, tp1)   (estimación cauta)

    Formula:  pnl_pct = (close - entry) / entry * 100
    Si side == "SHORT" → invertir signo.

    Returns:
        float pnl_pct o None si datos insuficientes (entry <= 0 o tp1/sl missing donde aplica).
    """
    try:
        if not entry or entry <= 0:
            return None
        outcome_u = (outcome or "").upper()
        if outcome_u == "WIN":
            if not tp1 or tp1 <= 0:
                return None
            close = float(tp1)
        elif outcome_u == "LOSS":
            if not sl or sl <= 0:
                return None
            close = float(sl)
        elif outcome_u == "PARTIAL":
            if not tp1 or tp1 <= 0:
                return None
            close = (float(entry) + float(tp1)) / 2.0
        else:
            return None
        pnl_pct = (close - float(entry)) / float(entry) * 100.0
        if (side or "").upper() == "SHORT":
            pnl_pct *= -1.0
        return round(pnl_pct, 4)
    except Exception:
        return None


def update_intel_outcome(intel_id: int, outcome: str, pnl: float | None = None) -> bool:
    """Update outcome de un intel_outcomes row cuando trade cierra.

    Args:
        intel_id: id del row a actualizar
        outcome: "WIN" | "LOSS" | "PARTIAL"
        pnl: PnL del trade en USD o pct

    Returns:
        True si OK.
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            UPDATE intel_outcomes
            SET outcome = ?, outcome_pnl = ?, outcome_filled_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (outcome, pnl, intel_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[intel_outcomes UPDATE ERROR] {e}")
        return False


def get_intel_ab_stats() -> dict:
    """Spec 022: estadísticas A/B test gates + boost vs baseline.

    Returns dict:
        {
            'total': int,
            'with_outcome': int,
            'boost_segments': {
                'boost_0': {'count': N, 'wr': X.X},
                'boost_1+': {'count': N, 'wr': X.X},
                'boost_3+': {'count': N, 'wr': X.X},
            },
            'gates_blocked_count': int,
            'top_gates_blocking': [(gate_name, count), ...],
        }
    """
    import json
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        # Total + outcomes
        c.execute("SELECT COUNT(*) FROM intel_outcomes")
        total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM intel_outcomes WHERE outcome IS NOT NULL")
        with_outcome = c.fetchone()[0]
        # Gates blocked
        c.execute("SELECT COUNT(*) FROM intel_outcomes WHERE gates_blocked_json NOT IN ('[]', '', NULL)")
        gates_blocked_count = c.fetchone()[0]

        # WR por bucket de boost
        boost_segments = {}
        for label, condition in [
            ("boost_0", "boost_applied = 0"),
            ("boost_1+", "boost_applied >= 1.0"),
            ("boost_3+", "boost_applied >= 3.0"),
        ]:
            c.execute(f"SELECT COUNT(*) FROM intel_outcomes WHERE {condition}")
            cnt = c.fetchone()[0]
            c.execute(f"SELECT COUNT(*) FROM intel_outcomes WHERE {condition} AND outcome='WIN'")
            wins = c.fetchone()[0]
            wr = round(100.0 * wins / cnt, 1) if cnt > 0 else 0.0
            # Spec 022.6: PnL aggregates (avg + total) sobre outcome_pnl NOT NULL
            c.execute(f"SELECT AVG(outcome_pnl), SUM(outcome_pnl), COUNT(outcome_pnl) FROM intel_outcomes WHERE {condition} AND outcome_pnl IS NOT NULL")
            _avg, _total, _n = c.fetchone()
            avg_pnl_pct = round(float(_avg), 3) if _avg is not None else 0.0
            total_pnl_pct = round(float(_total), 3) if _total is not None else 0.0
            boost_segments[label] = {
                'count': cnt,
                'wr': wr,
                'avg_pnl_pct': avg_pnl_pct,
                'total_pnl_pct': total_pnl_pct,
                'pnl_n': int(_n or 0),
            }

        # Top gates blocking
        c.execute("SELECT gates_blocked_json FROM intel_outcomes WHERE gates_blocked_json NOT IN ('[]','',NULL)")
        gate_counter: dict = {}
        for (gj,) in c.fetchall():
            try:
                gates = json.loads(gj or "[]")
                for g in gates:
                    gate_counter[g] = gate_counter.get(g, 0) + 1
            except Exception:
                pass
        top_gates = sorted(gate_counter.items(), key=lambda x: -x[1])[:5]

        conn.close()
        return {
            'total': total,
            'with_outcome': with_outcome,
            'boost_segments': boost_segments,
            'gates_blocked_count': gates_blocked_count,
            'top_gates_blocking': top_gates,
        }
    except Exception as e:
        print(f"[intel_ab_stats ERROR] {e}")
        return {}

def save_backtest_session(date_str: str, version: str, trades: list, starting_balance: float = 1000.0):
    """Persiste los resultados de una simulación en la BD."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM backtest_sessions WHERE date = ? AND version = ?", (date_str, version))
    
    balance = starting_balance
    RISK = starting_balance * 0.01  # $10 por trade (1%)
    
    for t in trades:
        bal_before = balance
        result = t.get('result', '')
        
        # PnL real: WIN=2:1 R:R, LOST=1:1 riesgo, OPEN_EOD=movimiento real
        if result == 'WIN_FULL':
            pnl = RISK * 2.0          # +$20 (2:1 R:R)
        elif result == 'LOST':
            pnl = -RISK               # -$10
        elif result == 'OPEN_EOD':
            # Usar el pnl_usd calculado por la simulación (movimiento real)
            pnl = round(t.get('pnl_usd', 0), 2)
        else:
            pnl = 0
        
        balance = round(balance + pnl, 2)
        
        c.execute('''
            INSERT INTO backtest_sessions (
                date, version, symbol, type, entry_price, close_price, sl, tp1, tp2, 
                result, pnl_usd, pnl_pct, rsi_entry, bb_status, alert_reason, conf_score,
                open_time, close_time, duration_min, pivot_r1, pivot_s1, balance_before, balance_after,
                elliott_wave
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            date_str, version, t.get('symbol',''), t.get('type',''),
            t.get('entry_price'), t.get('close_price'), t.get('sl'), t.get('tp1'), t.get('tp2'),
            result, round(pnl, 2), t.get('pnl_pct', 0),
            t.get('rsi_entry'), t.get('bb_status'), t.get('alert_reason'), t.get('conf_score', 0),
            t.get('open_time'), t.get('close_time'), t.get('duration_min', 0),
            t.get('pivot_r1'), t.get('pivot_s1'),
            bal_before, balance,
            t.get('elliott', 'Analizando...')
        ))
    conn.commit()
    conn.close()

def get_backtest_session(date_str: str, version: str = None, symbol: str = None):
    """Recupera sesiones de backtesting guardadas."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    q = "SELECT * FROM backtest_sessions WHERE date = ?"
    params = [date_str]
    if version:
        q += " AND version = ?"
        params.append(version)
    if symbol and symbol != 'all':
        q += " AND symbol = ?"
        params.append(symbol)
    q += " ORDER BY open_time ASC"
    c.execute(q, params)
    cols = [desc[0] for desc in c.description]
    rows = [dict(zip(cols, row)) for row in c.fetchall()]
    conn.close()
    return rows

def get_backtest_days():
    """Lista los días únicos con sesiones guardadas."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT DISTINCT date, version, COUNT(*) as trades FROM backtest_sessions GROUP BY date, version ORDER BY date DESC")
    rows = [{"date": r[0], "version": r[1], "trades": r[2]} for r in c.fetchall()]
    conn.close()
    return rows

def log_trade(symbol, type, entry, tp1, tp2, sl, msg_id, version="V1-TECH", rsi=0.0, bb="", atr=0.0, elliott="", score=0, ai_analysis="", macro_bias="", inst_score=0, alert_type="unknown", trigger_conditions=None, is_manual=0, note=None):
    import json
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conditions_json = json.dumps(trigger_conditions) if trigger_conditions else None
    c.execute('''
        INSERT INTO trades (
            symbol, type, entry_price, tp1_price, tp2_price, sl_price, status, msg_id, open_time, strategy_version,
            rsi_entry, bb_status, atr, elliott_wave, conf_score, ai_analysis, macro_bias, inst_score, alert_type, trigger_conditions,
            is_manual, note
        )
        VALUES (?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (symbol, type, entry, tp1, tp2, sl, msg_id, now, version, rsi, bb, atr, elliott, score, ai_analysis, macro_bias, inst_score, alert_type, conditions_json, int(is_manual), note))
    conn.commit()
    trade_id = c.lastrowid
    conn.close()
    return trade_id


def update_trade_levels(trade_id: int, sl: float = None, tp1: float = None, tp2: float = None, entry: float = None):
    """Ajusta niveles de un trade abierto (SL/TP/entry)."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    sets, vals = [], []
    if sl is not None:
        sets.append("sl_price = ?"); vals.append(sl)
    if tp1 is not None:
        sets.append("tp1_price = ?"); vals.append(tp1)
    if tp2 is not None:
        sets.append("tp2_price = ?"); vals.append(tp2)
    if entry is not None:
        sets.append("entry_price = ?"); vals.append(entry)
    if sets:
        vals.append(trade_id)
        c.execute(f"UPDATE trades SET {', '.join(sets)} WHERE id = ?", vals)
        conn.commit()
    conn.close()


def mark_be(trade_id: int):
    """Marca be_moved=1 y mueve sl_price al entry_price."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE trades SET be_moved = 1, sl_price = entry_price WHERE id = ?", (trade_id,))
    conn.commit()
    conn.close()


def mark_partial(trade_id: int, pct: int):
    """Marca partial_pct y status PARTIAL_WON."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE trades SET partial_pct = ?, status = 'PARTIAL_WON' WHERE id = ?", (int(pct), trade_id))
    conn.commit()
    conn.close()


def append_event(trade_id: int, event: str):
    """Append event al events_json del trade."""
    import json as _json
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT events_json FROM trades WHERE id = ?", (trade_id,))
    row = c.fetchone()
    events = []
    if row and row[0]:
        try:
            events = _json.loads(row[0])
        except Exception:
            events = []
    events.append({"time": datetime.now().isoformat(), "event": event})
    c.execute("UPDATE trades SET events_json = ? WHERE id = ?", (_json.dumps(events), trade_id))
    conn.commit()
    conn.close()


def get_trade_by_id(trade_id: int) -> dict | None:
    """Recupera un trade por su ID primario."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT id, symbol, type, entry_price, tp1_price, tp2_price, sl_price,
               status, msg_id, open_time, is_manual, is_sim, be_moved, partial_pct, note
        FROM trades WHERE id = ?
    ''', (trade_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0], "symbol": row[1], "type": row[2],
        "entry_price": row[3], "tp1_price": row[4], "tp2_price": row[5], "sl_price": row[6],
        "status": row[7], "msg_id": row[8], "open_time": row[9],
        "is_manual": bool(row[10]), "is_sim": bool(row[11]),
        "be_moved": bool(row[12]), "partial_pct": row[13] or 0, "note": row[14],
    }


def log_simulated(symbol, side, entry, tp1, tp2, sl, msg_id, version="V1-TECH",
                  rsi=0.0, bb="", atr=0.0, score=0, alert_type="unknown",
                  trigger_conditions=None, macro_regime="") -> int:
    """
    Loguea señal como simulación (is_sim=1, status='OPEN').
    Usada cuando Fernando skipea una señal — el bot trackea si hubiera ganado.
    Win rate sim = trades con is_sim=1 cerrados; win rate real = is_sim=0.
    """
    import json
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    note_str = f"SIM | regime:{macro_regime}" if macro_regime else "SIM"
    conditions_json = json.dumps(trigger_conditions) if trigger_conditions else None
    c.execute('''
        INSERT INTO trades (
            symbol, type, entry_price, tp1_price, tp2_price, sl_price, status, msg_id, open_time,
            strategy_version, rsi_entry, bb_status, atr, conf_score, alert_type, trigger_conditions,
            is_manual, is_sim, note
        )
        VALUES (?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1, ?)
    ''', (symbol, side, entry, tp1, tp2, sl, msg_id, now,
          version, rsi, bb, atr, score, alert_type, conditions_json, note_str))
    conn.commit()
    trade_id = c.lastrowid
    conn.close()
    return trade_id


def get_open_manual_trades() -> list:
    """Trades manuales abiertos (is_manual=1, status OPEN o PARTIAL_WON)."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT id, symbol, type, entry_price, tp1_price, tp2_price, sl_price, status, msg_id, strategy_version,
               rsi_entry, bb_status, atr, elliott_wave, conf_score, open_time, be_moved, partial_pct, note, events_json
        FROM trades
        WHERE is_manual = 1 AND status IN ('OPEN', 'PARTIAL_WON')
        ORDER BY id DESC
    ''')
    rows = c.fetchall()
    conn.close()
    out = []
    for r in rows:
        out.append({
            "id": r[0], "symbol": r[1], "type": r[2],
            "entry_price": r[3], "tp1_price": r[4], "tp2_price": r[5], "sl_price": r[6],
            "status": r[7], "msg_id": r[8], "version": r[9],
            "rsi_entry": r[10], "bb_status": r[11], "atr": r[12], "elliott": r[13], "conf_score": r[14],
            "open_time": r[15] or "", "be_moved": bool(r[16]), "partial_pct": r[17] or 0,
            "note": r[18] or "", "events_json": r[19],
        })
    return out


def get_open_trade_by_symbol(symbol: str, manual_only: bool = False):
    """Trade abierto más reciente para un símbolo. manual_only=True filtra is_manual=1."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if manual_only:
        c.execute('''
            SELECT id, symbol, type, entry_price, tp1_price, tp2_price, sl_price, status, msg_id, open_time, be_moved, partial_pct
            FROM trades
            WHERE symbol = ? AND is_manual = 1 AND status IN ('OPEN', 'PARTIAL_WON')
            ORDER BY id DESC LIMIT 1
        ''', (symbol.upper(),))
    else:
        c.execute('''
            SELECT id, symbol, type, entry_price, tp1_price, tp2_price, sl_price, status, msg_id, open_time, be_moved, partial_pct
            FROM trades
            WHERE symbol = ? AND status IN ('OPEN', 'PARTIAL_WON')
            ORDER BY id DESC LIMIT 1
        ''', (symbol.upper(),))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0], "symbol": row[1], "type": row[2],
        "entry_price": row[3], "tp1_price": row[4], "tp2_price": row[5], "sl_price": row[6],
        "status": row[7], "msg_id": row[8], "open_time": row[9] or "",
        "be_moved": bool(row[10]), "partial_pct": row[11] or 0,
    }

def get_open_trades():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT id, symbol, type, entry_price, tp1_price, tp2_price, sl_price, status, msg_id, strategy_version,
               rsi_entry, bb_status, atr, elliott_wave, conf_score, open_time, is_manual, be_moved, partial_pct
        FROM trades
        WHERE status IN ('OPEN', 'PARTIAL_WON')
        ORDER BY id DESC
    ''')
    trades = c.fetchall()
    conn.close()

    result = []
    for t in trades:
        result.append({
            "id": t[0], "symbol": t[1], "type": t[2],
            "entry_price": t[3], "tp1_price": t[4], "tp2_price": t[5],
            "sl_price": t[6], "status": t[7], "msg_id": t[8], "version": t[9],
            "rsi_entry": t[10], "bb_status": t[11], "atr": t[12], "elliott": t[13], "conf_score": t[14],
            "open_time": t[15] or "",
            "is_manual": bool(t[16]), "be_moved": bool(t[17]), "partial_pct": t[18] or 0,
        })
    return result

def update_trade_status(trade_id: int, status: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if status in ['FULL_WON', 'LOST', 'PARTIAL_CLOSED']:
        c.execute("UPDATE trades SET status = ?, close_time = ? WHERE id = ?", (status, now, trade_id))
    else:
        c.execute("UPDATE trades SET status = ? WHERE id = ?", (status, trade_id))
    conn.commit()
    conn.close()

    # Spec 022.5 (2026-05-26): auto-update intel_outcomes outcome al cerrar trade.
    # Mapping status → outcome:
    #   FULL_WON / WON         → "WIN"
    #   PARTIAL_CLOSED / PARTIAL_WON → "PARTIAL"
    #   LOST                   → "LOSS"
    # PnL queda None — Spec 022.6 candidato computar % real cuando tp/sl/entry disponibles.
    try:
        _outcome_map = {
            "FULL_WON": "WIN",
            "WON": "WIN",
            "PARTIAL_CLOSED": "PARTIAL",
            "PARTIAL_WON": "PARTIAL",
            "LOST": "LOSS",
        }
        _outcome = _outcome_map.get(status)
        if _outcome is None:
            return
        # alert_id en intel_outcomes = trade.id (Spec 022 wire en strategies.py V3-REVERSAL)
        _conn = sqlite3.connect(DB_FILE)
        _c = _conn.cursor()
        # Solo update si todavía está sin outcome (evita sobreescribir update manual previo)
        _c.execute('''
            UPDATE intel_outcomes
            SET outcome = ?, outcome_filled_at = CURRENT_TIMESTAMP
            WHERE alert_id = ? AND outcome IS NULL
        ''', (_outcome, trade_id))
        _updated = _c.rowcount
        _conn.commit()
        if _updated > 0:
            print(f"📊 [intel_outcomes] auto-updated alert_id={trade_id} → {_outcome}")

        # Spec 022.6 (2026-05-26): compute pnl_pct real para rows recién marcados.
        # Query entry/sl/tp1/side, compute, UPDATE outcome_pnl WHERE NULL.
        try:
            _c.execute('''
                SELECT id, entry_price, sl_price, tp1_price, side
                FROM intel_outcomes
                WHERE alert_id = ? AND outcome = ? AND outcome_pnl IS NULL
            ''', (trade_id, _outcome))
            _rows = _c.fetchall()
            for _row_id, _entry, _sl, _tp1, _side in _rows:
                _pnl_pct = _compute_pnl_pct(_entry, _sl, _tp1, _outcome, _side)
                if _pnl_pct is None:
                    continue
                _c.execute('''
                    UPDATE intel_outcomes
                    SET outcome_pnl = ?
                    WHERE id = ?
                ''', (_pnl_pct, _row_id))
                print(f"📊 [intel_outcomes] pnl_pct alert_id={trade_id} (id={_row_id}, side={_side}) → {_pnl_pct:+.2f}%")
            _conn.commit()
        except Exception as _pe:
            print(f"[intel_outcomes pnl_pct ERROR] trade_id={trade_id}: {_pe}")

        _conn.close()
    except Exception as _e:
        print(f"[intel_outcomes auto-update ERROR] trade_id={trade_id}: {_e}")

def update_sl(trade_id: int, new_sl: float):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE trades SET sl_price = ? WHERE id = ?", (new_sl, trade_id))
    conn.commit()
    conn.close()

def get_win_rate(version: str = None):
    """Win rate de trades REALES (is_sim=0). Excluye señales skiadas (SIM)."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    SIM_FILTER = "AND (is_sim = 0 OR is_sim IS NULL)"

    def count_status(status_val, v):
        q = f"SELECT COUNT(*) FROM trades WHERE status = ? {SIM_FILTER}"
        p = [status_val]
        if v:
            q += " AND strategy_version = ?"
            p.append(v)
        c.execute(q, p)
        return c.fetchone()[0]

    full_won = count_status('FULL_WON', version)

    q_pw = f"SELECT COUNT(*) FROM trades WHERE status IN ('PARTIAL_WON', 'PARTIAL_CLOSED') {SIM_FILTER}"
    p_pw = []
    if version:
        q_pw += " AND strategy_version = ?"
        p_pw.append(version)
    c.execute(q_pw, p_pw)
    partial_won = c.fetchone()[0]

    lost = count_status('LOST', version)
    conn.close()

    total = full_won + partial_won + lost
    return full_won, partial_won, lost, total


def get_winrate_comparison() -> dict:
    """
    Compara win rate REAL (trades activados) vs SIM (señales skiadas).

    Real  = is_sim=0, status cerrado
    SIM   = is_sim=1, status cerrado
    Gap positivo → Fernando está skiando señales buenas (dejar pasar)
    Gap negativo → El filtro humano agrega valor (skipear fue correcto)
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    def _calc(sim_val: int) -> dict:
        c.execute('''
            SELECT
                SUM(CASE WHEN status IN ('FULL_WON','PARTIAL_WON','PARTIAL_CLOSED') THEN 1 ELSE 0 END),
                SUM(CASE WHEN status = 'LOST' THEN 1 ELSE 0 END),
                COUNT(*)
            FROM trades
            WHERE (is_sim = ? OR (? = 0 AND is_sim IS NULL))
              AND status IN ('FULL_WON','PARTIAL_WON','PARTIAL_CLOSED','LOST')
        ''', (sim_val, sim_val))
        row = c.fetchone()
        wins, losses, total = row[0] or 0, row[1] or 0, row[2] or 0
        wr = round(wins / total * 100, 1) if total > 0 else 0.0
        return {"wins": wins, "losses": losses, "total": total, "wr": wr}

    real = _calc(0)
    sim  = _calc(1)
    conn.close()

    gap = round(sim["wr"] - real["wr"], 1)
    verdict = ""
    if sim["total"] == 0:
        verdict = "Sin datos SIM aún — usa Skip en próximas señales"
    elif gap > 5:
        verdict = f"⚠️ Estás skiando señales buenas (+{gap}pp WR perdido)"
    elif gap < -5:
        verdict = f"✅ Tu filtro humano agrega valor ({gap}pp mejor que SIM)"
    else:
        verdict = f"↔️ Tus skips son neutrales (gap {gap:+.1f}pp)"

    return {"real": real, "sim": sim, "gap": gap, "verdict": verdict}

def get_alert_stats():
    """Desglose de win rate por tipo de alerta (alert_type). Solo trades REALES (is_sim=0)."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT alert_type, strategy_version, symbol, status, COUNT(*) as n
        FROM trades
        WHERE status IN ('FULL_WON', 'PARTIAL_WON', 'PARTIAL_CLOSED', 'LOST')
          AND (is_sim = 0 OR is_sim IS NULL)
        GROUP BY alert_type, strategy_version, symbol, status
    ''')
    rows = c.fetchall()
    conn.close()

    # Aggregate into {alert_type: {symbol: {wins, losses, total, wr}}}
    stats = {}
    for alert_type, version, symbol, status, n in rows:
        key = alert_type or 'unknown'
        if key not in stats:
            stats[key] = {"version": version, "by_symbol": {}, "total": {"wins": 0, "losses": 0}}
        if symbol not in stats[key]["by_symbol"]:
            stats[key]["by_symbol"][symbol] = {"wins": 0, "losses": 0}
        is_win = status in ('FULL_WON', 'PARTIAL_WON', 'PARTIAL_CLOSED')
        if is_win:
            stats[key]["by_symbol"][symbol]["wins"] += n
            stats[key]["total"]["wins"] += n
        else:
            stats[key]["by_symbol"][symbol]["losses"] += n
            stats[key]["total"]["losses"] += n

    result = []
    for alert_type, data in stats.items():
        total = data["total"]["wins"] + data["total"]["losses"]
        wr = round(data["total"]["wins"] / total * 100, 1) if total > 0 else 0.0
        result.append({
            "alert_type": alert_type,
            "version": data["version"],
            "total": total,
            "wins": data["total"]["wins"],
            "losses": data["total"]["losses"],
            "win_rate": wr,
            "by_symbol": data["by_symbol"]
        })
    return sorted(result, key=lambda x: x["total"], reverse=True)

def get_daily_pnl():
    """Obtiene operaciones cerradas HOY para PnL rápido."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    
    try:
        c.execute("SELECT status FROM trades WHERE (close_time LIKE ? OR open_time LIKE ?) AND status IN ('FULL_WON', 'LOST', 'PARTIAL_CLOSED', 'PARTIAL_WON')", (f"{today}%", f"{today}%"))
        trades = c.fetchall()
    except Exception as e:
        print(f"Db Error: {e}")
        trades = []
    finally:
        conn.close()
    
    wins = sum(1 for t in trades if t[0] in ['FULL_WON', 'PARTIAL_WON', 'PARTIAL_CLOSED'])
    losses = sum(1 for t in trades if t[0] == 'LOST')
    total = wins + losses
    win_rate = (wins / total * 100) if total > 0 else 0.0
    
    return {
        "wins": wins,
        "losses": losses,
        "total": total,
        "win_rate": win_rate
    }
def get_audit_metrics():
    """Calcula métricas profesionales de auditoría (Profit Factor, Win Rate, PnL Total)."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 1. Obtener todos los trades cerrados con PnL (simulando 1% riesgo por trade)
    # V13.5: Sincronizado con estados PARTIAL_WON de V12
    c.execute("SELECT status, type FROM trades WHERE status IN ('FULL_WON', 'LOST', 'PARTIAL_CLOSED', 'PARTIAL_WON') AND (is_sim = 0 OR is_sim IS NULL)")
    trades = c.fetchall()
    conn.close()
    
    wins = 0
    losses = 0
    gross_profit = 0.0
    gross_loss = 0.0
    
    for status, side in trades:
        if status == 'FULL_WON':
            wins += 1
            gross_profit += 2.0 # R:R 1:2
        elif status == 'LOST':
            losses += 1
            gross_loss += 1.0 # Riesgo 1.0
        elif status in ['PARTIAL_CLOSED', 'PARTIAL_WON']:
            wins += 1
            gross_profit += 1.0 # R:R 1:1 aproximado
            
    win_rate = (wins / len(trades) * 100) if trades else 0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)
    
    return {
        "total_trades": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate": f"{win_rate:.1f}%",
        "profit_factor": f"{profit_factor:.2f}",
        "status": "PROFESSIONAL" if profit_factor > 1.75 else "BULLISH" if profit_factor > 1.1 else "NEUTRAL"
    }

def get_all_trades(limit=50):
    import json
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT id, symbol, type, entry_price, tp1_price, tp2_price, sl_price, status, msg_id, open_time, close_time, strategy_version,
               rsi_entry, bb_status, atr, elliott_wave, conf_score, alert_type, trigger_conditions
        FROM trades
        ORDER BY id DESC LIMIT ?
    ''', (limit,))
    cols = [desc[0] for desc in c.description]
    rows = []
    for row in c.fetchall():
        d = dict(zip(cols, row))
        if d.get("trigger_conditions"):
            try:
                d["trigger_conditions"] = json.loads(d["trigger_conditions"])
            except Exception:
                pass
        rows.append(d)
    conn.close()
    return rows

def get_last_open_trade(symbol: str):
    """Recupera el trade más reciente en estado OPEN o PARTIAL_WON para un símbolo."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT id, symbol, type, entry_price, status, open_time, msg_id
        FROM trades 
        WHERE symbol = ? AND status IN ('OPEN', 'PARTIAL_WON')
        ORDER BY id DESC LIMIT 1
    ''', (symbol,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0], "symbol": row[1], "type": row[2],
            "entry_price": row[3], "status": row[4], "open_time": row[5], "msg_id": row[6]
        }
    return None

def get_recent_outcomes(n: int = 10) -> list:
    """
    Recupera los últimos N resultados de trades cerrados (para circuit breaker).
    Retorna lista de dicts con status y pnl estimado.
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT id, symbol, type, entry_price, sl_price, tp1_price, tp2_price, status, close_time
        FROM trades
        WHERE status IN ('FULL_WON', 'LOST', 'PARTIAL_WON', 'PARTIAL_CLOSED')
        ORDER BY id DESC LIMIT ?
    ''', (n,))
    rows = c.fetchall()
    conn.close()

    results = []
    for r in rows:
        entry = r[3] or 0
        sl = r[4] or 0
        tp1 = r[5] or 0
        status = r[7]

        # Estimar PnL % basado en status
        if entry > 0 and sl > 0:
            sl_dist = abs(entry - sl)
            if status == "FULL_WON":
                pnl_pct = (sl_dist * 2.0 / entry) * 100  # ~2:1 R:R
            elif status in ("PARTIAL_WON", "PARTIAL_CLOSED"):
                pnl_pct = (sl_dist * 1.0 / entry) * 100  # ~1:1 R:R
            elif status == "LOST":
                pnl_pct = -(sl_dist / entry) * 100
            else:
                pnl_pct = 0.0
        else:
            pnl_pct = 0.0

        results.append({
            "id": r[0],
            "symbol": r[1],
            "status": status,
            "pnl_pct": round(pnl_pct, 2),
            "is_win": status in ("FULL_WON", "PARTIAL_WON"),
            "close_time": r[8],
        })
    return results


def get_recent_closed_trades_by_symbol(sym: str, limit: int = 5, strategy: str = None) -> list:
    """
    Retorna los últimos N trades cerrados de un símbolo específico.
    Útil para detectar racha de pérdidas y aplicar cooldown automático.
    strategy: filtrar por strategy_version (e.g. "SWING", "V1-TECH")
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if strategy:
        c.execute('''
            SELECT id, symbol, status, open_time, close_time, strategy_version
            FROM trades
            WHERE symbol = ? AND strategy_version = ?
              AND status IN ('WON', 'FULL_WON', 'LOST', 'PARTIAL_WON', 'PARTIAL_CLOSED')
            ORDER BY id DESC LIMIT ?
        ''', (sym, strategy, limit))
    else:
        c.execute('''
            SELECT id, symbol, status, open_time, close_time, strategy_version
            FROM trades
            WHERE symbol = ?
              AND status IN ('WON', 'FULL_WON', 'LOST', 'PARTIAL_WON', 'PARTIAL_CLOSED')
            ORDER BY id DESC LIMIT ?
        ''', (sym, limit))
    rows = c.fetchall()
    conn.close()
    return [
        {"id": r[0], "symbol": r[1], "status": r[2],
         "open_time": r[3], "close_time": r[4], "version": r[5]}
        for r in rows
    ]


def get_today_trade_count(sym: str, strategy: str = None) -> int:
    """
    Cuenta trades abiertos HOY para un símbolo (sin importar si ganaron o perdieron).
    Útil para limitar max trades por día por símbolo.
    """
    from datetime import date
    today = date.today().isoformat()  # "2026-04-17"
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if strategy:
        c.execute('''
            SELECT COUNT(*) FROM trades
            WHERE symbol = ? AND strategy_version = ?
              AND open_time LIKE ?
        ''', (sym, strategy, f"{today}%"))
    else:
        c.execute('''
            SELECT COUNT(*) FROM trades
            WHERE symbol = ? AND open_time LIKE ?
        ''', (sym, f"{today}%"))
    count = c.fetchone()[0]
    conn.close()
    return count


# Inicializar BD al cargar el módulo
init_db()
