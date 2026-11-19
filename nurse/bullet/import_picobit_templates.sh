#!/usr/bin/env bash
# One-time source import for the three historical picoBit Rust examples.
# Does not modify the external Bullet installation and never overwrites a snapshot.
set -Eeuo pipefail
BASE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$BASE/bullet_runtime.sh"
bullet_resolve_runtime "$BASE" || exit 2
TARGET="$BASE/picobit_genesis"
mkdir -p "$TARGET"
for name in pico_bit_train.rs pico_bit_validate.rs pico_bit_parity.rs; do
  src="$BULLET_DIR/examples/$name";dst="$TARGET/$name"
  [[ -s "$src" ]] || { echo "ERROR: plantilla histórica ausente en $src" >&2;exit 2; }
  if [[ -e "$dst" ]]; then
    cmp -s "$src" "$dst" || echo "AVISO: $dst ya existe y difiere de Bullet; no se sobrescribe." >&2
  else
    cp -- "$src" "$dst"
    echo "IMPORTADO: $dst"
  fi
done
printf '\nPlantillas de referencia incluidas localmente en akkad/nurse/bullet/picobit_genesis.\n'
printf 'Para incorporarlas al repositorio, ejecutar git add nurse/bullet/picobit_genesis desde akkad.\n'
