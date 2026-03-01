#!/usr/bin/env bash
# =============================================================================
# stop.sh — Arrêt propre du framework AgriSem
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "============================================="
echo "  AgriSem Framework — Arrêt"
echo "============================================="

# Arrêt du serveur Flask
if [ -f "$SCRIPT_DIR/server.pid" ]; then
    PID=$(cat "$SCRIPT_DIR/server.pid")
    if kill -0 "$PID" 2>/dev/null; then
        echo "[*] Arrêt du serveur Flask (PID $PID)..."
        kill "$PID"
        rm -f "$SCRIPT_DIR/server.pid"
        echo "[✓] Serveur Flask arrêté"
    else
        echo "[!] Le serveur Flask n'est pas en cours d'exécution"
        rm -f "$SCRIPT_DIR/server.pid"
    fi
else
    echo "[!] Fichier server.pid non trouvé"
fi

# Arrêt de Docker Compose
if command -v docker-compose &>/dev/null || command -v docker &>/dev/null; then
    echo "[*] Arrêt de Fuseki (Docker)..."
    cd "$SCRIPT_DIR"
    if command -v docker-compose &>/dev/null; then
        docker-compose down 2>/dev/null || true
    else
        docker compose down 2>/dev/null || true
    fi
    echo "[✓] Fuseki arrêté"
fi

echo ""
echo "[✓] AgriSem Framework arrêté proprement."
