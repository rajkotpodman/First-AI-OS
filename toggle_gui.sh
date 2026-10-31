#!/bin/sh
# ==============================================================================
# toggle_gui.sh - On-Demand Dynamic GUI Switcher Script for AI OS
# Author: Linux Desktop Environment & Display Server Engineer
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXPANDER="${SCRIPT_DIR}/src/gui_expander.py"
[ ! -f "${EXPANDER}" ] && EXPANDER="/usr/local/bin/gui_expander.py"

case "$1" in
    --enable|start|on)
        echo "[*] Activating AI OS Graphical Desktop..."
        python3 "${EXPANDER}" --enable
        ;;
    --disable|stop|off|exit)
        echo "[*] Terminating Graphical Desktop and reverting to pure TTY CLI..."
        python3 "${EXPANDER}" --disable
        ;;
    --status)
        python3 "${EXPANDER}" --status
        ;;
    *)
        echo "Usage: $0 {--enable|start | --disable|stop | --status}"
        echo "Examples:"
        echo "  $0 --enable   # Download & launch Sway/Wayland minimal desktop"
        echo "  $0 --disable  # Terminate desktop compositor and revert to TTY"
        echo "  $0 --status   # Check display compositor status"
        exit 1
        ;;
esac
