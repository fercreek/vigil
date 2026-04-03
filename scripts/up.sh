#!/usr/bin/env bash
# 🚀 Zenith Launcher: Start Scalp Bot in the background
# --------------------------------------------------

# 1. Rutas del Entorno
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGS="$ROOT/logs"
PID_FILE="$LOGS/bot.pid"
VENV="$ROOT/venv/bin/python3"

mkdir -p "$LOGS"

# 2. Verificar si ya está corriendo
if [[ -f "$PID_FILE" ]]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null; then
        echo "⚠️ Zenith ya está corriendo (PID: $PID). Usa 'zenith down' antes."
        exit 1
    fi
    rm "$PID_FILE"
fi

# 3. Lanzar Bot en Background (&)
echo "🚀 Iniciando Zenith Scalp Bot (Background)..."
cd "$ROOT"

# Usamos nohup para que persista tras cerrar la terminal
# Redireccionamos stdout y stderr a logs/bot.log
nohup "$VENV" main.py >> "$LOGS/bot.log" 2>&1 &

# Guardar PID
echo $! > "$PID_FILE"

# 4. Feedback al usuario
echo "✅ Zenith iniciado correctamente."
echo "   • PID: $(cat "$PID_FILE")"
echo "   • Logs: $LOGS/bot.log"
echo "   • Dashboard: http://localhost:8080"
echo ""
echo "Usa 'zenith logs' para ver la actividad."
