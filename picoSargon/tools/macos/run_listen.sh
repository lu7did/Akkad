#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd -- "$HERE/../../.." && pwd -P)"
ENGINE="$ROOT/picoSargon/macOS/build/picoSargon"
WEIGHTS="$ROOT/picoSargon/x86/assets/grumpy.bin"
HOST="${LISTEN_HOST:-0.0.0.0}"
PORT="${LISTEN_PORT:-6200}"
PYTHON="${LISTEN_PYTHON:-python3}"
CORES="${PICOSARGON_CORES:-}"
usage() {
  cat <<'HELP'
Uso: ./picoSargon/tools/macos/run_listen.sh [--host DIRECCION] [--port PUERTO] [--cores N] [--help]
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
   --host|--port|--cores) (($#>=2)) || { echo "Falta valor de $1" >&2; exit 2; }
     if [[ "$1" == --host ]]; then HOST="$2"; elif [[ "$1" == --port ]]; then PORT="$2"; else CORES="$2"; fi
     shift 2 ;;
   *) echo "Opción desconocida: $1" >&2; usage >&2; exit 2 ;;
 esac
done
[[ "$PORT" =~ ^[0-9]+$ ]] && ((10#$PORT>=1 && 10#$PORT<=65535)) || { echo "Puerto inválido: $PORT" >&2; exit 2; }
[[ -x "$ENGINE" ]] || { echo "Falta ejecutable: $ENGINE. Compilar con picoSargon/macOS/build.sh" >&2; exit 1; }
[[ -f "$WEIGHTS" ]] || { echo "Falta la red NNUE: $WEIGHTS" >&2; exit 1; }
command -v "$PYTHON" >/dev/null || { echo "Falta Python 3: $PYTHON" >&2; exit 1; }
if [[ -n "$CORES" ]]; then
 [[ "$CORES" =~ ^[0-9]+$ ]] && ((10#$CORES>=1 && 10#$CORES<=1024)) || { echo "Nucleos invalidos: $CORES" >&2; exit 2; }
 exec "$PYTHON" "$HERE/uci_tcp_server.py" --host "$HOST" --port "$PORT" --engine "$ENGINE" --weights "$WEIGHTS" --cores "$CORES"
fi
exec "$PYTHON" "$HERE/uci_tcp_server.py" --host "$HOST" --port "$PORT" --engine "$ENGINE" --weights "$WEIGHTS"
