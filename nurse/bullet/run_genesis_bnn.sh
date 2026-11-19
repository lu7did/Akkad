#!/usr/bin/env bash
# Independent Bullet BNN genesis (Metal); never touches GRMP or Bashful.
set -Eeuo pipefail
BASE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${BASE}/bullet_runtime.sh"
bullet_resolve_runtime "${BASE}" || exit 2
RUN_ID="${RUN_ID:-bnn-bullet-001}"
TRAIN_DATA="${TRAIN_DATA:-$HOME/stockfish/test79-may2022-16tb7p-filter-v6-dd.min-mar2023.unmin.high-simple-eval-1k.min-v2.binpack}"
VALID_DATA="${VALID_DATA:-$HOME/stockfish/test77-jan2022-2tb7p.high-simple-eval-1k.min-v2.binpack}"
SUPERBATCHES="${SUPERBATCHES:-100}"
SAVE_EVERY="${SAVE_EVERY:-10}"
BATCH_SIZE="${BATCH_SIZE:-4096}"
BATCHES_PER_SB="${BATCHES_PER_SB:-256}"
LR_START="${LR_START:-0.001}"
LR_FINAL="${LR_FINAL:-0.0001}"
VALID_COUNT="${VALID_COUNT:-2000000}"
RUN_DIR="$(bullet_resolve_run_dir "$BASE" "$RUN_ID")"
CHECKPOINTS="$RUN_DIR/checkpoints"
STATE="$RUN_DIR/MON.state"
LOCK="$RUN_DIR/config.lock"
OUT="$RUN_DIR/${RUN_ID}.bnn"
REPORT="$RUN_DIR/report.json"
CSV="$RUN_DIR/validation.csv"
FINAL_CSV="$RUN_DIR/final_validation.csv"
TRAIN_EX="bnn_${RUN_ID//-/_}_train"
VALID_EX="bnn_${RUN_ID//-/_}_validate"

usage(){ cat <<'END'
Uso: bash run_genesis_bnn.sh [--mon 1..6] [--status] [--help]
MON 1: Verificación y bloqueo de entradas/configuración
MON 2: Instalación de ejemplos Rust aislados y compilación Metal
MON 3: Entrenamiento BNN con pesos maestros FP32 y forward binario/STE
MON 4: Validación independiente sobre T77 (pesos binarios reales)
MON 5: Selección y exportación a formato propio BULBNN01
MON 6: Verificación de bytes + inferencia final y reporte
MON 7: completado
Para retomar: bash run_genesis_bnn.sh (sin --mon).
Para evaluar FEN tras terminar:
  python3 bnn_genesis/bnn_export.py --verify runs/bnn-bullet-001/bnn-bullet-001.bnn \
      --fen 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
Variables: BULLET_DIR RUN_ID TRAIN_DATA VALID_DATA SUPERBATCHES SAVE_EVERY
 BATCH_SIZE BATCHES_PER_SB LR_START LR_FINAL VALID_COUNT
ATENCIÓN: .bnn NO es grumpy.bin. No lo carga Nurse/picoSargon sin un evaluador BNN.
END
}
CLI=""; STATUS=0
while (($#));do
 case "$1" in
   --mon) (($#>=2)) || { echo 'Falta valor --mon' >&2; exit 2; };CLI="$2";shift 2;;
   --status)STATUS=1;shift;;
   --help|-h)usage; exit 0;;
   *)echo "Argumento no reconocido: $1" >&2;usage; exit 2;;
 esac
done
[[ "$RUN_ID" =~ ^[A-Za-z][A-Za-z0-9_-]*$ ]] || { echo 'RUN_ID inválido' >&2; exit 2; }
for n in "$SUPERBATCHES" "$SAVE_EVERY" "$BATCH_SIZE" "$BATCHES_PER_SB" "$VALID_COUNT";do
 [[ "$n" =~ ^[1-9][0-9]*$ ]] || { echo "Entero inválido: $n" >&2; exit 2; }
done
[[ "$SAVE_EVERY" -le "$SUPERBATCHES" ]] || { echo 'SAVE_EVERY > SUPERBATCHES' >&2; exit 2; }
[[ -d "$BULLET_DIR/crates/bullet_lib" ]] || { echo "No encuentro Bullet: $BULLET_DIR" >&2; exit 2; }
mkdir -p "$RUN_DIR" "$CHECKPOINTS"
if [[ -n "$CLI" ]];then MON="$CLI";elif [[ -s "$STATE" ]];then MON="$(cat "$STATE")";else MON=1;fi
[[ "$MON" =~ ^[1-7]$ ]] || { echo "MON inválido: $MON" >&2; exit 2; }
config(){ cat <<END
VERSION=bnn-genesis-v0.1.0
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
VALID_COUNT=$VALID_COUNT
END
}
if [[ -f "$LOCK" ]] && ! config | cmp -s - "$LOCK";then
 echo "❌ Parámetros diferentes de $LOCK; usar RUN_ID nuevo o recuperar configuración original" >&2; exit 2
fi
if ((STATUS));then
 echo "RESULTADOS_AKKAD=$RUN_DIR"
 echo "RUN_ID=$RUN_ID MON=$MON"
 echo "CHECKPOINTS=$CHECKPOINTS"
 find "$CHECKPOINTS" -maxdepth 1 -type d -name "$RUN_ID-*" -print 2>/dev/null|sort -V || true
 echo "BIN=$OUT"; exit 0
fi
if ((MON==7));then echo "✅ Ya completado: $OUT"; exit 0;fi
trap 'echo "❌ Interrumpido/falló MON=$MON. Reanudar con bash run_genesis_bnn.sh" >&2' ERR
next(){ local nn=$((MON+1));printf '%s\n' "$nn" > "$STATE.tmp";mv "$STATE.tmp" "$STATE";echo "✅ MON=$MON -> MON=$nn";MON=$nn; }
check(){
 [[ -s "$TRAIN_DATA" && -s "$VALID_DATA" ]] || { echo 'Falta T79 o T77: configurar TRAIN_DATA/VALID_DATA' >&2; exit 2; }
 for f in bnn_train.rs bnn_validate.rs bnn_export.py;do
  [[ -s "$BASE/bnn_genesis/$f" ]] || { echo "Falta $f" >&2; exit 2; }
 done
 command -v cargo >/dev/null;command -v python3 >/dev/null
}
export BNN_RUN_ID="$RUN_ID" BNN_TRAIN="$TRAIN_DATA" BNN_VALID="$VALID_DATA"
export BNN_CHECKPOINTS="$CHECKPOINTS" BNN_SUPERBATCHES="$SUPERBATCHES" BNN_SAVE_EVERY="$SAVE_EVERY"
export BNN_BATCH="$BATCH_SIZE" BNN_BATCHES_PER_SB="$BATCHES_PER_SB"
export BNN_LR_START="$LR_START" BNN_LR_FINAL="$LR_FINAL" BNN_VALID_COUNT="$VALID_COUNT"
export BNN_VALID_CSV="$CSV"
cd "$BULLET_DIR"
if ((MON<=1));then
 echo '⚙️ MON=1 — entradas y configuración BNN'
 check
 git rev-parse HEAD > "$RUN_DIR/bullet_commit.txt"
 echo "Bullet commit: $(cat "$RUN_DIR/bullet_commit.txt")"
 echo "T79: $TRAIN_DATA";echo "T77: $VALID_DATA"
 if [[ ! -e "$LOCK" ]];then config > "$LOCK.tmp";mv "$LOCK.tmp" "$LOCK";fi
 printf '1\n' > "$STATE";next
fi
if ((MON<=2));then
 echo '⚙️ MON=2 — ejemplos Rust y compilación Metal'
 check
 # Only BNN-prefixed files, no replacement of prior Rust examples.
 bullet_install_example "$TRAIN_EX" "$BASE/bnn_genesis/bnn_train.rs"
 bullet_install_example "$VALID_EX" "$BASE/bnn_genesis/bnn_validate.rs"
 cargo build --release --locked -p bullet_lib --example "$TRAIN_EX" --features metal
 cargo build --release --locked -p bullet_lib --example "$VALID_EX" --features metal
 next
fi
if ((MON<=3));then
 echo '⚙️ MON=3 — entrenamiento binario STE en GPU'
 start=1;resume=''
 for ((i=SAVE_EVERY;i<=SUPERBATCHES;i+=SAVE_EVERY));do
  d="$CHECKPOINTS/$RUN_ID-$i"
  if [[ -s "$d/raw.bin" && -s "$d/optimiser_state/weights.bin" ]];then start=$((i+1));resume="$d";fi
 done
 if [[ -s "$CHECKPOINTS/$RUN_ID-$SUPERBATCHES/raw.bin" ]];then
  echo "✅ Checkpoint final existe ($SUPERBATCHES)"
 else
  export BNN_START_SB="$start" BNN_RESUME_FROM="$resume"
  echo "Retomar en superbatch $start; optimizador: ${resume:-nuevo}"
  "target/release/examples/$TRAIN_EX" 2>&1|tee -a "$RUN_DIR/training.log"
 fi
 [[ -s "$CHECKPOINTS/$RUN_ID-$SUPERBATCHES/raw.bin" ]] || { echo 'No se guardó el checkpoint final' >&2; exit 3; }
 next
fi
if ((MON<=4));then
 echo '⚙️ MON=4 — validación T77 de BNN real'
 BNN_VALID_CSV="$CSV" "target/release/examples/$VALID_EX" 2>&1|tee "$RUN_DIR/validation.log"
 [[ -s "$CSV" ]] || { echo 'No se generó validation.csv' >&2; exit 3; }
 next
fi
if ((MON<=5));then
 echo '⚙️ MON=5 — exportación BULBNN01'
 python3 "$BASE/bnn_genesis/bnn_export.py" --csv "$CSV" --checkpoints "$CHECKPOINTS" \
  --run-id "$RUN_ID" --out "$OUT" --report "$REPORT"
 [[ "$(wc -c < "$OUT"|tr -d ' ')" == 3524 ]] || { echo 'Tamaño BNN incorrecto' >&2; exit 3; }
 next
fi
if ((MON<=6));then
 echo '⚙️ MON=6 — comprobación exportado y reporte'
 python3 "$BASE/bnn_genesis/bnn_export.py" --verify "$OUT" \
  --fen 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
 export BNN_FINAL_FILE="$OUT"
 BNN_VALID_CSV="$FINAL_CSV" "target/release/examples/$VALID_EX" 2>&1|tee "$RUN_DIR/final_validation.log"
 python3 - "$REPORT" "$FINAL_CSV" <<'PY'
import csv,json,sys
from pathlib import Path
p=Path(sys.argv[1]);report=json.loads(p.read_text())
with open(sys.argv[2],newline='') as f:rows={x['model']:x for x in csv.DictReader(f)}
a=float(rows[str(report['best_checkpoint'])]['mse_bnn'])
b=float(rows['final-bnn']['mse_bnn'])
if abs(a-b)>1e-9:raise RuntimeError(f'Mismatch checkpoint vs binary: {a} vs {b}')
report['mse_final_verified']=b
report['final_validation_csv']=sys.argv[2]
p.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
print(f'✅ Paridad exportado/checkpoint: MSE={b:.10f}')
PY
 next
fi
if ((MON==7));then
 echo "✅ BNN Genesis completo: $OUT"
 echo "📊 $REPORT"
 echo "📈 $FINAL_CSV"
fi
