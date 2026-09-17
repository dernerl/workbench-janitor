#!/bin/zsh
# Start/Stop-Wrapper für das statische Localhost-Dashboard (dashboard/index.html).
# Serviert per `python3 -m http.server`, PID in .dashboard.pid.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd "${0:A:h}" || exit 1

PORT="${JANITOR_DASHBOARD_PORT:-8934}"
PIDFILE=".dashboard.pid"
URL="http://localhost:$PORT/dashboard/"

is_running() {
    [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null
}

start() {
    if is_running; then
        return 0
    fi
    nohup python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1 &
    echo $! > "$PIDFILE"
    disown
}

stop() {
    if is_running; then
        kill "$(cat "$PIDFILE")" 2>/dev/null
    fi
    rm -f "$PIDFILE"
}

status() {
    if is_running; then
        echo "läuft (PID $(cat "$PIDFILE")) — $URL"
    else
        echo "gestoppt"
    fi
}

case "$1" in
    start)  start; echo "$URL" ;;
    stop)   stop ;;
    status) status ;;
    open)   start; open "$URL" ;;
    *) echo "Usage: $0 {start|stop|status|open}"; exit 1 ;;
esac
