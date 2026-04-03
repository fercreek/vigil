#!/usr/bin/env bash
# 🛑 Zenith Shutdown: Stop Scalp Bot safely
# --------------------------------------------------

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT/logs/bot.pid"

if [[ -f "$PID_FILE" ]]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null; then
        echo "🛑 Deteniendo Zenith (PID: $PID)..."
        kill "$PID"
        
        # Esperar a que se limpie el puerto 8080 si es necesario
        for i in {1..5}; do
            if ! ps -p "$PID" > /dev/null; then
                break
            fi
            sleep 1
        done
        
        # Limpieza forzada de puerto si es necesario
        lsof -ti :8080 | xargs kill -9 2>/dev/null || true
        
        echo "✅ Zenith detenido."
    else
        echo "⚠️ El proceso con PID $PID no existe."
    fi
    rm "$PID_FILE"
else
    # Intento de limpieza por puerto
    PORT_PID=$(lsof -ti :8080)
    if [[ -n "$PORT_PID" ]]; then
        echo "⚠️ No se encontró PID_FILE, pero hay un proceso en :8080 (PID: $PORT_PID). Deteniendo..."
        kill -9 "$PORT_PID"
        echo "✅ Proceso en :8080 detenido."
    else
        echo "⚠️ Zenith no parece estar corriendo."
    fi
fi
