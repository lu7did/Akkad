#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
 echo 'Uso: ./build.sh [--help]'; echo 'Variables: STEROIDS=OFF|ON (default ON), MULTICORE=OFF|ON (default ON), JOBS=N'; exit 0
fi
if [[ $# -ne 0 ]]; then echo 'Opción desconocida. Usar --help' >&2;exit 2;fi
command -v cmake >/dev/null || { echo 'Falta cmake; instalar con brew install cmake' >&2;exit 1; }
command -v xcrun >/dev/null || { echo 'Faltan Xcode Command Line Tools; ejecutar xcode-select --install' >&2;exit 1; }
SHARED="$HERE/../x86"
for source in board.cpp engine.cpp grumpy.cpp host_main.cpp; do
  if [[ ! -f "$SHARED/src/$source" ]]; then
    echo "ERROR: Fuente compartido faltante: $SHARED/src/$source" >&2
    echo "Verificar que el parche v0.2.45 se haya descomprimido en la raiz akkad." >&2
    exit 1
  fi
done
cmake -S "$HERE" -B "$HERE/build" -DCMAKE_BUILD_TYPE=Release -DSTEROIDS="${STEROIDS:-ON}" -DMULTICORE="${MULTICORE:-ON}"
cmake --build "$HERE/build" --parallel "${JOBS:-$(sysctl -n hw.ncpu)}"
