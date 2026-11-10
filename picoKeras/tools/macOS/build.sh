#!/usr/bin/env bash
# picoKeras macOS build v0.2.14 (TFLite / shared C++ sources)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
SRC="$ROOT/macOS"
BUILD="$SRC/build"
TF="${TFLITE_ROOT:-$SRC/third_party/tensorflow}"
TF_VERSION="${TF_VERSION:-v2.18.1}"
# Pin the PSimd dependency used by the legacy FP16 build to a reproducible commit.
PSIMD_REF="072586a71b55b7f8c584153d223e95687148a900"
PSIMD_DIR="$SRC/third_party/psimd"
JOBS="${BUILD_JOBS:-$(sysctl -n hw.ncpu 2>/dev/null || printf 4)}"
XNNPACK=ON
KLEIDIAI=OFF  # Disable optional KleidiAI: upstream archive checksum mismatch on macOS
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
  --kleidiai ON|OFF       Optional KleidiAI kernels (default: OFF; XNNPACK remains ON)
  --native ON|OFF         -mcpu=native (default: ON; OFF for portable builds)
  --multicore ON|OFF     Compile parallel search (default: ON)
  --lto ON|OFF            Interprocedural optimization (default: ON)
  --no-install-deps       Fail instead of installing missing build dependencies
Environment: TFLITE_ROOT, TF_VERSION, BUILD_JOBS
  PSimd is fetched once at a pinned revision under macOS/third_party/psimd
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
 --jobs|--tf-root|--tf-version|--xnnpack|--kleidiai|--native|--lto|--multicore)
   (($# >= 2)) || fail "Missing argument for $1"
   case "$1" in
     --jobs) JOBS="$2";; --tf-root) TF="$2";; --tf-version) TF_VERSION="$2";;
     --xnnpack) XNNPACK="$2";; --kleidiai) KLEIDIAI="$2";; --native) NATIVE="$2";; --lto) LTO="$2";; --multicore) MULTICORE="$2";;
   esac
   shift 2;;
 *) fail "Unknown argument: $1 (try --help)";;
 esac
done
[[ "$(uname -s)" == Darwin ]] || fail 'macOS required'
[[ "$JOBS" =~ ^[1-9][0-9]*$ ]] || fail "Invalid --jobs $JOBS"
valid_bool "$XNNPACK";valid_bool "$KLEIDIAI";valid_bool "$NATIVE";valid_bool "$LTO";valid_bool "$MULTICORE"
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
# TensorFlow Lite v2.18.1 kernels/elementwise.cc uses std::abs<T> as a
# callable. AppleClang 21/libc++ rejects overload resolution when converting
# it to std::function<T(T)>. Apply an exact, idempotent compatibility patch
# to the pinned TensorFlow checkout before compiling.
# Never silently rewrite an unknown source version.
patch_tflite_appleclang() {
  local file="$TF/tensorflow/lite/kernels/elementwise.cc"
  [[ -f "$file" ]] || fail "Missing TensorFlow Lite source: $file"
  command -v python3 >/dev/null 2>&1 || fail 'python3 is required for the AppleClang compatibility fix'
  python3 - "$file" <<'PYFIX'
from pathlib import Path
import sys

p = Path(sys.argv[1])
s = p.read_text(encoding='utf-8')
replacements = (
    ('EvalImpl<float>(context, node, std::abs<float>, type)',
     'EvalImpl<float>(context, node, [](float x) -> float { return std::abs(x); }, type)'),
    ('EvalImpl<int32_t>(context, node, std::abs<int32_t>, type)',
     'EvalImpl<int32_t>(context, node, [](int32_t x) -> int32_t { return std::abs(x); }, type)'),
)
changed = False
for old, new in replacements:
    old_count = s.count(old)
    new_count = s.count(new)
    if old_count == 1 and new_count == 0:
        s = s.replace(old, new, 1)
        changed = True
    elif old_count == 0 and new_count == 1:
        pass  # Already patched: incremental builds remain safe.
    else:
        raise SystemExit(
            f'ERROR: unexpected TensorFlow Lite source in {p}: '
            f'old={old_count}, new={new_count}. No patch applied.'
        )
if changed:
    p.write_text(s, encoding='utf-8')
    print('🔧 AppleClang/TFLite: replaced ambiguous std::abs overloads in elementwise.cc')
else:
    print('✅ AppleClang/TFLite: elementwise.cc compatibility fix already present')
PYFIX
}
patch_tflite_appleclang

# FP16 0a92994d invokes a separate CMake project just to download PSimd.
# Modern CMake rejects that legacy bootstrap before it even clones PSimd.
# Supply a real, pinned PSimd source tree, and FP16 skips its own downloader.
if [[ ! -f "$PSIMD_DIR/CMakeLists.txt" ]]; then
  [[ ! -e "$PSIMD_DIR" ]] || fail "Incomplete PSimd checkout at $PSIMD_DIR; move it aside and retry"
  mkdir -p "$(dirname "$PSIMD_DIR")"
  tmp_psimd="$(mktemp -d "$(dirname "$PSIMD_DIR")/.psimd-fetch.XXXXXX")"
  cleanup_psimd(){ [[ -z "${tmp_psimd:-}" ]] || rm -rf -- "$tmp_psimd"; }
  trap cleanup_psimd EXIT
  printf '📦 Obtaining pinned PSimd %s...\n' "$PSIMD_REF"
  git -C "$tmp_psimd" init -q
  git -C "$tmp_psimd" remote add origin https://github.com/Maratyszcza/psimd.git
  git -C "$tmp_psimd" fetch -q --depth 1 origin "$PSIMD_REF"
  git -C "$tmp_psimd" checkout -q --detach FETCH_HEAD
  [[ -f "$tmp_psimd/CMakeLists.txt" ]] || fail 'Pinned PSimd checkout has no CMakeLists.txt'
  mv "$tmp_psimd" "$PSIMD_DIR"
  tmp_psimd=''
  trap - EXIT
fi
[[ -d "$PSIMD_DIR/.git" ]] || fail "PSimd is not a Git checkout: $PSIMD_DIR"
actual_psimd="$(git -C "$PSIMD_DIR" rev-parse HEAD)"
[[ "$actual_psimd" == "$PSIMD_REF" ]] || fail "PSimd revision mismatch: $actual_psimd (expected $PSIMD_REF)"
# Keep a policy compatibility floor for legacy CMake subprojects.  The
# separate PSimd downloader is bypassed explicitly via PSIMD_SOURCE_DIR;
# this setting alone was insufficient in v0.2.12.
export CMAKE_POLICY_VERSION_MINIMUM=3.5
if ((CLEAN)); then rm -rf "$BUILD";fi
if [[ -f "$BUILD/CMakeCache.txt" ]];then
 old="$(sed -n 's/^CMAKE_HOME_DIRECTORY:INTERNAL=//p' "$BUILD/CMakeCache.txt" | head -1)"
 [[ "$old" == "$SRC" ]] || fail "Existing CMake cache belongs to $old; rerun with --clean"
fi
printf '🔧 picoKeras macOS v0.2.14 / TFLite %s / jobs=%s XNNPACK=%s KleidiAI=%s native=%s LTO=%s MULTICORE=%s\n' "$TF_VERSION" "$JOBS" "$XNNPACK" "$KLEIDIAI" "$NATIVE" "$LTO" "$MULTICORE"
cmake -S "$SRC" -B "$BUILD" -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DTFLITE_ROOT="$TF" -DPICOKERAS_XNNPACK="$XNNPACK" \
  -DPICOKERAS_KLEIDIAI="$KLEIDIAI" -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  -DPSIMD_SOURCE_DIR="$PSIMD_DIR" \
  -DPICOKERAS_NATIVE="$NATIVE" -DPICOKERAS_LTO="$LTO" -DMULTICORE="$MULTICORE" \
  -DCMAKE_OSX_DEPLOYMENT_TARGET="${MACOS_DEPLOYMENT_TARGET:-13.0}"
cmake --build "$BUILD" --target picoKeras --parallel "$JOBS"
[[ -x "$BUILD/picoKeras" ]] || fail "Missing expected output $BUILD/picoKeras"
printf '✅ Built: %s\n' "$BUILD/picoKeras"

