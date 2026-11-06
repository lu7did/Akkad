#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd -- "$HERE/../../.." && pwd -P)"
ENGINE="$ROOT/picoSargon/macOS/build/picoSargon"
WEIGHTS="$ROOT/picoSargon/x86/assets/grumpy.bin"
HOST="${LISTEN_HOST:-127.0.0.1}"
PORT="${LISTEN_PORT:-6200}"
PYTHON="${LISTEN_PYTHON:-python3}"
usage() {
  cat <<'HELP'
Uso: ./picoSargon/tools/macos/run_listen.sh [--host DIRECCION] [--port PUERTO] [--help]
Defecto: 127.0.0.1:6200 (sólo conexiones locales)
Para permitir conexiones desde la LAN: --host 0.0.0.0
Variables: LISTEN_HOST, LISTEN_PORT, LISTEN_PYTHON
Telemetría: stderr; protocolo UCI: por conexión TCP.
HELP
}
while (($#)); do
 case "$1" in
   -h|--help) usage; exit 0 ;;
   --host|--port) (($#>=2)) || { echo "Falta valor de $1" >&2; exit 2; }
     if [[ "$1" == --host ]]; then HOST="$2"; else PORT="$2"; fi
     shift 2 ;;
   *) echo "Opción desconocida: $1" >&2; usage >&2; exit 2 ;;
 esac
done
[[ "$PORT" =~ ^[0-9]+$ ]] && ((10#$PORT>=1 && 10#$PORT<=65535)) || { echo "Puerto inválido: $PORT" >&2; exit 2; }
[[ -x "$ENGINE" ]] || { echo "Falta ejecutable: $ENGINE. Compilar con picoSargon/macOS/build.sh" >&2; exit 1; }
[[ -f "$WEIGHTS" ]] || { echo "Falta la red NNUE: $WEIGHTS" >&2; exit 1; }
command -v "$PYTHON" >/dev/null || { echo "Falta Python 3: $PYTHON" >&2; exit 1; }
exec "$PYTHON" "$HERE/uci_tcp_server.py" --host "$HOST" --port "$PORT" --engine "$ENGINE" --weights "$WEIGHTS"
