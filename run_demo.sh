#!/usr/bin/env bash
# =============================================================================
# IGNITE Medical Suite v12.3.4.81 · Standalone Showcase Launcher
# Fuer Fedora Linux, Ubuntu/Debian, Android (Termux) & macOS
# Jugend forscht 2026 · Fachgebiet Arbeitswelt
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "======================================================"
echo " IGNITE Medical Suite v12.3.4.81 · Standalone Showcase"
echo " Jugend forscht 2026 · Fachgebiet Arbeitswelt"
echo "======================================================"
echo ""

PYTHON_BIN=""

# 1. Pruefe Python 3
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
fi

# 2. Ausfuehrung
if [ -n "$PYTHON_BIN" ]; then
    echo "[OK] Python Runtime gefunden: $($PYTHON_BIN --version 2>&1)"
    echo "Starte interaktiven Showcase Server..."
    echo ""
    "$PYTHON_BIN" "$SCRIPT_DIR/standalone_demo.py" "$@"
else
    echo "[HINWEIS] Kein Python auf diesem System gefunden."
    echo "Oeffne Standalone Offline HTML-Showcase im Browser..."
    echo ""
    
    HTML_FILE="$SCRIPT_DIR/docs/STANDALONE_DEMO_OFFLINE.html"
    
    # Browser oeffnen je nach OS (Fedora/Linux, Termux, macOS)
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$HTML_FILE"
    elif command -v termux-open-url >/dev/null 2>&1; then
        termux-open-url "$HTML_FILE"
    elif command -v gio >/dev/null 2>&1; then
        gio open "$HTML_FILE"
    elif command -v open >/dev/null 2>&1; then
        open "$HTML_FILE"
    else
        echo "Bitte oeffne folgende Datei manuell in deinem Webbrowser:"
        echo "  $HTML_FILE"
    fi
fi
