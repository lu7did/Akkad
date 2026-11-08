#!/usr/bin/env bash
# Akkad / AlphaZero: macOS native build wrapper v0.2.4
# Auto-installs missing build dependencies; keeps the shared C++ build unchanged.
set -Eeuo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd -- "$HERE/../.." && pwd -P)"

usage() {
  cat <<'HELP'
AlphaZero macOS build v0.2.4
Uso: ./build.sh [--help]

Instala las dependencias que falten y luego compila AlphaZero C++ usando
AlphaZero/build.sh --OS MacOS (Apple Silicon arm64).

Dependencias: Xcode Command Line Tools, Homebrew, git, cmake, meson,
              ninja, python3, pkg-config, protobuf y eigen.

Variables:
  AZ_MULTICORE=ON|OFF    Activa/desactiva MULTICORE (default ON).
  BUILD_JOBS=N            Numero de compilaciones paralelas.
  LC0_REF=v0.32.1         Version de LC0 si hay que descargarla.
  LC0_SOURCE=PATH         Fuentes locales de LC0.
  CLEAN_BUILD=1           Reconstruye el directorio Meson.
  AZ_SKIP_INSTALL=1       No instala: solo comprueba dependencias.
  AZ_AUTO_INSTALL_BREW=0  No instala Homebrew si falta.

Salida: AlphaZero/macOS/build/AlphaZero
Nota: Homebrew o Xcode pueden solicitar contrasena/autorizacion del usuario.
HELP
}

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 2; }
info() { printf '[AlphaZero/macOS] %s\n' "$*"; }

if (( $# > 0 )); then
  case "$1" in
    -h|--help) [[ $# -eq 1 ]] || fail 'argumentos adicionales a --help'; usage; exit 0 ;;
    *) usage >&2; fail "argumento desconocido: $1" ;;
  esac
fi

[[ "$(uname -s)" == Darwin ]] || fail 'este script requiere macOS'
[[ "$(uname -m)" == arm64 ]] || fail 'este constructor requiere Apple Silicon arm64 en Terminal nativa'
[[ "$(sysctl -n sysctl.proc_translated 2>/dev/null || printf 0)" != 1 ]] || fail 'abrir Terminal arm64, no Rosetta'

# CLT installation is managed by macOS; the GUI installer must finish before
# this script can continue. Do not install anything as root or erase caches.
if ! xcode-select -p >/dev/null 2>&1 || ! xcrun --find clang++ >/dev/null 2>&1; then
  if [[ "${AZ_SKIP_INSTALL:-0}" == 1 ]]; then
    fail 'faltan las Xcode Command Line Tools (ejecutar xcode-select --install)'
  fi
  info 'Faltan las Xcode Command Line Tools; solicitando instalacion de macOS.'
  xcode-select --install || true
  fail 'completa la instalacion de Xcode Command Line Tools y vuelve a ejecutar build.sh'
fi

# Find Homebrew even when this shell has not loaded its Apple Silicon PATH.
find_brew() {
  if command -v brew >/dev/null 2>&1; then command -v brew; return 0; fi
  if [[ -x /opt/homebrew/bin/brew ]]; then printf '%s\n' /opt/homebrew/bin/brew; return 0; fi
  if [[ -x /usr/local/bin/brew ]]; then printf '%s\n' /usr/local/bin/brew; return 0; fi
  return 1
}

BREW="$(find_brew || true)"
# Do not bootstrap Homebrew when the existing toolchain already satisfies all
# checks? Homebrew is required here to install missing package-based libraries.
if [[ -z "$BREW" ]]; then
  [[ "${AZ_SKIP_INSTALL:-0}" != 1 ]] || fail 'Homebrew no disponible (AZ_SKIP_INSTALL=1)'
  [[ "${AZ_AUTO_INSTALL_BREW:-1}" != 0 ]] || fail 'Homebrew no disponible (AZ_AUTO_INSTALL_BREW=0)'
  command -v curl >/dev/null 2>&1 || fail 'curl es necesario para instalar Homebrew'
  info 'Homebrew no esta instalado. Se ejecutara su instalador oficial (puede pedir autorizacion).'
  installer="$(mktemp "${TMPDIR:-/tmp}/akkad-homebrew.XXXXXXXX")"
  trap 'rm -f -- "${installer:-}"' EXIT
  curl --fail --location --show-error --silent \
    https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh \
    --output "$installer" || fail 'no se pudo descargar el instalador oficial de Homebrew'
  /bin/bash "$installer" || fail 'la instalacion de Homebrew no termino correctamente'
  rm -f -- "$installer"
  trap - EXIT
  BREW="$(find_brew || true)"
  [[ -n "$BREW" ]] || fail 'Homebrew instalado pero no se encontro brew'
fi

# Make brew-supplied tools discoverable in current process AND child build.sh.
# shellcheck disable=SC2046
 eval "$("$BREW" shellenv)"
BREW="$(command -v brew)"

# Package names and actual command names differ for pkgconf/protobuf.
# Formula checks also cover headers needed by the LC0 Meson build.
missing=()
require_tool() {
  local executable="$1" formula="$2"
  if ! command -v "$executable" >/dev/null 2>&1; then missing+=("$formula"); fi
}
require_tool git git
require_tool cmake cmake
require_tool meson meson
require_tool ninja ninja
require_tool python3 python
require_tool pkg-config pkgconf
require_tool protoc protobuf

# Eigen is a header-only dependency and cannot be detected as an executable.
if ! "$BREW" list --versions eigen >/dev/null 2>&1; then
  missing+=(eigen)
fi
# Avoid duplicating packages when multiple checks refer to the same formula.
if (( ${#missing[@]} )); then
  unique=()
  for formula in "${missing[@]}"; do
    found=0
    for existing in "${unique[@]:-}"; do
      if [[ "$existing" == "$formula" ]]; then found=1; break; fi
    done
    if (( ! found )); then unique+=("$formula"); fi
  done
  if [[ "${AZ_SKIP_INSTALL:-0}" == 1 ]]; then
    fail "faltan dependencias: ${unique[*]} (AZ_SKIP_INSTALL=1)"
  fi
  info "Instalando dependencias faltantes con Homebrew: ${unique[*]}"
  "$BREW" install --formula "${unique[@]}" || fail 'Homebrew no pudo instalar las dependencias'
else
  info 'Las dependencias detectadas ya estan disponibles.'
fi

# Verify what the shared builder needs after installation.
for tool in git meson ninja python3 cmake pkg-config protoc; do
  command -v "$tool" >/dev/null 2>&1 || fail "falta $tool aun despues de Homebrew"
done
"$BREW" list --versions eigen >/dev/null 2>&1 || fail 'falta eigen aun despues de Homebrew'

info 'Dependencias verificadas. Iniciando compilacion compartida de AlphaZero.'
exec bash "$ROOT/build.sh" --OS MacOS
