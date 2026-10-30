cd ~/chess/akkad/AlphaZero

WEIGHTS="$HOME/chess/akkad/Sargon-NNUE/data/runs/lc0/t1-256x10-distilled-swa-2432500.pb.gz"

test -f "$WEIGHTS" || {
    echo "ERROR: No existe la red neuronal"
    exit 1
}

bash tools/bash/uci_smoke.sh "$WEIGHTS"
cd ~/chess/akkad/AlphaZero

WEIGHTS="$HOME/chess/akkad/Sargon-NNUE/data/runs/lc0/t1-256x10-distilled-swa-2432500.pb.gz"

test -f "$WEIGHTS" || {
    echo "ERROR: No existe la red neuronal"
    exit 1
}

bash tools/bash/uci_smoke.sh "$WEIGHTS"

