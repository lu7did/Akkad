#!/usr/bin/env bash
# Bullet-native, dual-head picoAlpha MCTS NNUE trainer. No SQLite or PyTorch.
set -Eeuo pipefail
BASE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${BASE}/bullet_runtime.sh"
bullet_resolve_runtime "${BASE}" || exit 2
RUN_ID="${RUN_ID:-mcts-bullet-rust-001}"
TRAIN_DATA="${TRAIN_DATA:-$HOME/stockfish/test79-may2022-16tb7p-filter-v6-dd.min-mar2023.unmin.high-simple-eval-1k.min-v2.binpack}"
VALID_DATA="${VALID_DATA:-$HOME/stockfish/test77-jan2022-2tb7p.high-simple-eval-1k.min-v2.binpack}"
SUPERBATCHES="${SUPERBATCHES:-100}";SAVE_EVERY="${SAVE_EVERY:-10}"
BATCH_SIZE="${BATCH_SIZE:-4096}";BATCHES_PER_SB="${BATCHES_PER_SB:-128}"
LR_START="${LR_START:-0.001}";LR_FINAL="${LR_FINAL:-0.0001}"
POLICY_WEIGHT="${POLICY_WEIGHT:-0.01}";CP_BLEND="${CP_BLEND:-1.0}"
VALID_COUNT="${VALID_COUNT:-200000}"
RUN_DIR="$(bullet_resolve_run_dir "$BASE" "$RUN_ID")"; CHECKPOINTS="$RUN_DIR/checkpoints"
STATE="$RUN_DIR/MON.state";LOCK="$RUN_DIR/config.lock"
TRAIN_EX=mcts_picoalpha_bullet_train;VALID_EX=mcts_picoalpha_bullet_validate
MON_FLAG='';STATUS=0
usage(){ cat <<'EOF'
Uso: ./run_genesis_mcts.sh [--mon 1..6] [--status] [--help]
Se ejecuta desde akkad/nurse/bullet; Bullet/Cargo/Metal siguen instalados fuera de Akkad. Requiere Rust/Cargo con Metal, Python3 y
T79/T77 binpack. No usa PyTorch, SQLite ni el código de entrenamiento picoAlpha.

MON=1 verifica dataset, dependencias y congela configuración
MON=2 instala 2 ejemplos Rust + módulo compartido y compila con Metal
MON=3 entrena 780x16 + from[64],to[64],value[1] con 2 pérdidas
MON=4 valida checkpoints cuantizados INT8 sobre T77
MON=5 exporta el mejor checkpoint a PANNI8 + header ARM
MON=6 audita el archivo exportado (pesos y predicciones)
MON=7 terminado; el estado se conserva automáticamente.

Variables: BULLET_DIR RUN_ID TRAIN_DATA VALID_DATA SUPERBATCHES SAVE_EVERY
BATCH_SIZE BATCHES_PER_SB LR_START LR_FINAL POLICY_WEIGHT CP_BLEND VALID_COUNT
Los pesos se exportan a akkad/nurse/bullet/runs/$RUN_ID/export/best_int8.bin y
akkad/nurse/bullet/runs/$RUN_ID/export/picoalpha_nnue_weights.hpp.
POLICY_WEIGHT regula CE(from)+CE(to); CP_BLEND=1 solo puntuación cp;
CP_BLEND=0 solo resultado final. Las etiquetas de política vienen del `mv`
registrado en el binpack (NO son visitas MCTS ni MultiPV Stockfish).

Cambiar la configuración de una ejecución requiere un RUN_ID distinto.
EOF
}
while (($#));do
 case "$1" in
 --mon) (($#>=2))|| { echo '--mon requires N' >&2;exit 2; };MON_FLAG="$2";shift 2;;
 --status)STATUS=1;shift;;
 --help|-h)usage;exit 0;;
 *)echo "Unknown argument $1" >&2;usage;exit 2;;
 esac
done
[[ "$RUN_ID" =~ ^[A-Za-z][A-Za-z0-9_-]*$ ]]|| { echo 'RUN_ID inválido' >&2;exit 2; }
for n in "$SUPERBATCHES" "$SAVE_EVERY" "$BATCH_SIZE" "$BATCHES_PER_SB" "$VALID_COUNT";do
 [[ "$n" =~ ^[1-9][0-9]*$ ]]|| { echo "Número inválido: $n" >&2;exit 2; }
done
((SAVE_EVERY<=SUPERBATCHES))|| { echo 'SAVE_EVERY > SUPERBATCHES' >&2;exit 2; }
[[ -d "$BULLET_DIR/crates/bullet_lib" ]]|| { echo "Bullet no encontrado: $BULLET_DIR" >&2;exit 2; }
mkdir -p "$RUN_DIR" "$CHECKPOINTS" "$RUN_DIR/export"
if [[ -n "$MON_FLAG" ]];then MON="$MON_FLAG";elif [[ -s "$STATE" ]];then MON="$(cat "$STATE")";else MON=1;fi
[[ "$MON" =~ ^[1-7]$ ]]|| { echo "MON inválido: $MON" >&2;exit 2; }
config(){ cat <<EOF
VERSION=rust-bullet-picoalpha-v0.1.0
RUN_ID=$RUN_ID
BULLET_DIR=$BULLET_DIR
TRAIN_DATA=$TRAIN_DATA
VALID_DATA=$VALID_DATA
SUPERBATCHES=$SUPERBATCHES
SAVE_EVERY=$SAVE_EVERY
BATCH_SIZE=$BATCH_SIZE
BATCHES_PER_SB=$BATCHES_PER_SB
LR_START=$LR_START
LR_FINAL=$LR_FINAL
POLICY_WEIGHT=$POLICY_WEIGHT
CP_BLEND=$CP_BLEND
VALID_COUNT=$VALID_COUNT
EOF
}
if [[ -s "$LOCK" ]] && ! config | cmp -s - "$LOCK";then
 echo "Configuración incompatible con $LOCK; usar otro RUN_ID" >&2;exit 2
fi
if ((STATUS));then
 echo "RESULTADOS_AKKAD=$RUN_DIR"
 echo "RUN_ID=$RUN_ID MON=$MON";echo "CHECKPOINTS=$CHECKPOINTS"
 find "$CHECKPOINTS" -maxdepth 1 -type d -name "$RUN_ID-*" -print 2>/dev/null|sort -V||true
 echo "OUTPUT=$RUN_DIR/export/best_int8.bin";exit 0
fi
trap 'echo "FALLO MON=$MON; estado conservado. Reanudar con ./run_genesis_mcts.sh" >&2' ERR
next(){ local nn=$((MON+1));printf '%s\n' "$nn" > "$STATE.tmp";mv "$STATE.tmp" "$STATE";echo "✅ MON=$MON -> MON=$nn";MON=$nn; }
check(){
 [[ -s "$TRAIN_DATA" && -s "$VALID_DATA" ]]|| { echo 'No se encuentran T79/T77' >&2;exit 2; }
 for f in mcts_data.rs mcts_train.rs mcts_validate.rs mcts_export.py mcts_audit.py;do
 [[ -s "$BASE/mcts_genesis/$f" ]]|| { echo "Falta $f" >&2;exit 2; };done
 command -v cargo >/dev/null;command -v python3 >/dev/null;command -v git >/dev/null
}
export MCTS_ID="$RUN_ID" MCTS_TRAIN="$TRAIN_DATA" MCTS_VALID="$VALID_DATA" MCTS_CHECKPOINTS="$CHECKPOINTS"
export MCTS_SUPERBATCHES="$SUPERBATCHES" MCTS_SAVE_EVERY="$SAVE_EVERY"
export MCTS_BATCH="$BATCH_SIZE" MCTS_BATCHES_PER_SB="$BATCHES_PER_SB"
export MCTS_LR_START="$LR_START" MCTS_LR_FINAL="$LR_FINAL" MCTS_POLICY_WEIGHT="$POLICY_WEIGHT"
export MCTS_CP_BLEND="$CP_BLEND" MCTS_VALID_COUNT="$VALID_COUNT" MCTS_VALID_CSV="$RUN_DIR/validation.csv"
cd "$BULLET_DIR"
if ((MON<=1));then
 echo '⚙️ MON=1 — verificar T79/T77 y dependencias'
 check
 git rev-parse HEAD > "$RUN_DIR/bullet_commit.txt"
 echo "Bullet commit=$(cat "$RUN_DIR/bullet_commit.txt")"
 echo "T79=$TRAIN_DATA";echo "T77=$VALID_DATA"
 # Don't silently use a different baseline from the one inspected.
 [[ "$(cat "$RUN_DIR/bullet_commit.txt")" == 5d70177680437b7c0ddf958bd4722d95afa78b0c ]] || {
 echo 'ADVERTENCIA: Bullet no coincide con commit auditado 5d70177; revisar API si falla la compilación.' >&2; }
 if [[ ! -e "$LOCK" ]];then config > "$LOCK.tmp";mv "$LOCK.tmp" "$LOCK";fi
 printf '1\n' > "$STATE";next
fi
if ((MON<=2));then
 echo '⚙️ MON=2 — instalar ejemplos Rust y compilar con Metal'
 check
 mkdir -p examples/mcts_picoalpha_bullet
 cp -- "$BASE/mcts_genesis/mcts_data.rs" "examples/mcts_picoalpha_bullet/mcts_data.rs"
 bullet_install_example "$TRAIN_EX" "$BASE/mcts_genesis/mcts_train.rs"
 bullet_install_example "$VALID_EX" "$BASE/mcts_genesis/mcts_validate.rs"
 cargo build --release --locked -p bullet_lib --example "$TRAIN_EX" --features metal
 cargo build --release --locked -p bullet_lib --example "$VALID_EX" --features metal
 # Rust unit tests are attached to the module; run them in both examples.
 cargo test --locked -p bullet_lib --example "$TRAIN_EX" --features metal
 next
fi
if ((MON<=3));then
 echo '⚙️ MON=3 — entrenamiento Dual Head (Rust + Metal)'
 start=1;resume=''
 for ((i=SAVE_EVERY;i<=SUPERBATCHES;i+=SAVE_EVERY));do
   d="$CHECKPOINTS/$RUN_ID-$i"
   if [[ -s "$d/raw.bin" && -s "$d/optimiser_state/weights.bin" ]];then start=$((i+1));resume="$d";fi
 done
 if [[ -s "$CHECKPOINTS/$RUN_ID-$SUPERBATCHES/raw.bin" ]];then echo 'Checkpoint final existente';else
   export MCTS_START_SB="$start" MCTS_RESUME_FROM="$resume"
   echo "Checkpoint reanudación=${resume:-ninguno}; comienzo SB=$start"
   "target/release/examples/$TRAIN_EX" 2>&1 | tee -a "$RUN_DIR/train.log"
 fi
 [[ -s "$CHECKPOINTS/$RUN_ID-$SUPERBATCHES/raw.bin" ]]|| { echo 'Falta checkpoint final' >&2;exit 3; }
 next
fi
if ((MON<=4));then
 echo '⚙️ MON=4 — validar checkpoints INT8 T77: valor y política'
 "target/release/examples/$VALID_EX" 2>&1 | tee "$RUN_DIR/validation.log"
 [[ -s "$RUN_DIR/validation.csv" ]]|| { echo 'Falta CSV validación' >&2;exit 3; }
 next
fi
if ((MON<=5));then
 echo '⚙️ MON=5 — seleccionar y exportar mejor red PANNI8'
 python3 "$BASE/mcts_genesis/mcts_export.py" --csv "$RUN_DIR/validation.csv" --checkpoints "$CHECKPOINTS" \
   --id "$RUN_ID" --out "$RUN_DIR/export"
 [[ "$(wc -c < "$RUN_DIR/export/best_int8.bin"|tr -d ' ')" == 14580 ]]|| { echo 'PANNI8 tamaño inválido' >&2;exit 3; }
 next
fi
if ((MON<=6));then
 echo '⚙️ MON=6 — auditoría exportado vs checkpoint y verificación de contrato'
 BEST="$(python3 - "$RUN_DIR/export/report.json" <<'PY'
import json,sys
print(json.load(open(sys.argv[1]))['best_superbatch'])
PY
)"
 python3 "$BASE/mcts_genesis/mcts_audit.py" --binary "$RUN_DIR/export/best_int8.bin" \
  --source "$CHECKPOINTS/$RUN_ID-$BEST/raw.bin" --out "$RUN_DIR/export/audit.json"
 next
fi
if ((MON==7));then
 echo "✅ Génesis MCTS completo: $RUN_DIR/export/best_int8.bin"
 echo "✅ Header ARM: $RUN_DIR/export/picoalpha_nnue_weights.hpp"
 echo "📊 $RUN_DIR/export/report.json"
fi
