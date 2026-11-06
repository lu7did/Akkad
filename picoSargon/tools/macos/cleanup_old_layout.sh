#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd -- "$HERE/../../.." && pwd -P)"
OLD="$ROOT/tools/macos"
if [[ ! -d "$OLD" ]]; then echo "OK: No existe $OLD"; exit 0; fi
command -v shasum >/dev/null || { echo 'Falta shasum' >&2; exit 1; }
removed=0
for file in "$OLD"/* "$OLD"/.[!.]* "$OLD"/..?*; do
  [[ -f "$file" ]] || { [[ -e "$file" ]] && echo "Conservado elemento no regular: $file"; continue; }
  name="$(basename "$file")"; expected=""
  case "$name" in
    cleanup_old_layout.ps1) expected="378fb7d2cf7a2caee484ce5a1f5c84d3c6f99f949661a53c2ea056e3d590eaa0" ;;
    cleanup_old_layout.sh) expected="70e49015bb6b4669f28ddd692687c90082ccb6046dd47fce8cdc44b2d226cc66" ;;
    run.sh) expected="38cc07e09b3d9ddbc01c7231aac4b7465b25f764061d9d376e372e13abdd3e62" ;;
    run_listen.sh) expected="d0810a64791df4c7e76b6c3556aadca40eb37e65ea0bfda4e69026bd5695145c" ;;
    tcp_smoke.sh) expected="9edd88d1046cf8287430427a3a1b72d42c959f82b93ad830f3aa1832cafa47bd" ;;
    uci_smoke.sh) expected="469cc1b2479b75418370c920308f606e3f82957c7dba792667e02810ab0b5a15" ;;
    uci_tcp_server.py) expected="7b1c049172a619b69121bf2fb36fdf9fc5109d20124539b789dc83cfbdc5fafa" ;;
    *) echo "Conservado archivo desconocido: $file"; continue ;;
  esac
  current="$(shasum -a 256 "$file" | awk '{print $1}')"
  if [[ "$current" == "$expected" ]]; then
    rm -- "$file"; echo "Eliminado archivo antiguo verificado: $file"; removed=$((removed+1))
  else
    echo "Conservado archivo modificado: $file"
  fi
done
rmdir "$OLD" 2>/dev/null || true
rmdir "$ROOT/tools" 2>/dev/null || true
# Older v0.2.34 layout cleanup, only when its contents are identical to the published package.
OLDN="$ROOT/picoSargon/macOS/picoSargon"
if [[ -d "$OLDN" ]]; then
  echo "Aviso: estructura v0.2.34 presente: $OLDN; no se elimina automáticamente."
fi
printf 'Limpieza completada: %d archivo(s) antiguos verificados eliminados.\n' "$removed"
