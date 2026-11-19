#!/usr/bin/env bash
# Bullet GRMP0001 Genesis: train FP32 on T79 / validate T77 / export 6-bit 1304B.
# Run from any directory; place grumpy_genesis/ alongside this script.
# Does NOT change picoSargon or Nurse source.
set -Eeuo pipefail
BASE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${BASE_DIR}/bullet_runtime.sh"
bullet_resolve_runtime "${BASE_DIR}" || exit 2
RUN_ID="${RUN_ID:-grumpy-bullet-001}"
TRAIN_DATA="${TRAIN_DATA:-$HOME/stockfish/test79-may2022-16tb7p-filter-v6-dd.min-mar2023.unmin.high-simple-eval-1k.min-v2.binpack}"
VALID_DATA="${VALID_DATA:-$HOME/stockfish/test77-jan2022-2tb7p.high-simple-eval-1k.min-v2.binpack}"
SUPERBATCHES="${SUPERBATCHES:-100}"
SAVE_EVERY="${SAVE_EVERY:-10}"
BATCH_SIZE="${BATCH_SIZE:-4096}"
BATCHES_PER_SB="${BATCHES_PER_SB:-256}"
LR_START="${LR_START:-0.001}"
LR_FINAL="${LR_FINAL:-0.0001}"
VALID_COUNT="${VALID_COUNT:-2000000}"
REFERENCE="${REFERENCE:-}"  # Optional path to real picoSargon/assets/grumpy.bin
RUN_DIR="$(bullet_resolve_run_dir "$BASE_DIR" "$RUN_ID")"
CKPTS="$RUN_DIR/checkpoints"
OUTPUT="$RUN_DIR/grumpy_new.bin"
REPORT="$RUN_DIR/report.json"
VALID_CSV="$RUN_DIR/validation.csv"
FINAL_CSV="$RUN_DIR/final_validation.csv"
LOCK="$RUN_DIR/config.lock"
STATE="$RUN_DIR/MON.state"
TRAIN_EX="grmp_${RUN_ID//-/_}_train"
VALID_EX="grmp_${RUN_ID//-/_}_validate"

usage(){ cat <<EOF
Uso: bash run_genesis.sh [--mon 1..6] [--status]
Etapas:
  MON=1: requisitos, identidad de fuentes y configuración bloqueada
  MON=2: instala ejemplos aislados y compila Metal
  MON=3: entrenamiento desde cero/reanudación con optimizador
  MON=4: validación independiente de todos los checkpoints FP32 + INT6
  MON=5: selecciona mejor INT6 y exporta grumpy_new.bin (1304 bytes)
  MON=6: valida el archivo final, checksum y compara referencia si existe
  MON=7: completo
Configuración opcional mediante variables de entorno: BULLET_DIR, RUN_ID,
 TRAIN_DATA, VALID_DATA, SUPERBATCHES, SAVE_EVERY, BATCH_SIZE, BATCHES_PER_SB,
 LR_START, LR_FINAL, VALID_COUNT, REFERENCE.
Ejemplo: bash run_genesis.sh --mon 1
Reanudar: bash run_genesis.sh  (lee MON.state)
NOTA: checkpoint seleccionado por T77; fuerza ajedrecística requiere Nurse.
EOF
}
CLI=""; STATUS=0
while (($#));do
  case "$1" in
    --mon) [[ $# -ge 2 ]] || { echo 'Falta valor --mon' >&2; exit 2; };CLI="$2";shift 2;;
    --status) STATUS=1;shift;;
    -h|--help) usage;exit 0;;
    *) echo "Argumento inesperado: $1" >&2; usage;exit 2;;
  esac
done
[[ "$RUN_ID" =~ ^[A-Za-z][A-Za-z0-9_-]*$ ]] || { echo 'RUN_ID inválido' >&2;exit 2; }
for value in "$SUPERBATCHES" "$SAVE_EVERY" "$BATCH_SIZE" "$BATCHES_PER_SB" "$VALID_COUNT";do
  [[ "$value" =~ ^[1-9][0-9]*$ ]] || { echo "Parámetro entero inválido: $value" >&2;exit 2; }
done
[[ "$SUPERBATCHES" -ge "$SAVE_EVERY" ]] || { echo 'SUPERBATCHES < SAVE_EVERY' >&2;exit 2; }
[[ -d "$BULLET_DIR/crates/bullet_lib" ]] || { echo "Bullet no encontrado: $BULLET_DIR" >&2; exit 2; }
mkdir -p "$RUN_DIR" "$CKPTS"
if [[ -n "$CLI" ]];then MON="$CLI";elif [[ -s "$STATE" ]];then MON="$(cat "$STATE")";else MON=1;fi
[[ "$MON" =~ ^[1-7]$ ]] || { echo "MON inválido: $MON" >&2;exit 2; }

config(){ cat <<EOF
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
REFERENCE=$REFERENCE
VERSION=grmp-bullet-genesis-v1
EOF
}
if [[ -f "$LOCK" ]] && ! config | cmp -s - "$LOCK";then
 echo "❌ La configuración difiere de $LOCK; restaure valores o use otro RUN_ID" >&2;exit 2
fi
if ((STATUS));then
 echo "RESULTADOS_AKKAD=$RUN_DIR"
  echo "RUN_ID=$RUN_ID MON=$MON"
  echo "CHECKPOINTS=$CKPTS"
  find "$CKPTS" -maxdepth 1 -type d -name "$RUN_ID-*" -print 2>/dev/null|sort -V || true
  echo "OUTPUT=$OUTPUT";exit 0
fi
if ((MON==7));then echo "✅ Completado: $OUTPUT";exit 0;fi
trap 'echo "❌ Falló MON=$MON; reanudar con bash run_genesis.sh --mon $MON" >&2' ERR
next(){ local nxt=$((MON+1));printf '%s\n' "$nxt" > "$STATE.tmp";mv "$STATE.tmp" "$STATE";echo "✅ MON=$MON -> MON=$nxt";MON=$nxt; }
verify_sources(){
 [[ -s "$TRAIN_DATA" && -s "$VALID_DATA" ]] || { echo 'Falta T79 o T77; configurar TRAIN_DATA y VALID_DATA' >&2;exit 2; }
 [[ -s "$BASE_DIR/grumpy_genesis/grumpy_train.rs" && -s "$BASE_DIR/grumpy_genesis/grumpy_validate.rs" && -s "$BASE_DIR/grumpy_genesis/grumpy_export.py" ]] || { echo 'Faltan fuentes en grumpy_genesis/' >&2;exit 2;}
 command -v cargo >/dev/null;command -v python3 >/dev/null
}
export GR_RUN_ID="$RUN_ID" GR_TRAIN="$TRAIN_DATA" GR_VALID="$VALID_DATA"
export GR_CHECKPOINTS="$CKPTS" GR_SUPERBATCHES="$SUPERBATCHES" GR_SAVE_EVERY="$SAVE_EVERY"
export GR_BATCH="$BATCH_SIZE" GR_BATCHES_PER_SUPERBATCH="$BATCHES_PER_SB"
export GR_LR_START="$LR_START" GR_LR_FINAL="$LR_FINAL" GR_VALID_COUNT="$VALID_COUNT"
export GR_VALID_CSV="$VALID_CSV"
[[ -z "$REFERENCE" ]] || export GR_REFERENCE="$REFERENCE"
cd "$BULLET_DIR"
if ((MON<=1));then
 echo '⚙️ MON=1 — entradas y bloqueo configuración'
 verify_sources
 echo "Bullet: $(git rev-parse HEAD 2>/dev/null || echo 'sin git')" | tee "$RUN_DIR/bullet_commit.txt"
 echo "Entrenamiento: $TRAIN_DATA";echo "Validación: $VALID_DATA"
 if [[ ! -e "$LOCK" ]];then config > "$LOCK.tmp";mv "$LOCK.tmp" "$LOCK";fi
 printf '1\n' > "$STATE";next
fi
if ((MON<=2));then
 echo '⚙️ MON=2 — instalación de ejemplos y compilación Metal'
 verify_sources
 bullet_install_example "$TRAIN_EX" "$BASE_DIR/grumpy_genesis/grumpy_train.rs"
 bullet_install_example "$VALID_EX" "$BASE_DIR/grumpy_genesis/grumpy_validate.rs"
 cargo build --release --locked -p bullet_lib --example "$TRAIN_EX" --features metal
 cargo build --release --locked -p bullet_lib --example "$VALID_EX" --features metal
 next
fi
if ((MON<=3));then
 echo '⚙️ MON=3 — entrenamiento FP32 (resume con optimizador)'
 verify_sources
 start=1; resume=''
 for ((sb=SAVE_EVERY; sb<=SUPERBATCHES; sb+=SAVE_EVERY));do
   d="$CKPTS/$RUN_ID-$sb"
   if [[ -s "$d/raw.bin" && -s "$d/optimiser_state/weights.bin" ]];then start=$((sb+1));resume="$d";fi
 done
 if [[ -s "$CKPTS/$RUN_ID-$SUPERBATCHES/raw.bin" ]];then
   echo "✅ Entrenamiento ya llegó a $SUPERBATCHES"
 else
   export GR_START_SB="$start" GR_RESUME_FROM="$resume"
   echo "Resume start_superbatch=$start checkpoint=${resume:-none}"
   "target/release/examples/$TRAIN_EX" 2>&1 | tee -a "$RUN_DIR/train.log"
 fi
 [[ -s "$CKPTS/$RUN_ID-$SUPERBATCHES/raw.bin" ]] || { echo 'Checkpoint final ausente' >&2; exit 3; }
 next
fi
if ((MON<=4));then
 echo '⚙️ MON=4 — T77: FP32, INT6 directo y Grumpy de referencia'
 verify_sources
 GR_VALID_CSV="$VALID_CSV" "target/release/examples/$VALID_EX" 2>&1 | tee "$RUN_DIR/validation.log"
 [[ -s "$VALID_CSV" ]] || { echo 'No se generó validation.csv' >&2;exit 3; }
 next
fi
if ((MON<=5));then
 echo '⚙️ MON=5 — exportación GRMP0001'
 python3 "$BASE_DIR/grumpy_genesis/grumpy_export.py" \
   --csv "$VALID_CSV" --checkpoints "$CKPTS" --run-id "$RUN_ID" \
   --out "$OUTPUT" --report "$REPORT" --reference "$REFERENCE"
 [[ "$(wc -c < "$OUTPUT" | tr -d ' ')" == 1304 ]] || { echo 'Archivo final no tiene 1304 bytes' >&2;exit 3; }
 next
fi
if ((MON<=6));then
 echo '⚙️ MON=6 — auditoría de compatibilidad y reporte final'
 python3 - "$OUTPUT" "$REPORT" <<'PY'
import sys,json,hashlib
from pathlib import Path
# Trusted verifier independently checks bytes and checksum.
p=Path(sys.argv[1]);b=p.read_bytes()
assert len(b)==1304 and b[:8]==b'GRMP0001' and int.from_bytes(b[8:12],'little')==105
assert hashlib.sha256(b[44:]).digest()==b[12:44]
r=json.loads(Path(sys.argv[2]).read_text())
assert hashlib.sha256(b).hexdigest()==r['grmp_sha256']
print('✅ GRMP0001 header=44 bytes, payload=1260 bytes, 1680 weights /6bits, SHA256 OK')
PY
 export GR_FINAL_FILE="$OUTPUT"
 GR_VALID_CSV="$FINAL_CSV" "target/release/examples/$VALID_EX" 2>&1 | tee "$RUN_DIR/final_validation.log"
 python3 - "$REPORT" "$FINAL_CSV" <<'PY'
import sys,csv,json
from pathlib import Path
p=Path(sys.argv[1]);report=json.loads(p.read_text())
with open(sys.argv[2],newline='') as f:rows={r['model']:r for r in csv.DictReader(f)}
assert 'final-grmp' in rows
best=rows[str(report['best_checkpoint'])]
actual=float(rows['final-grmp']['mse_int6'])
assert abs(actual-float(best['mse_int6']))<1e-9,(actual,best['mse_int6'])
report['mse_final_verification']=actual
report['final_validation_file']=sys.argv[2]
p.write_text(json.dumps(report,indent=2,ensure_ascii=False))
print('✅ Modelo exportado y checkpoint cuantizado equivalentes en T77; MSE=',actual)
print('✅ Salida final:',report['grmp_file'])
PY
 next
fi
if ((MON==7));then
 echo '✅ Genesis completado'
 echo "📦 $OUTPUT"
 echo "📊 $REPORT"
 echo "📈 $FINAL_CSV"
fi
