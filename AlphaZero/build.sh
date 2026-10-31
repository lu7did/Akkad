#!/usr/bin/env bash
# Akkad/AlphaZero - unified native POSIX builder.
# Replaces build_macos.sh, build_debian.sh, build_posix.sh and build_raspberrypi.sh.
set -Eeuo pipefail

usage() {
  cat <<'HELP'
Uso: ./build.sh --OS {MacOS|Debian|Posix|RBPi}
     ./build.sh --help

--OS es obligatorio para compilar. Opciones (respetar mayusculas):
  MacOS    macOS Apple Silicon ARM64; backend Eigen/BLAS.
  Debian   Linux Debian ARM64; backend Eigen + OpenBLAS.
  Posix    Detecta macOS ARM64 o Linux ARM64; no instala paquetes.
  RBPi     Linux ARM64 Raspberry Pi; instala dependencias con APT
           salvo SKIP_APT=1, y compila con OpenBLAS.
  --help   Muestra esta ayuda.

Variables de entorno:
  LC0_REF=v0.32.1    Version de LC0 si hay que descargarlo.
  LC0_SOURCE=ruta    Arbol de fuentes local de LC0 (alternativa al clone remoto).
  BUILD_JOBS=N       Paralelismo (MacOS: numero de CPU; Linux: 2).
  CLEAN_BUILD=1      Regenera el directorio Meson de esta plataforma.
  SKIP_APT=1         Omite apt-get en RBPi.

Ejemplos:
  ./build.sh --OS MacOS
  ./build.sh --OS Debian
  ./build.sh --OS Posix
  SKIP_APT=1 BUILD_JOBS=4 ./build.sh --OS RBPi
HELP
}

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 2; }

if (( $# == 0 )); then
  usage >&2
  printf '\nERROR: se requiere el argumento --OS.\n' >&2
  exit 2
fi

TARGET=''
while (( $# )); do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --OS)
      (( $# >= 2 )) || fail 'falta el valor de --OS'
      [[ -z "$TARGET" ]] || fail '--OS debe especificarse una sola vez'
      TARGET="$2"
      shift 2 ;;
    --OS=*)
      [[ -z "$TARGET" ]] || fail '--OS debe especificarse una sola vez'
      TARGET="${1#--OS=}"
      shift ;;
    *) fail "argumento desconocido: $1 (usar --help)" ;;
  esac
done

[[ -n "$TARGET" ]] || fail 'se requiere --OS (usar --help)'
case "$TARGET" in
  MacOS|Debian|Posix|RBPi) ;;
  *) fail "opcion --OS invalida: $TARGET (usar --help)" ;;
esac

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
HOST_OS="$(uname -s)"
ARCH="$(uname -m)"

case "$TARGET" in
  MacOS)
    [[ "$HOST_OS" == Darwin && "$ARCH" == arm64 ]] || fail "MacOS requiere Darwin arm64 nativo; detectado $HOST_OS/$ARCH"
    PLATFORM=macos ;;
  Debian|RBPi)
    [[ "$HOST_OS" == Linux && "$ARCH" == aarch64 ]] || fail "$TARGET requiere Linux aarch64; detectado $HOST_OS/$ARCH"
    PLATFORM=debian ;;
  Posix)
    case "$HOST_OS/$ARCH" in
      Darwin/arm64) PLATFORM=macos ;;
      Linux/aarch64) PLATFORM=debian ;;
      *) fail "Posix solo soporta Darwin/arm64 o Linux/aarch64; detectado $HOST_OS/$ARCH" ;;
    esac ;;
esac

if [[ "$PLATFORM" == macos ]]; then
  [[ "$(sysctl -n sysctl.proc_translated 2>/dev/null || printf 0)" != 1 ]] || fail 'usar una terminal ARM64 nativa, no Rosetta'
  JOBS="${BUILD_JOBS:-$(sysctl -n hw.ncpu)}"
else
  JOBS="${BUILD_JOBS:-2}"
  if [[ -r /etc/os-release ]]; then
    # Source shell variables only from the OS-maintained release file.
    . /etc/os-release
    case "${ID:-} ${ID_LIKE:-}" in
      *debian*) ;;
      *) printf 'ADVERTENCIA: el build esta probado sobre Debian ARM64; detectado %s\n' "${PRETTY_NAME:-Linux}" >&2 ;;
    esac
  fi
fi
[[ "$JOBS" =~ ^[0-9]+$ && "$JOBS" =~ [1-9] ]] || fail 'BUILD_JOBS debe ser un entero positivo'

# Preserve RBPi's explicit dependency installation; other modes do not use apt.
if [[ "$TARGET" == RBPi && "${SKIP_APT:-0}" != 1 ]]; then
  command -v apt-get >/dev/null 2>&1 || fail 'apt-get no disponible; usar SKIP_APT=1 para gestionar dependencias manualmente'
  if (( EUID == 0 )); then
    SUDO=()
  else
    command -v sudo >/dev/null 2>&1 || fail 'sudo no disponible; usar SKIP_APT=1 o ejecutar con permisos'
    SUDO=(sudo)
  fi
  "${SUDO[@]}" apt-get update
  "${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential git ca-certificates cmake meson ninja-build pkg-config python3 \
    protobuf-compiler libprotobuf-dev libopenblas-dev libeigen3-dev zlib1g-dev libssl-dev
fi

for tool in git meson ninja python3 cmake; do
  command -v "$tool" >/dev/null 2>&1 || fail "falta $tool"
done
if [[ "$PLATFORM" == debian ]]; then
  for tool in pkg-config g++; do
    command -v "$tool" >/dev/null 2>&1 || fail "falta $tool"
  done
  pkg-config --exists zlib || fail 'falta la biblioteca de desarrollo zlib'
  pkg-config --exists openblas || fail 'falta la biblioteca de desarrollo OpenBLAS'
fi

LC0_REF="${LC0_REF:-v0.32.1}"
LC0_SOURCE="${LC0_SOURCE:-}"
ROOT="$HERE/build"
VENDOR="$ROOT/lc0-src"
MESON_DIR="$ROOT/lc0-build-${PLATFORM}-arm64"
OUT="$ROOT/AlphaZero"

[[ -f "$HERE/src/akkad_alphazero_main.cc" ]] || fail 'falta src/akkad_alphazero_main.cc'
[[ -f "$HERE/src/config.h" ]] || fail 'falta src/config.h'
printf 'TARGET=%s PLATFORM=%s ARCH=%s BUILD_JOBS=%s LC0_REF=%s\n' "$TARGET" "$PLATFORM" "$ARCH" "$JOBS" "$LC0_REF"

mkdir -p "$ROOT"
if [[ ! -f "$VENDOR/meson.build" ]]; then
  if [[ -n "$LC0_SOURCE" ]]; then
    [[ -f "$LC0_SOURCE/meson.build" ]] || fail 'LC0_SOURCE debe apuntar a fuentes de lc0 con meson.build'
    git clone --local "$(cd -- "$LC0_SOURCE" && pwd)" "$VENDOR"
  else
    git clone --depth 1 --branch "$LC0_REF" https://github.com/LeelaChessZero/lc0.git "$VENDOR"
  fi
fi

git -C "$VENDOR" submodule update --init --recursive
[[ -f "$VENDOR/src/main.cc" ]] || fail 'cambio en el arbol de LC0: falta src/main.cc'
cp "$HERE/src/akkad_alphazero_main.cc" "$VENDOR/src/main.cc"

# Adjust the build copy, never the tracked config.h source.
python3 - "$HERE/src/config.h" "$VENDOR/src/config.h" <<'PY'
from pathlib import Path
import sys
src = Path(sys.argv[1]).read_text(encoding='utf-8')
old = 'kBackend = "onnx-dml"'
if old not in src and 'kBackend = "eigen"' not in src:
    raise SystemExit('ERROR: kBackend default no reconocido; revisar config.h')
src = src.replace(old, 'kBackend = "eigen"')
src = src.replace('kBackendOptions = "gpu=0"', 'kBackendOptions = ""')
Path(sys.argv[2]).write_text(src, encoding='utf-8')
PY

if [[ "${CLEAN_BUILD:-0}" == 1 ]]; then
  rm -rf -- "$MESON_DIR"
fi

meson_options=(-Ddefault_library=static -Dlc0=true -Dgtest=false -Donnx=false -Dblas=true -Ddnnl=false -Dispc=false)
if [[ "$PLATFORM" == debian ]]; then
  meson_options+=(-Dopenblas=true)
else
  meson_options+=(-Dopenblas=false)
fi

if [[ -f "$MESON_DIR/build.ninja" ]]; then
  meson setup --reconfigure "$MESON_DIR" "${meson_options[@]}" || fail 'Meson reconfigure fallo; reintentar con CLEAN_BUILD=1'
else
  meson setup "$MESON_DIR" "$VENDOR" --backend=ninja --buildtype=release "${meson_options[@]}"
fi

meson compile -C "$MESON_DIR" -j "$JOBS" lc0
bin="$(find "$MESON_DIR" -type f -name lc0 -perm -u+x -print -quit)"
[[ -n "$bin" ]] || fail 'no se encontro el ejecutable lc0 compilado'
cp "$bin" "$OUT"
chmod +x "$OUT"
printf 'SUCCESS: %s (%s; Akkad MCTS; LC0 C++; backend eigen CPU)\n' "$OUT" "$ARCH"
printf 'Uso: %s --weights /ruta/absoluta/red.pb.gz --backend eigen\n' "$OUT"

