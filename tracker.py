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

def log_trade(symbol: str, type: str, entry: float, tp1: float, tp2: float, sl: float, msg_id: str = None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
        INSERT INTO trades (symbol, type, entry_price, tp1_price, tp2_price, sl_price, status, msg_id, open_time)
        VALUES (?, ?, ?, ?, ?, ?, 'OPEN', ?, ?)
    ''', (symbol, type, entry, tp1, tp2, sl, msg_id, now))
    conn.commit()
    trade_id = c.lastrowid
    conn.close()
    return trade_id

def get_open_trades():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Obtenemos trades OPEN o PARTIAL_WON (ya tocaron TP1 pero siguen vivos para TP2 o SL de ganancia)
    c.execute("SELECT id, symbol, type, entry_price, tp1_price, tp2_price, sl_price, status, msg_id FROM trades WHERE status IN ('OPEN', 'PARTIAL_WON')")
    trades = c.fetchall()
    conn.close()
    
    result = []
    for t in trades:
        result.append({
            "id": t[0], "symbol": t[1], "type": t[2], 
            "entry_price": t[3], "tp1_price": t[4], "tp2_price": t[5], 
            "sl_price": t[6], "status": t[7], "msg_id": t[8]
        })
    return result

def update_trade_status(trade_id: int, status: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Si se cierra completo, añadimos close_time, sino solo actualizamos estado
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

def get_win_rate():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM trades WHERE status = 'FULL_WON'")
    full_won = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM trades WHERE status IN ('PARTIAL_WON', 'PARTIAL_CLOSED')")
    partial_won = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM trades WHERE status = 'LOST'")
    lost = c.fetchone()[0]
    conn.close()
    
    total = full_won + partial_won + lost
    return full_won, partial_won, lost, total

def get_all_trades():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, symbol, type, entry_price, tp1_price, tp2_price, sl_price, status, open_time, close_time FROM trades ORDER BY id DESC")
    trades = c.fetchall()
    conn.close()
    
    result = []
    for t in trades:
        result.append({
            "id": t[0], "symbol": t[1], "type": t[2], 
            "entry_price": t[3], "tp1_price": t[4], "tp2_price": t[5], 
            "sl_price": t[6], "status": t[7], "open_time": t[8], "close_time": t[9]
        })
    return result

# Inicializar BD al cargar el módulo
init_db()
