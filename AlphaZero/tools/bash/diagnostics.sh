#!/usr/bin/env bash
set -Eeuo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
echo "OS: $(uname -srmo)"
echo "Cores: $(nproc)"
free -h
for command in cmake meson ninja git g++ protoc; do if command -v "$command" >/dev/null; then echo "$command: $(command -v "$command")"; else echo "FALTA: $command"; fi; done
if [[ -f "$ROOT/build/AlphaZero" ]]; then
  file "$ROOT/build/AlphaZero"
  ldd "$ROOT/build/AlphaZero" || true
else echo "Ejecutable aún no compilado"; fi
