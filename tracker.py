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
            close_time TEXT
        )
    ''')
    conn.commit()
    conn.close()

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
    base_query = "SELECT COUNT(*) FROM trades WHERE status = ? "
    params_fw = ['FULL_WON']
    params_pw = ['PARTIAL_WON'] # Simplificamos
    params_l = ['LOST']

    if version:
        base_query += "AND strategy_version = ?"
        params_fw.append(version)
        params_pw.append(version)
        params_l.append(version)

    c.execute(base_query, params_fw)
    full_won = c.fetchone()[0]
    
    c.execute(base_query.replace("status = ?", "status IN ('PARTIAL_WON', 'PARTIAL_CLOSED')"), params_pw)
    partial_won = c.fetchone()[0]
    
    c.execute(base_query, params_l)
    lost = c.fetchone()[0]
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
