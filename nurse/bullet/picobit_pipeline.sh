#!/usr/bin/env bash
# picoBit / Bullet: NNUE convencional Chess768-(128x2)-1
# MON: 1 verificacion, 2 generacion, 3 compilacion, 4 entrenamiento,
#      5 paridad nativa, 6 validacion T77, 7 informe.
set -Eeuo pipefail

# ====================== CONFIGURACION CENTRAL ======================
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/bullet_runtime.sh"
bullet_resolve_runtime "$SCRIPT_DIR" || exit 2
# Templates are immutable source inputs: prefer Akkad's imported snapshot.
TEMPLATE_DIR="$SCRIPT_DIR/picobit_genesis"
picobit_require_templates() {
  local missing=0 f
  for f in pico_bit_train.rs pico_bit_validate.rs pico_bit_parity.rs; do
    [[ -s "$TEMPLATE_DIR/$f" ]] || missing=1
  done
  if ((missing)); then
    echo '⚙️ Importando las plantillas Rust históricas desde Bullet externo' >&2
    bash "$SCRIPT_DIR/import_picobit_templates.sh" || return 2
  fi
  for f in pico_bit_train.rs pico_bit_validate.rs pico_bit_parity.rs; do
    [[ -s "$TEMPLATE_DIR/$f" ]] || {
      echo "ERROR: no existe $TEMPLATE_DIR/$f. Plantilla original ausente tanto de Akkad como de Bullet." >&2
      return 2
    }
  done
}


RUN_ID="picobit-nnue-003"              # nombre UNICO por corrida/red
TRAIN_DATA="${HOME}/stockfish/test79-may2022-16tb7p-filter-v6-dd.min-mar2023.unmin.high-simple-eval-1k.min-v2.binpack"
VALID_DATA="${HOME}/stockfish/test77-jan2022-2tb7p.high-simple-eval-1k.min-v2.binpack"
HIDDEN=128                         # arquitectura actual; NO se modifica aqui
BATCH_SIZE=4096
BATCHES_PER_SB=256
END_SB=100
SAVE_EVERY=10                       # END_SB debe ser multiplo de SAVE_EVERY
LEARNING_RATE=0.001
FINAL_LEARNING_RATE=0.0001
WDL=0.75
EVAL_SCALE=400.0
LOADER_THREADS=2
READ_BUFFER_MB=32
QUEUE_SIZE=8
VALID_POSITIONS=2000000            # cero para todo el archivo (no recomendado)
PARITY_TOL=0.0001
# MON se guarda automáticamente tras CADA etapa; --mon N permite retomarla.
# Para iniciar de cero, cambiar RUN_ID; NUNCA borrar checkpoints previos.
# ====================================================================

usage() { cat <<'HELP'
Uso: bash picobit_pipeline.sh [--mon N] [--status]
  MON=1 verifica entradas; MON=2 genera ejemplos Rust; MON=3 compila;
  MON=4 entrena/reanuda desde ultimo checkpoint completo; MON=5 compara
  inferencia con Bullet; MON=6 valida T77; MON=7 presenta resultados.
  Sin --mon, recupera MON del estado de RUN_ID. Valores 1..7.
  Cambiar RUN_ID para entrenar una red nueva sin pisar checkpoints.
  NO modifica ejemplos originales ni código interno de Bullet.
  Las plantillas pertenecen a akkad/nurse/bullet/picobit_genesis/.
  Si todavía no están allí: bash import_picobit_templates.sh
  BULLET_DIR permite elegir instalación externa de Bullet.
HELP
}
CLI_MON=""; STATUS=0
while (($#)); do
  case "$1" in
    --mon) [[ $# -ge 2 ]] || { echo "Falta valor para --mon" >&2; exit 2; }; CLI_MON="$2"; shift 2;;
    --status) STATUS=1; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Argumento desconocido: $1" >&2; usage; exit 2;;
  esac
done
[[ "$RUN_ID" =~ ^[A-Za-z][A-Za-z0-9_-]*$ ]] || { echo "RUN_ID inválido" >&2; exit 2; }
[[ "$HIDDEN" == 128 ]] || { echo "Este pipeline sólo soporta HIDDEN=128; adaptar inferencia/paridad antes de cambiarlo" >&2; exit 2; }
for v in BATCH_SIZE BATCHES_PER_SB END_SB SAVE_EVERY LOADER_THREADS READ_BUFFER_MB QUEUE_SIZE; do
  [[ "${!v}" =~ ^[1-9][0-9]*$ ]] || { echo "$v debe ser entero positivo" >&2; exit 2; }
done
[[ "$VALID_POSITIONS" =~ ^[0-9]+$ ]] || { echo "VALID_POSITIONS inválido" >&2; exit 2; }
(( END_SB % SAVE_EVERY == 0 )) || { echo "END_SB debe ser divisible por SAVE_EVERY" >&2; exit 2; }
RUN_DIR="$(bullet_resolve_run_dir "$SCRIPT_DIR" "$RUN_ID")"
CKPT_DIR="$RUN_DIR/checkpoints"
STATE_FILE="$RUN_DIR/MON.state"
CONFIG_FILE="$RUN_DIR/config.lock"
SLUG="pb_$(printf '%s' "$RUN_ID" | tr '-' '_')"
TRAIN_EX="${SLUG}_train"; PARITY_EX="${SLUG}_parity"; VALID_EX="${SLUG}_validate"
mkdir -p "$RUN_DIR"
if [[ -n "$CLI_MON" ]]; then MON="$CLI_MON";
elif [[ -f "$STATE_FILE" ]]; then MON="$(cat "$STATE_FILE")";
else MON=1; fi
[[ "$MON" =~ ^[1-8]$ ]] || { echo "MON inválido: $MON" >&2; exit 2; }

config_text() { cat <<EOF
RUN_ID=$RUN_ID
BULLET_DIR=$BULLET_DIR
TRAIN_DATA=$TRAIN_DATA
VALID_DATA=$VALID_DATA
HIDDEN=$HIDDEN
BATCH_SIZE=$BATCH_SIZE
BATCHES_PER_SB=$BATCHES_PER_SB
END_SB=$END_SB
SAVE_EVERY=$SAVE_EVERY
LEARNING_RATE=$LEARNING_RATE
FINAL_LEARNING_RATE=$FINAL_LEARNING_RATE
WDL=$WDL
EVAL_SCALE=$EVAL_SCALE
LOADER_THREADS=$LOADER_THREADS
READ_BUFFER_MB=$READ_BUFFER_MB
QUEUE_SIZE=$QUEUE_SIZE
VALID_POSITIONS=$VALID_POSITIONS
PARITY_TOL=$PARITY_TOL
EOF
}
if [[ -f "$CONFIG_FILE" ]]; then
  if ! config_text | cmp -s - "$CONFIG_FILE"; then
    echo "ERROR: configuración distinta de $CONFIG_FILE. Usá otro RUN_ID o restaurá la configuración original." >&2
    exit 2
  fi
fi
if ((STATUS)); then
  echo "RESULTADOS_AKKAD=$RUN_DIR"
  echo "RUN_ID=$RUN_ID MON=$MON"; echo "Estado: $STATE_FILE"
  find "$CKPT_DIR" -maxdepth 1 -type d -name "${RUN_ID}-*" -print 2>/dev/null | sort -V || true
  exit 0
fi
if ((MON == 8)); then echo "✅ Pipeline ya completado: $RUN_DIR"; exit 0; fi
cd "$BULLET_DIR"
fail() { echo "❌ Falló MON=$MON. Estado conservado en $STATE_FILE" >&2; }
trap fail ERR
advance() {
  local next="$((MON + 1))"
  printf '%s\n' "$next" > "$STATE_FILE.tmp"
  mv "$STATE_FILE.tmp" "$STATE_FILE"
  echo "✅ MON=$MON completado -> MON=$next"
  MON="$next"
}

if (( MON == 1 )); then
  echo '⚙️ MON=1 — verificar herramientas, datasets y plantilla'
  command -v cargo >/dev/null; command -v python3 >/dev/null
  [[ -s "$TRAIN_DATA" && -s "$VALID_DATA" ]]
  picobit_require_templates || exit 2
  [[ -s crates/bullet_lib/Cargo.toml ]] || { echo 'Falta Cargo.toml de Bullet' >&2;exit 2; }
  [[ -d crates/bullet_lib/src ]]
  config_text > "$CONFIG_FILE"
  git rev-parse HEAD > "$RUN_DIR/bullet_commit.txt"
  echo "Repositorio: $(cat "$RUN_DIR/bullet_commit.txt")"
  echo "Train: $(du -h "$TRAIN_DATA" | cut -f1) / Val: $(du -h "$VALID_DATA" | cut -f1)"
  advance
fi

if (( MON == 2 )); then
  echo '⚙️ MON=2 — generar fuentes Rust aisladas de la corrida'
  picobit_require_templates || exit 2
  export PB_TEMPLATE_DIR="$TEMPLATE_DIR"
  export PB_RUN_ID="$RUN_ID" PB_RUN_DIR="$RUN_DIR" PB_CKPT_DIR="$CKPT_DIR" PB_TRAIN_EX="$TRAIN_EX" PB_PARITY_EX="$PARITY_EX" PB_VALID_EX="$VALID_EX"
  export PB_TRAIN_DATA="$TRAIN_DATA" PB_VALID_DATA="$VALID_DATA" PB_BATCH_SIZE="$BATCH_SIZE" PB_BATCHES_PER_SB="$BATCHES_PER_SB" PB_END_SB="$END_SB" PB_SAVE_EVERY="$SAVE_EVERY" PB_LR="$LEARNING_RATE" PB_FINAL_LR="$FINAL_LEARNING_RATE" PB_WDL="$WDL" PB_EVAL_SCALE="$EVAL_SCALE" PB_THREADS="$LOADER_THREADS" PB_READ_BUF="$READ_BUFFER_MB" PB_QUEUE="$QUEUE_SIZE" PB_VALID_N="$VALID_POSITIONS" PB_TOL="$PARITY_TOL"
  python3 - <<'PY'
import os, re, json
from pathlib import Path
O=os.environ
p=Path('examples')
templates=Path(O['PB_TEMPLATE_DIR'])
def replace_one(s,pattern,repl,flags=0):
    s,n=re.subn(pattern,lambda m: repl,s,count=1,flags=flags)
    if n!=1: raise RuntimeError(f'No se encontró patrón exacto en plantilla: {pattern}')
    return s
def lit(s): return json.dumps(str(s),ensure_ascii=False)
run=O['PB_RUN_ID']; path=O['PB_CKPT_DIR']; ids=list(range(int(O['PB_SAVE_EVERY']),int(O['PB_END_SB'])+1,int(O['PB_SAVE_EVERY'])))
train=(templates/'pico_bit_train.rs').read_text()
train=replace_one(train,r'const TRAIN: &str = concat!\(.*?\);',f'const TRAIN: &str = {lit(O["PB_TRAIN_DATA"])};',re.S)
train=replace_one(train,r'net_id: "[^"]+"\.to_string\(\)',f'net_id: {lit(run)}.to_string()')
train=replace_one(train,r'output_directory: "[^"]+"',f'output_directory: {lit(path)}')
for field,val in [('batch_size',O['PB_BATCH_SIZE']),('batches_per_superbatch',O['PB_BATCHES_PER_SB']),('end_superbatch',O['PB_END_SB']),('save_rate',O['PB_SAVE_EVERY']),('threads',O['PB_THREADS']),('batch_queue_size',O['PB_QUEUE'])]:
    train=replace_one(train,rf'\b{field}: \d+',f'{field}: {val}')
train=replace_one(train,r'\bstart_superbatch: \d+','start_superbatch: start_sb')
train=replace_one(train,r'\beval_scale: [\d.]+',f'eval_scale: {O["PB_EVAL_SCALE"]}')
train=replace_one(train,r'value: 0\.75',f'value: {O["PB_WDL"]}')
train=replace_one(train,r'lr_scheduler: lr::ConstantLR \{\s*value: [^}]+\}',f'lr_scheduler: lr::CosineDecayLR {{ initial_lr: {O["PB_LR"]}, final_lr: {O["PB_FINAL_LR"]}, final_superbatch: {O["PB_END_SB"]} }}',re.S)
train=replace_one(train,r'SfBinpackLoader::new\(\s*TRAIN,\s*\d+,\s*\d+,',f'SfBinpackLoader::new(\n        TRAIN,\n        {O["PB_READ_BUF"]},\n        {O["PB_THREADS"]},')
train=replace_one(train,r'    let schedule = TrainingSchedule', '''    let start_sb: usize = std::env::var("PICOBIT_START_SB")
        .ok().and_then(|x| x.parse().ok()).unwrap_or(1);
    if let Ok(ckpt) = std::env::var("PICOBIT_RESUME_CKPT") {
        println!("Reanudando pesos y AdamW desde: {ckpt}");
        trainer.load_from_checkpoint(&ckpt);
    }
    let schedule = TrainingSchedule''')
train=re.sub(r'    println!\("⚙️ Batches:.*?;\n','',train)
train=re.sub(r'    println!\("⚙️ Checkpoints:.*?;\n','',train)
train_path=p/(O['PB_TRAIN_EX']+'.rs'); train_path.write_text(train)
val=(templates/'pico_bit_validate.rs').read_text()
val=replace_one(val,r'const TEST: &str = concat!\(.*?\);',f'const TEST: &str = {lit(O["PB_VALID_DATA"])};',re.S)
val=replace_one(val,r'const N: usize = [^;]+;',f'const N: usize = {O["PB_VALID_N"] if O["PB_VALID_N"]!="0" else "usize::MAX"};')
val=replace_one(val,r'const WDL: f32 = [^;]+;',f'const WDL: f32 = {O["PB_WDL"]};')
val=replace_one(val,r'const EVAL_SCALE: f32 = [^;]+;',f'const EVAL_SCALE: f32 = {O["PB_EVAL_SCALE"]};')
val=replace_one(val,r'const CHECKPOINTS: \[usize; \d+\] = \[[^]]+\];',f'const CHECKPOINTS: [usize; {len(ids)}] = {ids!r};')
val=replace_one(val,r'let path = format!\(\s*"checkpoints/picobit-train-v1-\{id\}/raw.bin"\s*\);',f'let path = format!({lit(path+"/"+run+"-{id}/raw.bin")});')
val=replace_one(val,r'File::create\("picobit_validation.csv"\)',f'File::create({lit(O["PB_RUN_DIR"]+"/validation.csv")})')
val=val.replace('✅ CSV: picobit_validation.csv', '✅ CSV: '+O['PB_RUN_DIR']+'/validation.csv')
val_path=p/(O['PB_VALID_EX']+'.rs'); val_path.write_text(val)
par=(templates/'pico_bit_parity.rs').read_text()
par=replace_one(par,r'let path = format!\("checkpoints/picobit-train-v1-\{id\}"\);',f'let path = format!({lit(path+"/"+run+"-{id}")});')
par=replace_one(par,r'for id in \[5, 10, 15, 20\]',f'for id in {ids!r}')
par=replace_one(par,r'let path = format!\(\s*"checkpoints/picobit-train-v1-\{id\}/raw.bin"\s*\);',f'let path = format!({lit(path+"/"+run+"-{id}/raw.bin")});')
# Paridad: utilizar exactamente el mismo constructor de red generado en train
builder=re.search(r'    let mut trainer = ValueTrainerBuilder::default\(\).*?(?=    let start_sb: usize)',train,re.S)
if not builder: raise RuntimeError('No se puede extraer constructor de NNUE del entrenador')
par=replace_one(par,r'(?m)^[ \t]*let mut trainer = ValueTrainerBuilder::default\(\).*?(?=^[ \t]*let path = format!)', builder.group().rstrip()+'\n', re.S|re.M)
par_path=p/(O['PB_PARITY_EX']+'.rs'); par_path.write_text(par)
manifest=Path('crates/bullet_lib/Cargo.toml')
s=manifest.read_text()
for ex in [O['PB_TRAIN_EX'],O['PB_PARITY_EX'],O['PB_VALID_EX']]:
    if f'name = "{ex}"' not in s:
        s+=f'\n[[example]]\nname = "{ex}"\npath = "../../examples/{ex}.rs"\n'
manifest.write_text(s)
print('Archivos:',train_path,par_path,val_path)
print('Checkpoints:',ids)
PY
  advance
fi

if (( MON == 3 )); then
  echo '⚙️ MON=3 — compilar entrenamiento, paridad y validación (Metal)'
  cargo build --release --locked -p bullet_lib --features metal --example "$TRAIN_EX" --example "$PARITY_EX" --example "$VALID_EX" 2>&1 | tee "$RUN_DIR/build.log"
  advance
fi

if (( MON == 4 )); then
  echo '⚙️ MON=4 — entrenar / reanudar checkpoints'
  mkdir -p "$CKPT_DIR"
  latest=0
  for ((i=SAVE_EVERY;i<=END_SB;i+=SAVE_EVERY)); do
    d="$CKPT_DIR/${RUN_ID}-$i"
    if [[ -s "$d/raw.bin" && -s "$d/optimiser_state/weights.bin" ]]; then latest="$i"; fi
  done
  if ((latest >= END_SB)); then
    echo "✅ Checkpoint final ya existente: ${RUN_ID}-${END_SB}; no se sobrescribe"
  else
    if ((latest > 0)); then
      export PICOBIT_START_SB="$((latest+1))" PICOBIT_RESUME_CKPT="$CKPT_DIR/${RUN_ID}-${latest}"
      echo "Reanudando en superbatch $PICOBIT_START_SB desde $PICOBIT_RESUME_CKPT"
    else
      unset PICOBIT_START_SB PICOBIT_RESUME_CKPT || true
      echo "Entrenamiento nuevo desde superbatch 1"
    fi
    "./target/release/examples/$TRAIN_EX" 2>&1 | tee -a "$RUN_DIR/train.log"
  fi
  [[ -s "$CKPT_DIR/${RUN_ID}-${END_SB}/raw.bin" ]] || { echo "Falta checkpoint final" >&2; exit 1; }
  advance
fi

if (( MON == 5 )); then
  echo '⚙️ MON=5 — comprobar paridad con inferencia nativa Bullet'
  "./target/release/examples/$PARITY_EX" 2>&1 | tee "$RUN_DIR/parity.log"
  grep -q 'INFERENCIA MANUAL COINCIDE CON BULLET' "$RUN_DIR/parity.log"
  advance
fi

if (( MON == 6 )); then
  echo '⚙️ MON=6 — validar T77 con todos los checkpoints'
  "./target/release/examples/$VALID_EX" 2>&1 | tee "$RUN_DIR/validation.log"
  [[ -s "$RUN_DIR/validation.csv" ]] || { echo "No se generó CSV de validación" >&2; exit 1; }
  advance
fi

if (( MON == 7 )); then
  echo '⚙️ MON=7 — informe final'
  python3 - "$RUN_DIR/validation.csv" "$RUN_DIR/report.txt" <<'PY'
import csv,sys
rows=list(csv.DictReader(open(sys.argv[1],newline='')))
if not rows: raise SystemExit('CSV de validación vacío')
rows.sort(key=lambda r: float(r['mse']))
lines=['picoBit NNUE | resumen de validación',f"Mejor checkpoint: {rows[0]['checkpoint']}",f"MSE: {rows[0]['mse']}",f"RMSE: {rows[0]['rmse']}",f"MAE: {rows[0]['mae']}",f"Posiciones: {rows[0]['positions']}", '', 'Ranking:']
lines += [f"{r['checkpoint']}: MSE={r['mse']} RMSE={r['rmse']} MAE={r['mae']}" for r in rows]
s='\n'.join(lines)+'\n';open(sys.argv[2],'w').write(s);print(s)
PY
  echo "Archivos generados: $RUN_DIR"
  advance
fi
