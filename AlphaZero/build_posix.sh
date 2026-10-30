#!/usr/bin/env bash
# Akkad AlphaZero portable Linux/macOS builder (CPU BLAS backends).
set -Eeuo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
OS="$(uname -s)"
case "$OS" in Linux) PLATFORM=debian ;; Darwin) PLATFORM=macos ;; *) echo "ERROR: unsupported host OS: $OS" >&2; exit 2 ;; esac
LC0_REF="${LC0_REF:-v0.32.1}"
LC0_SOURCE="${LC0_SOURCE:-}"
ROOT="$HERE/build"
VENDOR="$ROOT/lc0-src"
MESON_DIR="$ROOT/lc0-build-${PLATFORM}-arm64"
OUT="$ROOT/AlphaZero"
ARCH="$(uname -m)"
if [ "$PLATFORM" = macos ]; then
  [ "$ARCH" = arm64 ] || { echo "ERROR: macOS Apple Silicon arm64 required (avoid Rosetta/x86_64 shell): $ARCH" >&2; exit 2; }
  [ "$(sysctl -n sysctl.proc_translated 2>/dev/null || printf 0)" != 1 ] || { echo "ERROR: run native arm64 terminal, not Rosetta" >&2; exit 2; }
  JOBS="${BUILD_JOBS:-$(sysctl -n hw.ncpu)}"
else
  [ "$ARCH" = aarch64 ] || { echo "ERROR: Raspberry Pi Debian ARM64 (aarch64) required; found $ARCH. Install 64-bit Debian." >&2; exit 2; }
  if [ -r /etc/os-release ]; then
    . /etc/os-release
    case "${ID:-} ${ID_LIKE:-}" in *debian*) : ;; *) echo "WARNING: target is Debian 13.x; detected ${PRETTY_NAME:-unknown}" >&2 ;; esac
  fi
  JOBS="${BUILD_JOBS:-2}"
fi
case "$JOBS" in ""|*[!0-9]*|0) echo "ERROR: BUILD_JOBS must be a positive integer" >&2; exit 2;; esac
echo "PLATFORM=$PLATFORM ARCH=$ARCH BUILD_JOBS=$JOBS LC0_REF=$LC0_REF"
for tool in git meson ninja python3 cmake; do
  command -v "$tool" >/dev/null 2>&1 || { echo "ERROR: missing $tool (read README_PORTABILITY.md)" >&2; exit 2; }
done
if [ "$PLATFORM" = debian ]; then
  command -v pkg-config >/dev/null 2>&1 || { echo 'ERROR: missing pkg-config' >&2; exit 2; }
  pkg-config --exists zlib || { echo 'ERROR: missing zlib development library' >&2; exit 2; }
  pkg-config --exists openblas || { echo 'ERROR: missing OpenBLAS development library' >&2; exit 2; }
fi
mkdir -p "$ROOT"
if [ ! -f "$VENDOR/meson.build" ]; then
  if [ -n "$LC0_SOURCE" ]; then
    [ -f "$LC0_SOURCE/meson.build" ] || { echo 'ERROR: LC0_SOURCE must point to lc0 source with meson.build' >&2; exit 2; }
    git clone --local "$(cd "$LC0_SOURCE" && pwd)" "$VENDOR"
  else
    git clone --depth 1 --branch "$LC0_REF" https://github.com/LeelaChessZero/lc0.git "$VENDOR"
  fi
fi
# Obtain the LC0 protobuf/common submodules needed by its source tree.
git -C "$VENDOR" submodule update --init --recursive
[ -f "$VENDOR/src/main.cc" ] || { echo 'ERROR: LC0 source layout changed (missing src/main.cc)' >&2; exit 2; }
cp "$HERE/src/akkad_alphazero_main.cc" "$VENDOR/src/main.cc"
# Change ONLY the runtime default backend on POSIX: DirectML cannot run here.
# User's tracked C++ source and config.h are not touched.
python3 - "$HERE/src/config.h" "$VENDOR/src/config.h" <<'PY'
from pathlib import Path
import sys
src = Path(sys.argv[1]).read_text(encoding='utf-8')
old = 'kBackend = "onnx-dml"'
if old not in src and 'kBackend = "eigen"' not in src:
    raise SystemExit('ERROR: kBackend default not recognized; inspect config.h')
src = src.replace(old, 'kBackend = "eigen"')
src = src.replace('kBackendOptions = "gpu=0"', 'kBackendOptions = ""')
Path(sys.argv[2]).write_text(src, encoding='utf-8')
PY
# Meson retains settings across builds; clean setup so every invocation applies default settings.
if [ "${CLEAN_BUILD:-0}" = 1 ]; then rm -rf "$MESON_DIR"; fi
meson_args=(setup "$MESON_DIR" "$VENDOR" --backend=ninja --buildtype=release -Ddefault_library=static -Dlc0=true -Dgtest=false -Donnx=false -Dblas=true -Ddnnl=false -Dispc=false)
if [ "$PLATFORM" = debian ]; then
  meson_args+=(-Dopenblas=true)
else
  meson_args+=(-Dopenblas=false)
fi
if [ -f "$MESON_DIR/build.ninja" ]; then
  meson setup --reconfigure "$MESON_DIR" || { echo "ERROR: Meson reconfigure falló (usar CLEAN_BUILD=1)" >&2; exit 2; }
else
  meson "${meson_args[@]}"
fi
meson compile -C "$MESON_DIR" -j "$JOBS" lc0
bin="$(find "$MESON_DIR" -type f -name lc0 -perm -u+x -print -quit)"
[ -n "$bin" ] || { echo 'ERROR: compiled lc0 binary not found' >&2; exit 2; }
cp "$bin" "$OUT"
chmod +x "$OUT"
echo "SUCCESS: $OUT ($ARCH; Akkad MCTS; LC0 C++ backend; eigen CPU)"
echo "To use weights: $OUT --weights /absolute/path/network.pb.gz --backend eigen"
