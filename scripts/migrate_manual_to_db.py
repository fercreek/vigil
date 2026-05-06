#!/usr/bin/env python3
"""
migrate_manual_to_db.py — One-shot migration: manual_positions.json → trades.db

Corre UNA vez. Idempotente: no duplica si ya existe registro para el mismo
símbolo con is_manual=1 y status OPEN. Archiva el JSON como .archived.

Uso:
    cd /path/to/scalp_bot
    python3 scripts/migrate_manual_to_db.py
"""

import json
import os
import sys
import sqlite3
from datetime import datetime

# Asegurar que podamos importar tracker desde raíz del bot
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

JSON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "manual_positions.json")
DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trades.db")


def run():
    if not os.path.exists(JSON_PATH):
        print(f"✅ {JSON_PATH} no existe — nada que migrar.")
        return

    with open(JSON_PATH) as f:
        positions = json.load(f)

    if not positions:
        print("✅ JSON vacío — nada que migrar.")
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    migrated = 0
    skipped = 0

    for pos in positions:
        sym = pos.get("symbol", "").upper()
        side = pos.get("side", "LONG").upper()
        entry = pos.get("entry", 0.0)
        active = pos.get("active", True)

        if not sym or not entry:
            print(f"  ⚠️  Saltando posición inválida: {pos}")
            continue

        if not active:
            print(f"  ⏭️  {sym} inactiva en JSON — omitiendo")
            continue

        # Idempotency: skip si ya existe trade manual abierto para este símbolo
        c.execute(
            "SELECT id FROM trades WHERE symbol = ? AND is_manual = 1 AND status IN ('OPEN', 'PARTIAL_WON')",
            (sym,)
        )
        if c.fetchone():
            print(f"  ⏭️  {sym} ya tiene trade manual OPEN en DB — skip")
            skipped += 1
            continue

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        open_time = pos.get("open_time", now)[:19]  # truncar ISO a datetime

        # Calcular SL/TP aproximados (5% / 10% si no hay datos)
        sl = round(entry * 0.92, 6) if side == "LONG" else round(entry * 1.08, 6)
        tp1 = round(entry * 1.05, 6) if side == "LONG" else round(entry * 0.95, 6)
        tp2 = round(entry * 1.10, 6) if side == "LONG" else round(entry * 0.90, 6)

        be_moved = 1 if pos.get("be_moved", False) else 0
        partial_pct = int(pos.get("partial_pct", 0))
        status = "PARTIAL_WON" if partial_pct > 0 else "OPEN"
        note = pos.get("size_note", "") or f"platform:{pos.get('platform','manual')}"
        events = pos.get("events", [])
        events_json = json.dumps(events) if events else None
        pnl_seed = pos.get("pnl_seed", 0.0)
        if pnl_seed:
            note = f"{note} | pnl_seed:{pnl_seed:.2f}"

        c.execute('''
            INSERT INTO trades (
                symbol, type, entry_price, tp1_price, tp2_price, sl_price,
                status, msg_id, open_time, strategy_version,
                alert_type, is_manual, be_moved, partial_pct, note, events_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
        ''', (
            sym, side, entry, tp1, tp2, sl,
            status, "migrated", open_time, "MANUAL",
            "manual_migrated", be_moved, partial_pct, note, events_json
        ))
        migrated += 1
        print(f"  ✅ {sym} {side} @ ${entry:.4f} → trades.db (id={c.lastrowid})")

    conn.commit()
    conn.close()

    print(f"\n📊 Resultado: {migrated} migrados, {skipped} saltados.")

    # Archivar JSON
    archived = JSON_PATH + ".archived"
    os.rename(JSON_PATH, archived)
    print(f"📦 JSON archivado en: {archived}")


if __name__ == "__main__":
    run()
