#!/usr/bin/env bash
# =============================================================================
# start.sh — Lancement unique du framework AgriSem
# Usage : ./start.sh [--live | --standalone]
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:---standalone}"
FUSEKI_URL="http://localhost:3030"
SERVER_PORT=12345
DATASET="agrisem"

echo "============================================="
echo "  AgriSem Framework — Démarrage"
echo "  Mode : $MODE"
echo "============================================="

# ── 1. Vérification des prérequis ─────────────────────────────────────────────
check_python() {
    if ! command -v python3 &>/dev/null; then
        echo "[ERREUR] Python 3 non trouvé. Installez Python 3.8+."
        exit 1
    fi
    PY_VERSION=$(python3 -c "import sys; print(sys.version_info.minor)")
    PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
    if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_VERSION" -lt 8 ]; }; then
        echo "[ERREUR] Python 3.8+ requis. Version actuelle : $(python3 --version)"
        exit 1
    fi
    echo "[✓] Python $(python3 --version) détecté"
}

check_docker() {
    if ! command -v docker &>/dev/null; then
        echo "[AVERTISSEMENT] Docker non trouvé. Fuseki ne sera pas lancé."
        echo "                Le framework fonctionnera sans persistance RDF."
        return 1
    fi
    if ! docker info &>/dev/null 2>&1; then
        echo "[AVERTISSEMENT] Docker daemon non démarré. Fuseki ne sera pas lancé."
        return 1
    fi
    echo "[✓] Docker disponible"
    return 0
}

check_python

DOCKER_AVAILABLE=false
if check_docker; then
    DOCKER_AVAILABLE=true
fi

# ── 2. Environnement virtuel Python ───────────────────────────────────────────
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
    echo "[*] Création de l'environnement virtuel Python..."
    python3 -m venv venv
fi

echo "[*] Activation du venv et installation des dépendances..."
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "[✓] Dépendances Python installées"

# ── 3. Lancement de Fuseki via Docker ─────────────────────────────────────────
if [ "$DOCKER_AVAILABLE" = true ]; then
    echo "[*] Lancement d'Apache Jena Fuseki..."
    if command -v docker-compose &>/dev/null; then
        docker-compose up -d
    else
        docker compose up -d
    fi

    # Attendre que Fuseki soit prêt
    echo "[*] Attente de Fuseki (max 60s)..."
    for i in $(seq 1 30); do
        if curl -sf "$FUSEKI_URL/\$/ping" &>/dev/null; then
            echo "[✓] Fuseki prêt"
            break
        fi
        if [ "$i" -eq 30 ]; then
            echo "[AVERTISSEMENT] Fuseki n'est pas prêt après 60s. Continuons sans persistance."
            DOCKER_AVAILABLE=false
        fi
        sleep 2
    done

    # ── 4. Créer le dataset agrisem ───────────────────────────────────────────
    if [ "$DOCKER_AVAILABLE" = true ]; then
        echo "[*] Création du dataset '$DATASET'..."
        curl -sf -X POST "$FUSEKI_URL/\$/datasets" \
            -H "Content-Type: application/x-www-form-urlencoded" \
            -u admin:admin \
            --data "dbName=$DATASET&dbType=tdb2" &>/dev/null || true
        echo "[✓] Dataset '$DATASET' prêt"

        # ── 5. Charger l'ontologie ────────────────────────────────────────────
        if [ -f "semantic/ontology.ttl" ]; then
            echo "[*] Chargement de l'ontologie..."
            curl -sf -X POST "$FUSEKI_URL/$DATASET/data" \
                -u admin:admin \
                -H "Content-Type: text/turtle" \
                --data-binary @semantic/ontology.ttl &>/dev/null || true
            echo "[✓] Ontologie chargée"
        fi
    fi
fi

# ── 6. Créer le dossier de résultats ──────────────────────────────────────────
mkdir -p results

# ── 7. Lancer le serveur Flask ────────────────────────────────────────────────
echo "[*] Démarrage du serveur AgriSem (port $SERVER_PORT)..."

if [ "$MODE" = "--live" ]; then
    AGRISEM_MODE=live python3 server.py &
else
    AGRISEM_MODE=standalone python3 server.py &
fi

SERVER_PID=$!
echo $SERVER_PID > "$SCRIPT_DIR/server.pid"

# Attendre que le serveur soit prêt
sleep 3
for i in $(seq 1 15); do
    if curl -sf "http://localhost:$SERVER_PORT/health" &>/dev/null; then
        echo "[✓] Serveur AgriSem prêt (PID $SERVER_PID)"
        break
    fi
    if [ "$i" -eq 15 ]; then
        echo "[ERREUR] Le serveur n'a pas démarré. Vérifiez les logs."
        exit 1
    fi
    sleep 1
done

# ── 8. Afficher les URLs ──────────────────────────────────────────────────────
echo ""
echo "============================================="
echo "  AgriSem Framework démarré !"
echo "============================================="
echo ""
echo "  🌾 Serveur principal  : http://localhost:$SERVER_PORT"
echo "  📊 Pipeline complet   : http://localhost:$SERVER_PORT/"
echo "  📈 Métriques          : http://localhost:$SERVER_PORT/metrics"
echo "  ❤️  Health check       : http://localhost:$SERVER_PORT/health"
if [ "$DOCKER_AVAILABLE" = true ]; then
    echo "  🗄️  Fuseki SPARQL     : $FUSEKI_URL"
    echo "  🔍 UI Fuseki         : $FUSEKI_URL/$DATASET"
fi
echo ""
echo "  Pour arrêter : ./stop.sh"
echo "============================================="

wait $SERVER_PID
