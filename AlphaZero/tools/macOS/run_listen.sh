#!/usr/bin/env bash
# AlphaZero macOS TCP/UCI listener v0.2.9
set -Eeuo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
AKKAD="$(cd -- "$HERE/../../.." && pwd -P)"
SARGON="$AKKAD/Sargon-NNUE"
IP=0.0.0.0
PORT=6200
BRAIN=emma
PYTHON="${PYTHON_BIN:-python3}"
CORES=1
usage() {
 cat <<'HELP'
AlphaZero macOS TCP/UCI listener v0.2.9
Uso: ./run_listen.sh [--ip IP] [--port NUM] [--brain ID] [--python PATH] [--cores N] [--help]
IP por defecto: 0.0.0.0; puerto: 6200; brain: emma.
La configuración del motor y red proviene de Sargon-NNUE/etc/brains/brains.json.
HELP
}
while (( $# )); do
 case "$1" in
 --help|-h) usage; exit 0;;
 --ip|--port|--brain|--python|--cores)
  (( $#>=2 )) || { echo "ERROR: falta valor para $1" >&2; exit 2; }
  case "$1" in --ip) IP="$2";; --port) PORT="$2";; --brain) BRAIN="$2";; --python) PYTHON="$2";; --cores) CORES="$2";; esac
  shift 2;;
 *) echo "ERROR: opción desconocida: $1" >&2; exit 2;;
 esac
done
[[ "$CORES" =~ ^[0-9]+$ ]] && (( CORES>=1 && CORES<=256 )) || { echo "ERROR: cores debe ser 1..256" >&2; exit 2; }
export AKKAD_AZ_CORES="$CORES"
[[ "$PORT" =~ ^[0-9]+$ ]] && (( PORT>=1 && PORT<=65535 )) || { echo 'ERROR: puerto inválido' >&2; exit 2; }
[[ -f "$SARGON/etc/brains/brains.json" ]] || { echo 'ERROR: falta brains.json' >&2; exit 2; }
[[ -d "$SARGON/src/sargon_nnue" ]] || { echo 'ERROR: falta paquete sargon_nnue' >&2; exit 2; }
command -v "$PYTHON" >/dev/null 2>&1 || { echo "ERROR: Python no encontrado: $PYTHON" >&2; exit 2; }
[[ -x "$AKKAD/AlphaZero/macOS/build/AlphaZero" ]] || { echo 'ERROR: motor sin compilar, ejecutar tools/macOS/build.sh' >&2; exit 2; }
# Validate the deployed executable, not only the source code version.
ENGINE="$AKKAD/AlphaZero/macOS/build/AlphaZero"
ENGINE_ID="$(printf 'uci\nquit\n' | "$ENGINE" 2>/dev/null | grep -m1 '^id name ' || true)"
if [[ "$ENGINE_ID" != 'id name AlphaZero v0.2.9' ]]; then
  echo "ERROR: binario AlphaZero incompatible o desactualizado: $ENGINE" >&2
  echo "ERROR: identidad detectada: ${ENGINE_ID:-ninguna}" >&2
  echo 'Recompilar: bash AlphaZero/tools/macOS/build.sh' >&2
  exit 2
fi
printf '⚙️ AlphaZero executable=%s version=v0.2.9\n' "$ENGINE" >&2
export PYTHONPATH="$SARGON/src${PYTHONPATH:+:$PYTHONPATH}"
cd "$SARGON"
exec "$PYTHON" -m sargon_nnue.sargon_listen --brain "$SARGON/etc/brains/brains.json" --id "$BRAIN" --mode TCP --host "$IP" --port "$PORT"
