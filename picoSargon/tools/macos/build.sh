#!/usr/bin/env bash
# picoSargon macOS build v0.2.53
set -Eeuo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd -- "$HERE/../.." && pwd -P)"
SOURCE="$ROOT/macOS"
SHARED="$ROOT/x86"
BUILD="$SOURCE/build"
usage() {
  cat <<'HELP'
picoSargon macOS build v0.2.53
Uso: ./build.sh [--help]
Origen CMake: picoSargon/macOS
Directorio de compilación: picoSargon/macOS/build
Fuentes C++ compartidas: picoSargon/x86
Variables: STEROIDS=ON|OFF (default ON), MULTICORE=ON|OFF (default ON), JOBS=N
HELP
}
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then usage; exit 0; fi
if (( $# != 0 )); then echo 'ERROR: opción desconocida (usar --help)' >&2; exit 2; fi
command -v cmake >/dev/null 2>&1 || { echo 'ERROR: falta cmake; instalar con brew install cmake' >&2; exit 1; }
command -v xcrun >/dev/null 2>&1 || { echo 'ERROR: faltan Xcode Command Line Tools; ejecutar xcode-select --install' >&2; exit 1; }
[[ -f "$SOURCE/CMakeLists.txt" ]] || { echo "ERROR: falta $SOURCE/CMakeLists.txt" >&2; exit 1; }
for source in board.cpp engine.cpp grumpy.cpp host_main.cpp; do
  [[ -f "$SHARED/src/$source" ]] || { echo "ERROR: falta fuente $SHARED/src/$source" >&2; exit 1; }
done
for header in board.hpp engine.hpp grumpy.hpp; do
  [[ -f "$SHARED/include/$header" ]] || { echo "ERROR: falta cabecera $SHARED/include/$header" >&2; exit 1; }
done
for key in STEROIDS MULTICORE; do
  val="${!key:-ON}"
  [[ "$val" == ON || "$val" == OFF ]] || { echo "ERROR: $key debe ser ON u OFF" >&2; exit 2; }
done
JOBS="${JOBS:-$(sysctl -n hw.ncpu)}"
[[ "$JOBS" =~ ^[0-9]+$ ]] && (( JOBS >= 1 )) || { echo 'ERROR: JOBS debe ser entero positivo' >&2; exit 2; }
echo "⚙️ picoSargon macOS build v0.2.53 source=$SOURCE build=$BUILD shared=$SHARED"
echo "⚙️ STEROIDS=${STEROIDS:-ON} MULTICORE=${MULTICORE:-ON} JOBS=$JOBS"
cmake -S "$SOURCE" -B "$BUILD" -DCMAKE_BUILD_TYPE=Release -DSTEROIDS="${STEROIDS:-ON}" -DMULTICORE="${MULTICORE:-ON}"
cmake --build "$BUILD" --parallel "$JOBS"
[[ -x "$BUILD/picoSargon" ]] || { echo "ERROR: no se generó $BUILD/picoSargon" >&2; exit 1; }
echo "✅ Ejecutable: $BUILD/picoSargon"
