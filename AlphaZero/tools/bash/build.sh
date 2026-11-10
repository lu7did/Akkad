
#!/usr/bin/env bash
# Akkad / AlphaZero - Debian Raspberry Pi ARM64 autonomous builder
# Install at AlphaZero/tools/bash/build.sh
set -Eeuo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
AZ_ROOT="$(cd -- "$HERE/../.." && pwd -P)"
BUILD_ROOT="$AZ_ROOT/debian/build"
LC0_TREE="$BUILD_ROOT/lc0-src"
MESON_BUILD="$BUILD_ROOT/lc0-build"
OUTPUT="$BUILD_ROOT/AlphaZero"
LC0_REF="${LC0_REF:-v0.32.1}"
JOBS="${BUILD_JOBS:-2}"
MULTICORE="${AZ_MULTICORE:-ON}"
INSTALL_DEPS=1
CLEAN=0

usage() {
  cat <<'HELP'
AlphaZero C++ - compilador autonomo para Debian/Raspberry Pi ARM64
Uso: ./build.sh [--jobs N] [--multicore ON|OFF] [--clean] [--no-install-deps] [--help]

  --jobs N            Compilaciones simultaneas (default: 2; recomendado en RPi)
  --multicore ON|OFF  Soporte MULTICORE (default: ON)
  --clean             Regenerar solo el directorio Meson; no borra las fuentes LC0
  --no-install-deps   No instalar paquetes; emitir error si faltan
  --help              Mostrar ayuda

Variables: BUILD_JOBS=2, AZ_MULTICORE=ON, LC0_REF=v0.32.1,
           LC0_SOURCE=/ruta/a/fuentes/lc0
Salida:    AlphaZero/debian/build/AlphaZero
No depende de AlphaZero/build.sh.
HELP
}
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 2; }
info() { printf '[AlphaZero/Debian] %s\n' "$*"; }

while (($#)); do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --jobs) (($# >= 2)) || fail 'falta valor de --jobs'; JOBS="$2"; shift 2 ;;
    --jobs=*) JOBS="${1#*=}"; shift ;;
    --multicore) (($# >= 2)) || fail 'falta valor de --multicore'; MULTICORE="$2"; shift 2 ;;
    --multicore=*) MULTICORE="${1#*=}"; shift ;;
    --clean) CLEAN=1; shift ;;
    --no-install-deps) INSTALL_DEPS=0; shift ;;
    *) fail "opcion desconocida: $1 (usar --help)" ;;
  esac
done

[[ "$(uname -s)" == Linux ]] || fail 'requiere Linux'
[[ "$(uname -m)" == aarch64 ]] || fail 'requiere Debian ARM64/aarch64 (Raspberry Pi de 64 bits)'
[[ "$JOBS" =~ ^[1-9][0-9]*$ ]] || fail '--jobs debe ser un entero positivo'
[[ "$MULTICORE" == ON || "$MULTICORE" == OFF ]] || fail '--multicore debe ser ON u OFF'
[[ -f "$AZ_ROOT/src/akkad_alphazero_main.cc" ]] || fail 'falta src/akkad_alphazero_main.cc'
[[ -f "$AZ_ROOT/src/config.h" ]] || fail 'falta src/config.h'
[[ -f "$AZ_ROOT/src/lc0_startup_telemetry.h" ]] || fail 'falta src/lc0_startup_telemetry.h (fuente requerida por la version actual)'
command -v apt-get >/dev/null 2>&1 || fail 'este script requiere apt-get (Debian)'
command -v dpkg-query >/dev/null 2>&1 || fail 'falta dpkg-query'

packages=(build-essential git ca-certificates cmake meson ninja-build pkg-config
          python3 protobuf-compiler libprotobuf-dev libopenblas-dev
          libeigen3-dev zlib1g-dev libssl-dev)
missing=()
for pkg in "${packages[@]}"; do
  if ! dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -qx 'install ok installed'; then
    missing+=("$pkg")
  fi
done
if ((${#missing[@]})); then
  ((INSTALL_DEPS)) || fail "faltan dependencias: ${missing[*]}"
  command -v sudo >/dev/null 2>&1 || [[ "$EUID" == 0 ]] || fail 'se necesita sudo para instalar dependencias'
  sudo_cmd=()
  [[ "$EUID" == 0 ]] || sudo_cmd=(sudo)
  info "Instalando dependencias ausentes: ${missing[*]}"
  "${sudo_cmd[@]}" apt-get update
  "${sudo_cmd[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${missing[@]}"
fi
for exe in git python3 meson ninja pkg-config g++; do
  command -v "$exe" >/dev/null 2>&1 || fail "falta herramienta: $exe"
done
pkg-config --exists openblas || fail 'no se detecta OpenBLAS con pkg-config'
pkg-config --exists zlib || fail 'no se detecta zlib con pkg-config'

info "raiz=$AZ_ROOT"
info "LC0=$LC0_REF multicore=$MULTICORE jobs=$JOBS"
mkdir -p -- "$BUILD_ROOT"

if [[ ! -d "$LC0_TREE" ]]; then
  if [[ -n "${LC0_SOURCE:-}" ]]; then
    [[ -f "$LC0_SOURCE/meson.build" ]] || fail 'LC0_SOURCE no apunta a un arbol LC0 valido'
    git clone --local -- "$(cd -- "$LC0_SOURCE" && pwd -P)" "$LC0_TREE"
  else
    git clone --depth 1 --branch "$LC0_REF" \
      https://github.com/LeelaChessZero/lc0.git "$LC0_TREE"
  fi
fi
[[ -f "$LC0_TREE/meson.build" ]] || fail "LC0 existente sin meson.build: $LC0_TREE (no se borrara automaticamente)"
[[ -d "$LC0_TREE/.git" || -f "$LC0_TREE/.git" ]] || fail 'LC0 existente no es un checkout git'
git -C "$LC0_TREE" submodule update --init --recursive
[[ -f "$LC0_TREE/src/main.cc" ]] || fail 'LC0 sin src/main.cc'

# Modificamos solamente la copia de construccion de LC0.
cp -- "$AZ_ROOT/src/akkad_alphazero_main.cc" "$LC0_TREE/src/main.cc"
cp -- "$AZ_ROOT/src/lc0_startup_telemetry.h" "$LC0_TREE/src/lc0_startup_telemetry.h"
if [[ "$MULTICORE" == OFF ]]; then
  python3 - "$LC0_TREE/src/main.cc" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
p.write_text('#define AZ_MULTICORE 0\n'+p.read_text(encoding='utf-8'), encoding='utf-8')
PY
fi
python3 - "$AZ_ROOT/src/config.h" "$LC0_TREE/src/config.h" <<'PY'
from pathlib import Path
import sys
src=Path(sys.argv[1]).read_text(encoding='utf-8')
if 'kBackend = "onnx-dml"' not in src and 'kBackend = "eigen"' not in src:
    raise SystemExit('ERROR: formato de backend no reconocido en src/config.h')
src=src.replace('kBackend = "onnx-dml"', 'kBackend = "eigen"')
src=src.replace('kBackendOptions = "gpu=0"', 'kBackendOptions = ""')
Path(sys.argv[2]).write_text(src, encoding='utf-8')
PY

options=(-Ddefault_library=static -Dlc0=true -Dgtest=false -Donnx=false
         -Dblas=true -Dopenblas=true -Ddnnl=false -Dispc=false)

# No reutilizar metadata Meson trasladada desde otro host o directorio.
valid=0
if [[ -f "$MESON_BUILD/build.ninja" && -f "$MESON_BUILD/meson-info/meson-info.json" ]]; then
  if meson introspect "$MESON_BUILD" --buildoptions >/dev/null 2>&1 && \
     python3 - "$MESON_BUILD" "$LC0_TREE" <<'PY'
import json, pathlib, sys
b=pathlib.Path(sys.argv[1]).resolve()
s=pathlib.Path(sys.argv[2]).resolve()
try:
    obj=json.loads((b/'meson-info/meson-info.json').read_text(encoding='utf-8'))
    assert pathlib.Path(obj['directories']['source']).resolve()==s
    assert pathlib.Path(obj['directories']['build']).resolve()==b
except (OSError,ValueError,KeyError,AssertionError,TypeError):
    sys.exit(1)
PY
  then valid=1; fi
fi
if ((CLEAN)); then valid=0; fi

if ((valid)); then
  if ! meson setup --reconfigure "$MESON_BUILD" "${options[@]}"; then
    info 'Configuracion Meson anterior no reutilizable; regenerando.'
    valid=0
  fi
fi
if ((!valid)); then
  if [[ -e "$MESON_BUILD" ]]; then
    backup="$MESON_BUILD.stale.$(date +%Y%m%d-%H%M%S).$$"
    mv -- "$MESON_BUILD" "$backup"
    info "Construccion anterior resguardada: $backup"
  fi
  meson setup "$MESON_BUILD" "$LC0_TREE" --backend=ninja \
    --buildtype=release "${options[@]}"
fi

meson compile -C "$MESON_BUILD" -j "$JOBS" lc0
binary="$(find "$MESON_BUILD" -type f -name lc0 -perm -u+x -print -quit)"
[[ -n "$binary" ]] || fail 'Meson termino, pero no se encontro el ejecutable lc0'
cp -- "$binary" "$OUTPUT"
chmod +x "$OUTPUT"
info "OK: $OUTPUT"
info "Para inspeccionar la version: $OUTPUT --version"
