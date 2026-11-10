#!/usr/bin/env bash
# picoKeras macOS listener v0.2.10. Brain mode delegates UCI handling to Nurse.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PK_ROOT="$(cd "$HERE/../.." && pwd)"
AKKAD="$(cd "$PK_ROOT/.." && pwd)"
EXE="$PK_ROOT/macOS/build/picoKeras"
BRAINS="$AKKAD/nurse/etc/brains/brains.json"
ID=""
WEIGHTS=""
IP="0.0.0.0"
PORT=6200
DIRECT=0
CORES=auto
DEPTH=2
TMAX=15000

usage(){
 cat <<'HELP'
Usage: picoKeras/tools/macOS/run_listen.sh --id BRAIN [options]
       picoKeras/tools/macOS/run_listen.sh --direct --weights FILE.tflite [options]

  --id, --brain ID       Named picoKeras UCI brain in --brains JSON (Nurse mode)
  --brains FILE          Default: akkad/nurse/etc/brains/brains.json
  --ip ADDRESS           Bind interface (default: 0.0.0.0)
  --port PORT            Listener port (default: 6200)
  --cores N|auto         Native direct-mode CPU budget (default: auto)
  --depth N              Native direct-mode minimax depth (default: 2)
  --tmax MS              Native direct-mode search timeout (default: 15000)
  --direct               Use picoKeras native TCP server instead of Nurse
  --weights FILE.tflite  Mandatory with --direct; in brain mode use brain args
  --help                 Show help

Brain mode: type=uci, player.macOS points to macOS/build/picoKeras,
args.macOS contains --weights /absolute/path/model.tflite.
Nurse listens on TCP and forwards UCI to the picoKeras executable over stdio.
Direct mode: picoKeras itself listens on TCP (--tcp).
HELP
}
fail(){ printf '❌ %s\n' "$*" >&2;exit 1; }
while (($#));do
 case "$1" in
 --help|-h) usage;exit 0;;
 --direct) DIRECT=1;shift;;
 --id|--brain|--brains|--ip|--port|--weights|--cores|--depth|--tmax)
   (($# >= 2)) || fail "Missing value for $1"
   case "$1" in
    --id|--brain) ID="$2";; --brains) BRAINS="$2";; --ip) IP="$2";;
    --port) PORT="$2";; --weights) WEIGHTS="$2";;
    --cores) CORES="$2";; --depth) DEPTH="$2";; --tmax) TMAX="$2";;
   esac
   shift 2;;
 *) fail "Unknown option $1 (try --help)";;
 esac
done
[[ "$(uname -s)" == Darwin ]] || fail 'macOS required'
[[ "$PORT" =~ ^[0-9]+$ ]] && (( PORT>=1 && PORT<=65535 )) || fail 'Port must be between 1 and 65535'
[[ -x "$EXE" ]] || fail "Engine missing: $EXE. Run tools/macOS/build.sh first."
if ((DIRECT));then
 [[ -z "$ID" ]] || fail '--direct cannot be combined with --id'
 [[ -f "$WEIGHTS" && "$WEIGHTS" == *.tflite ]] || fail '--direct requires an existing .tflite file via --weights'
 printf '🌐 picoKeras native TCP %s:%s weights=%s\n' "$IP" "$PORT" "$WEIGHTS"
 exec "$EXE" --weights "$WEIGHTS" --tcp --host "$IP" --port "$PORT" --cores "$CORES" --depth "$DEPTH" --tmax "$TMAX"
fi
[[ -n "$ID" ]] || fail 'Required: --id BRAIN (or --direct --weights FILE.tflite)'
[[ -z "$WEIGHTS" ]] || fail 'In brain mode, weights must be declared in brains.json args.macOS'
[[ -f "$BRAINS" ]] || fail "Missing brains file: $BRAINS"
# Preserve the caller's relative path before changing to the Akkad root.
BRAINS="$(cd "$(dirname "$BRAINS")" && pwd)/$(basename "$BRAINS")"
command -v python3 >/dev/null || fail 'python3 is required for Nurse brain mode'
# Run from repo root so brain arguments that are repository-relative resolve
# consistently. Use Nurse's own read_brain (including duplicate-key rejection).
cd "$AKKAD"
export PYTHONPATH="$AKKAD/nurse/src${PYTHONPATH:+:$PYTHONPATH}"
python3 - "$BRAINS" "$ID" "$EXE" <<'PY'
import os,sys
from pathlib import Path
from nurse.config import read_brain
config_file, identity, binary = sys.argv[1:]
cfg=read_brain(config_file,identity)
if cfg['_type']!='uci':
    raise SystemExit(f"❌ Brain {identity!r} must be type='uci' for picoKeras macOS")
if Path(cfg['_engine']).resolve()!=Path(binary).resolve():
    raise SystemExit(f"❌ Brain {identity!r} player.macOS must point to {binary}; got {cfg['_engine']}")
args=cfg.get('_args',[])
if '--weights' not in args and '--network' not in args:
    raise SystemExit(f"❌ Brain {identity!r} args.macOS must contain --weights model.tflite")
idx=args.index('--weights') if '--weights' in args else args.index('--network')
if idx+1>=len(args):
    raise SystemExit('❌ --weights requires a model path')
model=Path(args[idx+1]).expanduser()
if model.suffix!='.tflite' or not model.is_file():
    raise SystemExit(f'❌ picoKeras macOS requires an existing .tflite model: {model}')
print(f'✅ picoKeras brain={identity} executable={binary} network={model}',flush=True)
PY
printf '🌐 Nurse TCP listener %s:%s brain=%s\n' "$IP" "$PORT" "$ID"
exec python3 -m nurse.listen --brains "$BRAINS" --id "$ID" --ip "$IP" --port "$PORT"
