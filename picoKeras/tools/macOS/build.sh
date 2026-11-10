#!/usr/bin/env bash
# picoKeras macOS build v0.2.10 (TFLite / shared C++ sources)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
SRC="$ROOT/macOS"
BUILD="$SRC/build"
TF="${TFLITE_ROOT:-$SRC/third_party/tensorflow}"
TF_VERSION="${TF_VERSION:-v2.18.1}"
JOBS="${BUILD_JOBS:-$(sysctl -n hw.ncpu 2>/dev/null || printf 4)}"
XNNPACK=ON
NATIVE=ON
LTO=ON
MULTICORE=ON
CLEAN=0
INSTALL_DEPS=1

usage() {
 cat <<'HELP'
Usage: picoKeras/tools/macOS/build.sh [options]
  --help                  Show this help
  --clean                 Remove macOS/build before building
  --jobs N                Build concurrency (default: hw.ncpu)
  --tf-root DIR           Existing TensorFlow source checkout (overrides TFLITE_ROOT)
  --tf-version TAG        Git ref to clone (default: v2.18.1)
  --xnnpack ON|OFF        Optimized CPU delegate (default: ON)
  --native ON|OFF         -mcpu=native (default: ON; OFF for portable builds)
  --multicore ON|OFF     Compile parallel search (default: ON)
  --lto ON|OFF            Interprocedural optimization (default: ON)
  --no-install-deps       Fail instead of installing missing build dependencies
Environment: TFLITE_ROOT, TF_VERSION, BUILD_JOBS
Output: picoKeras/macOS/build/picoKeras
Input network: .tflite, not a SavedModel directory; convert it separately.
HELP
}
fail(){ printf '❌ %s\n' "$*" >&2; exit 1; }
valid_bool(){ [[ "$1" == ON || "$1" == OFF ]] || fail "Expected ON or OFF, got $1"; }
while (($#)); do
 case "$1" in
 --help|-h) usage;exit 0;;
 --clean) CLEAN=1;shift;;
 --no-install-deps) INSTALL_DEPS=0;shift;;
 --jobs|--tf-root|--tf-version|--xnnpack|--native|--lto|--multicore)
   (($# >= 2)) || fail "Missing argument for $1"
   case "$1" in
     --jobs) JOBS="$2";; --tf-root) TF="$2";; --tf-version) TF_VERSION="$2";;
     --xnnpack) XNNPACK="$2";; --native) NATIVE="$2";; --lto) LTO="$2";; --multicore) MULTICORE="$2";;
   esac
   shift 2;;
 *) fail "Unknown argument: $1 (try --help)";;
 esac
done
[[ "$(uname -s)" == Darwin ]] || fail 'macOS required'
[[ "$JOBS" =~ ^[1-9][0-9]*$ ]] || fail "Invalid --jobs $JOBS"
valid_bool "$XNNPACK";valid_bool "$NATIVE";valid_bool "$LTO";valid_bool "$MULTICORE"
command -v xcrun >/dev/null || fail 'Xcode Command Line Tools unavailable. Install via: xcode-select --install'
xcrun --find clang++ >/dev/null 2>&1 || fail 'Apple Clang missing. Run: xcode-select --install'

ensure_deps(){
 local missing=() tool
 for tool in cmake ninja git; do command -v "$tool" >/dev/null || missing+=("$tool"); done
 ((${#missing[@]} == 0)) && return 0
 ((INSTALL_DEPS)) || fail "Missing build dependencies: ${missing[*]}"
 if ! command -v brew >/dev/null; then
   for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
     if [[ -x "$candidate" ]]; then export PATH="$(dirname "$candidate"):$PATH";break;fi
   done
 fi
 if ! command -v brew >/dev/null; then
   command -v curl >/dev/null || fail 'Homebrew missing and curl unavailable'
   printf '🍺 Installing Homebrew for required tools...\n'
   NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
     if [[ -x "$candidate" ]]; then export PATH="$(dirname "$candidate"):$PATH";break;fi
   done
 fi
 command -v brew >/dev/null || fail 'Homebrew installation failed'
 brew install "${missing[@]}"
 for tool in "${missing[@]}"; do command -v "$tool" >/dev/null || fail "$tool unavailable after installation";done
}
ensure_deps

if [[ ! -f "$TF/tensorflow/lite/CMakeLists.txt" ]]; then
 [[ "$TF" == "$SRC/third_party/tensorflow" ]] || fail "Invalid external TFLITE_ROOT=$TF"
 mkdir -p "$(dirname "$TF")"
 printf '📦 Cloning TensorFlow source %s...\n' "$TF_VERSION"
 git clone --depth 1 --branch "$TF_VERSION" https://github.com/tensorflow/tensorflow.git "$TF"
fi
if ((CLEAN)); then rm -rf "$BUILD";fi
if [[ -f "$BUILD/CMakeCache.txt" ]];then
 old="$(sed -n 's/^CMAKE_HOME_DIRECTORY:INTERNAL=//p' "$BUILD/CMakeCache.txt" | head -1)"
 [[ "$old" == "$SRC" ]] || fail "Existing CMake cache belongs to $old; rerun with --clean"
fi
printf '🔧 picoKeras macOS v0.2.10 / TFLite %s / jobs=%s XNNPACK=%s native=%s LTO=%s MULTICORE=%s\n' "$TF_VERSION" "$JOBS" "$XNNPACK" "$NATIVE" "$LTO" "$MULTICORE"
cmake -S "$SRC" -B "$BUILD" -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DTFLITE_ROOT="$TF" -DPICOKERAS_XNNPACK="$XNNPACK" \
  -DPICOKERAS_NATIVE="$NATIVE" -DPICOKERAS_LTO="$LTO" -DMULTICORE="$MULTICORE" \
  -DCMAKE_OSX_DEPLOYMENT_TARGET="${MACOS_DEPLOYMENT_TARGET:-13.0}"
cmake --build "$BUILD" --target picoKeras --parallel "$JOBS"
[[ -x "$BUILD/picoKeras" ]] || fail "Missing expected output $BUILD/picoKeras"
printf '✅ Built: %s\n' "$BUILD/picoKeras"
