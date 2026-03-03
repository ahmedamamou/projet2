#!/bin/bash
# run_simulation.sh — Run Cooja smart farm simulation
# Usage: ./run_simulation.sh [10|25|50] [loss_rate]

NODES=${1:-10}
LOSS_RATE=${2:-0}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
SIM_DIR="$REPO_DIR/cooja/simulations"
COOJA_DIR="${COOJA_DIR:-$HOME/contiki-ng/tools/cooja}"

# Select simulation file
case $NODES in
    10) SIM_FILE="$SIM_DIR/smart_farm_10nodes.csc" ;;
    25) SIM_FILE="$SIM_DIR/smart_farm_25nodes.csc" ;;
    50) SIM_FILE="$SIM_DIR/smart_farm_50nodes.csc" ;;
    *)  echo "Invalid node count. Use 10, 25, or 50."; exit 1 ;;
esac

echo "Starting Cooja simulation: $NODES nodes, loss_rate=$LOSS_RATE%"
echo "Simulation file: $SIM_FILE"

if [ ! -f "$COOJA_DIR/build/libs/cooja.jar" ]; then
    echo "ERROR: Cooja not found at $COOJA_DIR"
    echo "Set COOJA_DIR to your Contiki-NG tools/cooja directory"
    exit 1
fi

java -jar "$COOJA_DIR/build/libs/cooja.jar" \
    -nogui="$SIM_FILE" \
    -contiki="$HOME/contiki-ng" \
    2>&1 | tee "$REPO_DIR/results/cooja_${NODES}nodes_loss${LOSS_RATE}.log"
