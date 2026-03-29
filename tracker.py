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
            strategy_version TEXT DEFAULT 'V1-TECH'
        )
    ''')
    # Migrate: add strategy_version if missing
    try:
        c.execute("ALTER TABLE trades ADD COLUMN strategy_version TEXT DEFAULT 'V1-TECH'")
        conn.commit()
    except Exception:
        pass

    # Tabla de sesiones de backtesting (resultados persistidos por día)
    c.execute('''
        CREATE TABLE IF NOT EXISTS backtest_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            version TEXT NOT NULL,
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
            open_time TEXT,
            close_time TEXT,
            duration_min INTEGER,
            pivot_r1 REAL,
            pivot_s1 REAL,
            balance_before REAL,
            balance_after REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
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
            INSERT INTO backtest_sessions 
            (date, symbol, version, type, entry_price, close_price, sl, tp1, tp2,
             result, pnl_usd, pnl_pct, rsi_entry, bb_status, alert_reason,
             open_time, close_time, duration_min, pivot_r1, pivot_s1,
             balance_before, balance_after)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            date_str, t.get('symbol',''), version, t.get('type',''),
            t.get('entry_price'), t.get('close_price'), t.get('sl'), t.get('tp1'), t.get('tp2'),
            result, round(pnl, 2), t.get('pnl_pct', 0),
            t.get('rsi_entry'), t.get('bb_status'), t.get('alert_reason'),
            t.get('open_time'), t.get('close_time'), t.get('duration_min', 0),
            t.get('pivot_r1'), t.get('pivot_s1'),
            bal_before, balance
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

def log_trade(symbol: str, type: str, entry: float, tp1: float, tp2: float, sl: float, msg_id: str = None, version: str = "V1-TECH"):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
        INSERT INTO trades (symbol, type, entry_price, tp1_price, tp2_price, sl_price, status, msg_id, open_time, strategy_version)
        VALUES (?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?)
    ''', (symbol, type, entry, tp1, tp2, sl, msg_id, now, version))
    conn.commit()
    trade_id = c.lastrowid
    conn.close()
    return trade_id

def get_open_trades():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, symbol, type, entry_price, tp1_price, tp2_price, sl_price, status, msg_id, strategy_version FROM trades WHERE status IN ('OPEN', 'PARTIAL_WON')")
    trades = c.fetchall()
    conn.close()
    
    result = []
    for t in trades:
        result.append({
            "id": t[0], "symbol": t[1], "type": t[2], 
            "entry_price": t[3], "tp1_price": t[4], "tp2_price": t[5], 
            "sl_price": t[6], "status": t[7], "msg_id": t[8], "version": t[9]
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

def get_all_trades():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, symbol, type, entry_price, tp1_price, tp2_price, sl_price, status, open_time, close_time, strategy_version FROM trades ORDER BY id DESC")
    trades = c.fetchall()
    conn.close()
    
    result = []
    for t in trades:
        result.append({
            "id": t[0], "symbol": t[1], "type": t[2], 
            "entry_price": t[3], "tp1_price": t[4], "tp2_price": t[5], 
            "sl_price": t[6], "status": t[7], "open_time": t[8], "close_time": t[9],
            "version": t[10]
        })
    return result

# Inicializar BD al cargar el módulo
init_db()
