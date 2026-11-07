#!/usr/bin/env bash
#
#  run_listen.sh --cores n --depth n --qdepth n --timeout nnnnn
#
#
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd -- "$HERE/../../.." && pwd -P)"
ENGINE="$ROOT/picoSargon/macOS/build/picoSargon"
WEIGHTS="$ROOT/picoSargon/ARM/assets/grumpy.bin"
HOST="${LISTEN_HOST:-0.0.0.0}"
PORT="${LISTEN_PORT:-6200}"
PYTHON="${LISTEN_PYTHON:-python3}"
CORES="${PICOSARGON_CORES:-}"
DEPTH=""
QDEPTH=""
TIMEOUT=""
BRAINS=""
BRAIN="tinySargon"
usage() {
  cat <<'HELP'
Uso: ./picoSargon/tools/macos/run_listen.sh [--host DIRECCION] [--port PUERTO] [--cores N] [--depth N] [--qdepth N] [--timeout MS] [--brains ARCHIVO] [--brain NOMBRE] [--help]
Defecto: --host 0.0.0.0 --port 6200
--cores N es obligatorio si el ejecutable fue compilado con MULTICORE=ON.
--cores N no se admite si el ejecutable fue compilado con MULTICORE=OFF.
Variables: LISTEN_HOST, LISTEN_PORT, LISTEN_PYTHON, PICOSARGON_CORES
Telemetría: stderr; protocolo UCI: por conexión TCP.
HELP
}
while (($#)); do
 case "$1" in
   -h|--help) usage; exit 0 ;;
   --host|--port|--cores|--depth|--qdepth|--timeout|--brains|--brain) (($#>=2)) || { echo "Falta valor de $1" >&2; exit 2; }
     if [[ "$1" == --host ]]; then HOST="$2"; elif [[ "$1" == --port ]]; then PORT="$2"; elif [[ "$1" == --cores ]]; then CORES="$2"; elif [[ "$1" == --depth ]]; then DEPTH="$2"; elif [[ "$1" == --qdepth ]]; then QDEPTH="$2"; elif [[ "$1" == --timeout ]]; then TIMEOUT="$2"; elif [[ "$1" == --brains ]]; then BRAINS="$2"; else BRAIN="$2"; fi
     shift 2 ;;
   *) echo "Opción desconocida: $1" >&2; usage >&2; exit 2 ;;
 esac
done
[[ "$PORT" =~ ^[0-9]+$ ]] && ((10#$PORT>=1 && 10#$PORT<=65535)) || { echo "Puerto inválido: $PORT" >&2; exit 2; }
[[ -x "$ENGINE" ]] || { echo "Falta ejecutable: $ENGINE. Compilar con picoSargon/macOS/build.sh" >&2; exit 1; }
[[ -f "$WEIGHTS" ]] || { echo "Falta la red NNUE: $WEIGHTS" >&2; exit 1; }
command -v "$PYTHON" >/dev/null || { echo "Falta Python 3: $PYTHON" >&2; exit 1; }
ARGS=(--host "$HOST" --port "$PORT" --engine "$ENGINE" --weights "$WEIGHTS")
for item in CORES DEPTH QDEPTH TIMEOUT; do
  value="${!item}"
  case "$item" in
    CORES) flag=cores; min=1; max=1024 ;;
    DEPTH) flag=depth; min=1; max=40 ;;
    QDEPTH) flag=qdepth; min=0; max=32 ;;
    TIMEOUT) flag=timeout; min=1; max=2147483647 ;;
  esac
  if [[ -n "$value" ]]; then
    [[ "$value" =~ ^[0-9]+$ ]] && ((10#$value >= min && 10#$value <= max)) || { echo "Valor invalido para --$flag: $value" >&2; exit 2; }
    ARGS+=("--$flag" "$value")
  fi
done
if [[ -n "$BRAINS" ]]; then
  [[ -f "$BRAINS" ]] || { echo "Archivo brains.json inexistente: $BRAINS" >&2; exit 2; }
  ARGS+=(--brains "$BRAINS" --brain "$BRAIN")
fi
exec "$PYTHON" "$HERE/uci_tcp_server.py" "${ARGS[@]}"
