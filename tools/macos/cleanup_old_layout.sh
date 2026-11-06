#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
OLD="$HERE/../../picoSargon/macOS/picoSargon"
if [[ ! -d "$OLD" ]]; then echo 'No existe estructura antigua. OK'; exit 0; fi
for file in "$OLD"/* "$OLD"/.[!.]* "$OLD"/..?*; do
 [[ -e "$file" ]] || continue
 case "$(basename "$file")" in CMakeLists.txt|README.md|build.sh|run.sh|uci_smoke.sh) ;; *) echo "Archivo no previsto: $file. No se borra." >&2; exit 2;; esac
done
rm -f -- "$OLD/CMakeLists.txt" "$OLD/README.md" "$OLD/build.sh" "$OLD/run.sh" "$OLD/uci_smoke.sh"
rmdir -- "$OLD"
echo 'Estructura obsoleta eliminada.'
