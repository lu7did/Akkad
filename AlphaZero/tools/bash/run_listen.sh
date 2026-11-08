#!/usr/bin/env bash
# AlphaZero debian TCP/UCI listener v0.2.11
set -Eeuo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
AKKAD="$(cd -- "$HERE/../../.." && pwd -P)"
SARGON="$AKKAD/Sargon-NNUE"
IP=0.0.0.0
PORT=6200
BRAIN=amelie
PYTHON="${PYTHON_BIN:-python3}"
CORES=1
usage() {
 cat <<'HELP'
AlphaZero debian TCP/UCI listener v0.2.11
Uso: ./run_listen.sh [--ip IP] [--port NUM] [--brain ID] [--python PATH] [--cores N] [--help]
IP por defecto: 0.0.0.0; puerto: 6200; brain: amelie.
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
[[ -x "$AKKAD/AlphaZero/debian/build/AlphaZero" ]] || { echo 'ERROR: motor sin compilar, ejecutar tools/bash/build.sh' >&2; exit 2; }
ENGINE="$AKKAD/AlphaZero/debian/build/AlphaZero"
ENGINE_ID="$("$ENGINE" --version 2>/dev/null || true)"
case "$ENGINE_ID" in
  'AlphaZero v0.2.11 build='*) ;;
  *) printf 'ERROR: binario incompatible: %s (version=%s)\n' "$ENGINE" "$ENGINE_ID" >&2; exit 2 ;;
esac
printf '⚙️ AlphaZero launcher executable=%s\n' "$ENGINE" >&2
printf '⚙️ AlphaZero launcher version=%s\n' "$ENGINE_ID" >&2
printf '⚙️ AlphaZero launcher brain=%s config=%s\n' "$BRAIN" "$SARGON/etc/brains/brains.json" >&2
export PYTHONPATH="$SARGON/src${PYTHONPATH:+:$PYTHONPATH}"
cd "$SARGON"
exec "$PYTHON" -m sargon_nnue.sargon_listen --brain "$SARGON/etc/brains/brains.json" --id "$BRAIN" --mode TCP --host "$IP" --port "$PORT"
