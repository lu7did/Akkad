#!/usr/bin/env bash
# Shared resolver for Akkad/nurse/bullet launchers.
# Sources/configuration live in Akkad; executable Bullet/Cargo/Metal stays outside.
# This file is sourced; do not set shell options or change the caller's CWD.

bullet_resolve_runtime() {
  local source_dir="$1" candidate resolved
  local explicit="${BULLET_DIR:-}"
  local candidates=()
  if [[ -n "$explicit" ]]; then
    candidates+=("$explicit")
  else
    # Preserve the historical capitalisation first, to avoid changing the
    # literal BULLET_DIR value in existing config.lock files.
    candidates+=("$HOME/github/Bobby/bullet" "$HOME/github/bobby/bullet" \
      "$HOME/github/bullet" "$HOME/GitHub/Bobby/bullet")
  fi
  for candidate in "${candidates[@]}"; do
    [[ -d "$candidate/crates/bullet_lib" && -f "$candidate/Cargo.toml" && -d "$candidate/examples" ]] || continue
    resolved="$(cd -- "$candidate" && pwd -P)" || return 2
    if [[ "$resolved" == "$(cd -- "$source_dir" && pwd -P)" ]]; then
      echo 'ERROR: nurse/bullet es un directorio de fuentes, no una instalación de Bullet. Configure BULLET_DIR.' >&2
      return 2
    fi
    BULLET_DIR="$resolved"
    export BULLET_DIR
    return 0
  done
  echo 'ERROR: no se encuentra la instalación externa de Bullet (Cargo.toml, crates/bullet_lib, examples).' >&2
  if [[ -n "$explicit" ]]; then
    echo "  BULLET_DIR especificado: $explicit" >&2
  else
    echo "  Ubicación esperada: $HOME/github/Bobby/bullet (o github/bobby/bullet)" >&2
  fi
  echo '  Ejemplo: BULLET_DIR=/Users/pedrocolla/github/bobby/bullet bash run_genesis_mcts.sh --mon 2' >&2
  return 2
}

# Ensure a Rust example is registered exactly once. The caller must already
# be inside the external Bullet root; name and source are explicit.
bullet_install_example() {
  local name="$1" source_file="$2" destination="examples/$1.rs"
  [[ -s "$source_file" ]] || { echo "ERROR: falta fuente Rust: $source_file" >&2; return 2; }
  [[ -d examples && -f crates/bullet_lib/Cargo.toml ]] || { echo 'ERROR: no estoy en raíz Bullet.' >&2; return 2; }
  cp -- "$source_file" "$destination"
  python3 - "$name" <<'PY'
from pathlib import Path
import re,sys
name=sys.argv[1]
p=Path('crates/bullet_lib/Cargo.toml')
s=p.read_text()
entries=re.findall(r'(?m)^name\s*=\s*"([^"]+)"\s*$',s)
if name not in entries:
    with p.open('a') as f:
        f.write(f'\n[[example]]\nname = "{name}"\npath = "../../examples/{name}.rs"\n')
else:
    # A name occurring in a package attribute is not sufficient. Ensure it is
    # registered as an explicit example, and don't hide a conflicting mapping.
    blocks=re.split(r'(?m)^\[\[example\]\]\s*$',s)[1:]
    matches=[b for b in blocks if re.search(rf'(?m)^name\s*=\s*"{re.escape(name)}"\s*$',b)]
    expected=f'../../examples/{name}.rs'
    if not matches or any(not re.search(rf'(?m)^path\s*=\s*"{re.escape(expected)}"\s*$',b) for b in matches):
        raise SystemExit(f'Conflicto de ejemplo Cargo: {name}. Revisar Cargo.toml')
PY
}

# Persistent output ownership belongs to Akkad, never to external Bullet.
# RUNS_ROOT is intentionally NOT overridable: changing it would break the
# recorded identity of a run. The only external location is the compiler.
bullet_resolve_run_dir() {
  local base="$1" id="$2" dest legacy
  [[ "$id" =~ ^[A-Za-z][A-Za-z0-9_-]*$ ]] || { echo 'RUN_ID inválido' >&2; return 2; }
  dest="$base/runs/$id"
  legacy="$BULLET_DIR/runs/$id"
  if [[ -L "$base/runs" || -L "$dest" ]]; then
    echo 'ERROR: symlink en destino de checkpoints; se exige directorio real dentro de Akkad.' >&2
    return 2
  fi
  # Do not silently restart a completed/partial old run. A fresh destination
  # with no checkpoints/state cannot be assumed to be the same experiment.
  if [[ -d "$legacy" && ! -e "$dest/MON.state" && ! -e "$dest/config.lock" ]]; then
    if [[ -e "$legacy/MON.state" || -e "$legacy/config.lock" || -d "$legacy/checkpoints" ]]; then
      echo "ERROR: corrida $id existente en Bullet externo pero no migrada a Akkad:" >&2
      echo "  Origen: $legacy" >&2
      echo "  Destino: $dest" >&2
      echo "  Ejecutar: bash '$base/migrate_bullet_runs.sh' --run '$id'" >&2
      return 2
    fi
  fi
  printf '%s\n' "$dest"
}
