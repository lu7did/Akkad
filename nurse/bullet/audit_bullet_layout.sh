#!/usr/bin/env bash
# Read-only check of the split Akkad source / external Bullet runtime layout.
set -Eeuo pipefail
BASE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$BASE/bullet_runtime.sh"
fail=0
check_file() {
  local f="$1"
  if [[ -s "$f" ]];then echo "✅ $f";else echo "❌ FALTA $f";fail=1;fi
}
echo "Fuentes Akkad: $BASE"
for s in run_genesis.sh run_genesis_bnn.sh run_genesis_mcts.sh picobit_pipeline.sh;do check_file "$BASE/$s";done
for s in grumpy_genesis/grumpy_train.rs grumpy_genesis/grumpy_validate.rs \
  grumpy_genesis/grumpy_export.py bnn_genesis/bnn_train.rs \
  bnn_genesis/bnn_validate.rs bnn_genesis/bnn_export.py \
  mcts_genesis/mcts_data.rs mcts_genesis/mcts_train.rs \
  mcts_genesis/mcts_validate.rs mcts_genesis/mcts_export.py \
  mcts_genesis/mcts_audit.py;do check_file "$BASE/$s";done
if ! bullet_resolve_runtime "$BASE";then exit 2;fi
echo "Instalación Bullet: $BULLET_DIR"
echo "Resultados Akkad: $BASE/runs"
for id in grumpy-bullet-001 bnn-bullet-001 mcts-bullet-rust-001 picobit-nnue-003;do
  if [[ -e "$BULLET_DIR/runs/$id/MON.state" && ! -e "$BASE/runs/$id/MON.state" ]];then
    echo "⚠️ Corrida histórica pendiente de migrar: $id"
    echo "    bash migrate_bullet_runs.sh --run $id"
  fi
done
for x in cargo python3 git;do
 if command -v "$x" >/dev/null;then echo "✅ $x: $(command -v "$x")";else echo "❌ FALTA ejecutable: $x";fail=1;fi
done
for f in pico_bit_train.rs pico_bit_validate.rs pico_bit_parity.rs;do
 if [[ -s "$BASE/picobit_genesis/$f" ]];then
  echo "✅ plantilla Akkad: $f"
 elif [[ -s "$BULLET_DIR/examples/$f" ]];then
  echo "⚠️ Plantilla aún solo en Bullet: $f (se importará cuando se ejecute picobit_pipeline.sh)"
 else
  echo "❌ Plantilla picoBit ausente en Akkad Y Bullet: $f";fail=1
 fi
done
TRAIN_DATA="${TRAIN_DATA:-$HOME/stockfish/test79-may2022-16tb7p-filter-v6-dd.min-mar2023.unmin.high-simple-eval-1k.min-v2.binpack}"
VALID_DATA="${VALID_DATA:-$HOME/stockfish/test77-jan2022-2tb7p.high-simple-eval-1k.min-v2.binpack}"
check_file "$TRAIN_DATA";check_file "$VALID_DATA"
if ((fail));then echo '❌ Layout incompleto. Revisar los elementos faltantes.' >&2;exit 2;fi
printf '\n✅ Preflight de rutas correcto (NO ejecutó Cargo, GPU ni entrenamiento).\n'
