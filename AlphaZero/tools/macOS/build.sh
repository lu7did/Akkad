#!/usr/bin/env bash
# Akkad AlphaZero - autonomous macOS Apple Silicon builder.
# Install: AlphaZero/tools/macOS/build.sh
set -Eeuo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
AZ="$(cd -- "$HERE/../.." && pwd -P)"
DEST="$AZ/macOS/build"
SRC="$DEST/lc0-src"
MESON="$DEST/lc0-build"
OUT="$DEST/AlphaZero"
LC0_REF="${LC0_REF:-v0.32.1}"
JOBS="${BUILD_JOBS:-$(sysctl -n hw.ncpu 2>/dev/null || echo 4)}"
MULTICORE="${AZ_MULTICORE:-ON}"
SKIP_INSTALL="${AZ_SKIP_INSTALL:-0}"
CLEAN=0

info(){ printf '[AlphaZero/macOS] %s\n' "$*"; }
fail(){ printf 'ERROR: %s\n' "$*" >&2; exit 2; }
usage(){ cat <<'HELP'
AlphaZero - compilador autonomo macOS Apple Silicon
Uso: ./build.sh [--jobs N] [--multicore ON|OFF] [--clean] [--no-install-deps] [--help]
  --jobs N            Trabajos paralelos (default: numero de CPUs logicas)
  --multicore ON|OFF  MULTICORE (default: ON)
  --clean             Nueva configuracion Meson; conserva fuentes y build previo
  --no-install-deps   Falla si faltan dependencias, no las instala
  --help              Ayuda
Variables: LC0_REF=v0.32.1, LC0_SOURCE=/ruta/lc0, BUILD_JOBS=N,
           AZ_MULTICORE=ON, AZ_SKIP_INSTALL=1
Salida: AlphaZero/macOS/build/AlphaZero
No requiere AlphaZero/build.sh.
HELP
}
while (($#)); do
  case "$1" in
    -h|--help) usage; exit 0;;
    --jobs|--multicore)
      (($#>=2)) || fail "falta valor para $1"
      if [[ "$1" == --jobs ]]; then JOBS="$2"; else MULTICORE="$2"; fi
      shift 2;;
    --jobs=*) JOBS="${1#*=}"; shift;;
    --multicore=*) MULTICORE="${1#*=}"; shift;;
    --clean) CLEAN=1; shift;;
    --no-install-deps) SKIP_INSTALL=1; shift;;
    *) fail "opcion desconocida $1 (usar --help)";;
  esac
done
[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]] || fail 'requiere macOS Apple Silicon nativo (arm64)'
[[ "$(sysctl -n sysctl.proc_translated 2>/dev/null || echo 0)" != 1 ]] || fail 'terminal ejecutandose bajo Rosetta; usar terminal arm64'
[[ "$JOBS" =~ ^[1-9][0-9]*$ ]] || fail '--jobs debe ser entero positivo'
[[ "$MULTICORE" == ON || "$MULTICORE" == OFF ]] || fail '--multicore debe ser ON u OFF'
[[ -f "$AZ/src/akkad_alphazero_main.cc" && -f "$AZ/src/config.h" && -f "$AZ/src/lc0_startup_telemetry.h" ]] || fail 'faltan archivos en AlphaZero/src (main.cc, config.h o telemetria)'

if ! xcode-select -p >/dev/null 2>&1 || ! xcrun --find clang++ >/dev/null 2>&1; then
  [[ "$SKIP_INSTALL" != 1 ]] || fail 'faltan Xcode Command Line Tools'
  info 'Solicitando instalacion de Xcode Command Line Tools'
  xcode-select --install || true
  fail 'completar instalacion de Xcode Command Line Tools y repetir build.sh'
fi
find_brew(){
  if command -v brew >/dev/null 2>&1; then command -v brew; return; fi
  for f in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    if [[ -x "$f" ]]; then printf '%s\n' "$f"; return; fi
  done
  return 1
}
BREW="$(find_brew || true)"
if [[ -z "$BREW" ]]; then
  [[ "$SKIP_INSTALL" != 1 ]] || fail 'Homebrew no instalado'
  [[ "${AZ_AUTO_INSTALL_BREW:-1}" != 0 ]] || fail 'Homebrew no instalado y AZ_AUTO_INSTALL_BREW=0'
  command -v curl >/dev/null 2>&1 || fail 'falta curl para instalar Homebrew'
  info 'Instalando Homebrew mediante el instalador oficial'
  installer="$(mktemp "${TMPDIR:-/tmp}/az-brew.XXXXXXXX")"
  trap 'rm -f -- "${installer:-}"' EXIT
  curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh -o "$installer"
  /bin/bash "$installer"
  rm -f -- "$installer"; trap - EXIT
  BREW="$(find_brew || true)"
  [[ -n "$BREW" ]] || fail 'Homebrew no disponible despues de instalarlo'
fi
eval "$("$BREW" shellenv)"
BREW="$(command -v brew)"
missing=()
require_cmd(){ command -v "$1" >/dev/null 2>&1 || missing+=("$2"); }
require_cmd git git
require_cmd cmake cmake
require_cmd meson meson
require_cmd ninja ninja
require_cmd python3 python
require_cmd pkg-config pkgconf
require_cmd protoc protobuf
for formula in eigen protobuf; do
  "$BREW" list --versions "$formula" >/dev/null 2>&1 || missing+=("$formula")
done
if ((${#missing[@]})); then
  [[ "$SKIP_INSTALL" != 1 ]] || fail "faltan dependencias: ${missing[*]}"
  unique=(); for name in "${missing[@]}"; do
    seen=0; for prior in "${unique[@]:-}"; do [[ "$prior" == "$name" ]] && seen=1; done
    ((seen)) || unique+=("$name")
  done
  info "Instalando con Homebrew: ${unique[*]}"
  "$BREW" install --formula "${unique[@]}"
fi
for tool in git cmake meson ninja python3 pkg-config protoc; do
  command -v "$tool" >/dev/null 2>&1 || fail "falta $tool tras instalar dependencias"
done
[[ -d "$("$BREW" --prefix eigen)/include/eigen3" ]] || fail 'no se encuentra Eigen'

mkdir -p -- "$DEST"
info "root=$AZ jobs=$JOBS MULTICORE=$MULTICORE LC0=$LC0_REF"
if [[ ! -e "$SRC" ]]; then
  if [[ -n "${LC0_SOURCE:-}" ]]; then
    [[ -f "$LC0_SOURCE/meson.build" ]] || fail 'LC0_SOURCE no contiene meson.build'
    git clone --local -- "$(cd -- "$LC0_SOURCE" && pwd -P)" "$SRC"
  else
    git clone --depth 1 --branch "$LC0_REF" https://github.com/LeelaChessZero/lc0.git "$SRC"
  fi
fi
[[ -f "$SRC/meson.build" && -f "$SRC/src/main.cc" ]] || fail "LC0 incompleto en $SRC; no se borraran los archivos"
git -C "$SRC" submodule update --init --recursive
cp -- "$AZ/src/akkad_alphazero_main.cc" "$SRC/src/main.cc"
cp -- "$AZ/src/lc0_startup_telemetry.h" "$SRC/src/lc0_startup_telemetry.h"
python3 - "$AZ/src/config.h" "$SRC/src/config.h" "$MULTICORE" "$SRC/src/main.cc" <<'PY'
from pathlib import Path
import sys
src, target, multi, main = sys.argv[1:]
config = Path(src).read_text(encoding='utf-8')
if 'kBackend = "onnx-dml"' not in config and 'kBackend = "eigen"' not in config:
    raise SystemExit('ERROR: backend desconocido en src/config.h')
config = config.replace('kBackend = "onnx-dml"', 'kBackend = "eigen"')
config = config.replace('kBackendOptions = "gpu=0"', 'kBackendOptions = ""')
Path(target).write_text(config, encoding='utf-8')
p = Path(main)
content = p.read_text(encoding='utf-8')
p.write_text('#define AZ_MULTICORE '+('1' if multi == 'ON' else '0')+'\n'+content, encoding='utf-8')
PY
options=(-Ddefault_library=static -Dlc0=true -Dgtest=false -Donnx=false -Dblas=true -Dopenblas=false -Ddnnl=false -Dispc=false)
valid=0
if (( ! CLEAN )) && [[ -f "$MESON/build.ninja" && -f "$MESON/meson-info/meson-info.json" ]]; then
  if meson introspect "$MESON" --buildoptions >/dev/null 2>&1 && python3 - "$MESON" "$SRC" <<'PY'
import pathlib,json,sys
b,s=(pathlib.Path(p).resolve() for p in sys.argv[1:])
try:
    d=json.loads((b/'meson-info/meson-info.json').read_text())['directories']
    assert pathlib.Path(d['build']).resolve()==b
    assert pathlib.Path(d['source']).resolve()==s
except (OSError,ValueError,KeyError,AssertionError,TypeError):
    raise SystemExit(1)
PY
  then valid=1; fi
fi
if ((valid)); then
  if ! meson setup --reconfigure "$MESON" "${options[@]}"; then valid=0; fi
fi
if ((!valid)); then
  if [[ -e "$MESON" ]]; then
    backup="$MESON.stale.$(date +%Y%m%d-%H%M%S).$$"
    mv -- "$MESON" "$backup"
    info "Build previo conservado en $backup"
  fi
  meson setup "$MESON" "$SRC" --backend=ninja --buildtype=release "${options[@]}"
fi
meson compile -C "$MESON" -j "$JOBS" lc0
binary="$(find "$MESON" -type f -name lc0 -perm -u+x -print -quit)"
[[ -n "$binary" ]] || fail 'el build termino sin encontrar el binario lc0'
cp -- "$binary" "$OUT"
chmod +x "$OUT"
info "OK ejecutable=$OUT"
"$OUT" --version || true

