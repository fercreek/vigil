import sqlite3
from datetime import datetime
import os

DB_FILE = "trades.db"

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
        ("trigger_conditions", "TEXT DEFAULT NULL")
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
    conn.commit()
    conn.close()

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

def log_trade(symbol, type, entry, tp1, tp2, sl, msg_id, version="V1-TECH", rsi=0.0, bb="", atr=0.0, elliott="", score=0, ai_analysis="", macro_bias="", inst_score=0, alert_type="unknown", trigger_conditions=None):
    import json
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conditions_json = json.dumps(trigger_conditions) if trigger_conditions else None
    c.execute('''
        INSERT INTO trades (
            symbol, type, entry_price, tp1_price, tp2_price, sl_price, status, msg_id, open_time, strategy_version,
            rsi_entry, bb_status, atr, elliott_wave, conf_score, ai_analysis, macro_bias, inst_score, alert_type, trigger_conditions
        )
        VALUES (?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (symbol, type, entry, tp1, tp2, sl, msg_id, now, version, rsi, bb, atr, elliott, score, ai_analysis, macro_bias, inst_score, alert_type, conditions_json))
    conn.commit()
    trade_id = c.lastrowid
    conn.close()
    return trade_id

def get_open_trades():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT id, symbol, type, entry_price, tp1_price, tp2_price, sl_price, status, msg_id, strategy_version,
               rsi_entry, bb_status, atr, elliott_wave, conf_score, open_time
        FROM trades
        WHERE status IN ('OPEN', 'PARTIAL_WON')
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
            "open_time": t[15] or ""
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

def update_sl(trade_id: int, new_sl: float):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE trades SET sl_price = ? WHERE id = ?", (new_sl, trade_id))
    conn.commit()
    conn.close()

def get_win_rate(version: str = None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    def count_status(status_val, v):
        q = "SELECT COUNT(*) FROM trades WHERE status = ?"
        p = [status_val]
        if v:
            q += " AND strategy_version = ?"
            p.append(v)
        c.execute(q, p)
        return c.fetchone()[0]

    full_won = count_status('FULL_WON', version)
    
    # Para Partial Won (especial)
    q_pw = "SELECT COUNT(*) FROM trades WHERE status IN ('PARTIAL_WON', 'PARTIAL_CLOSED')"
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

def get_alert_stats():
    """Desglose de win rate por tipo de alerta (alert_type) para comparar estrategias."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT alert_type, strategy_version, symbol, status, COUNT(*) as n
        FROM trades
        WHERE status IN ('FULL_WON', 'PARTIAL_WON', 'PARTIAL_CLOSED', 'LOST')
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
    c.execute("SELECT status, type FROM trades WHERE status IN ('FULL_WON', 'LOST', 'PARTIAL_CLOSED', 'PARTIAL_WON')")
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


# Inicializar BD al cargar el módulo
init_db()
