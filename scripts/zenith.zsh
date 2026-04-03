#!/usr/bin/env zsh
# 🛰️ Zenith Zsh Integration: Custom command for Scalp Bot
# --------------------------------------------------

export ZENITH_ROOT="${ZENITH_ROOT:-$HOME/Documents/ideas/scalp_bot}"

zenith-up() {
    (cd "$ZENITH_ROOT" && bash ./scripts/up.sh)
}

zenith-down() {
    (cd "$ZENITH_ROOT" && bash ./scripts/down.sh)
}

zenith-status() {
    local PID_FILE="$ZENITH_ROOT/logs/bot.pid"
    if [[ -f "$PID_FILE" ]]; then
        local PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null; then
            echo "✅ Zenith Scalp Bot (PID: $PID) - Activo."
            echo "   • Dashboard: http://localhost:8080"
        else
            echo "⚠️ Zenith Scalp Bot (PID: $PID) - Inactivo (PID no detectado)."
            echo "   • Intenta: 'zenith down' y 'zenith up'."
        fi
    else
        # Verificar por puerto si no hay PID_FILE
        local PORT_PID=$(lsof -ti :8080)
        if [[ -n "$PORT_PID" ]]; then
            echo "✅ Zenith Scalp Bot (PID: $PORT_PID) - Activo en puerto :8080."
        else
            echo "❌ Zenith Scalp Bot - Apagado."
        fi
    fi
}

zenith-logs() {
    tail -f "$ZENITH_ROOT/logs/bot.log"
}

zenith-open() {
    open "http://localhost:8080"
}

zenith-help() {
    echo "🛰️  Zenith Scalp Bot - Comandos"
    echo "------------------------------"
    echo "  zenith up      Inicia el bot en segundo plano (background)"
    echo "  zenith down    Detiene el bot de forma segura"
    echo "  zenith status  Muestra el estado actual del proceso"
    echo "  zenith logs    Muestra el log de actividad en vivo"
    echo "  zenith open    Abre el Dashboard en el navegador"
    echo "  zenith hub     Va al directorio del proyecto"
}

zenith() {
    case "${1:-}" in
        ""|help|-h|--help)
            zenith-help
            ;;
        up)
            zenith-up
            ;;
        down)
            zenith-down
            ;;
        status|st)
            zenith-status
            ;;
        logs|l)
            zenith-logs
            ;;
        open)
            zenith-open
            ;;
        hub|cd)
            cd "$ZENITH_ROOT"
            ;;
        *)
            echo "Comando desconocido: $1"
            zenith-help
            return 1
            ;;
    esac
}

# Alias directos opcionales
alias zup='zenith up'
alias zdown='zenith down'
alias zst='zenith status'
alias zl='zenith logs'
