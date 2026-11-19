#!/usr/bin/env bash
# Copy verified historical runs into Akkad, without deleting originals.
set -Eeuo pipefail
BASE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source "$BASE/bullet_runtime.sh"
bullet_resolve_runtime "$BASE"
usage(){ cat <<'EOF'
Uso: bash migrate_bullet_runs.sh --run RUN_ID [--run RUN_ID ...]
     bash migrate_bullet_runs.sh --all
Copia ejecuciones completas desde Bullet/runs a akkad/nurse/bullet/runs.
No modifica ni borra originales. No fusiona ni sobreescribe destinos.
Verifica por comparación binaria recursiva (diff -qr).
La opción --all incluye TODAS las corridas en Bullet/runs, incluso no Akkad.
EOF
}
ids=(); all=0
while (($#));do
 case "$1" in
  --run) (($#>=2)) || { usage >&2;exit 2; };ids+=("$2");shift 2;;
  --all) all=1;shift;;
  -h|--help)usage;exit 0;;
  *)echo "Argumento desconocido: $1" >&2;exit 2;;
 esac
done
((all==0 || ${#ids[@]}==0)) || { echo 'No combinar --all y --run' >&2;exit 2; }
if ((all));then
 shopt -s nullglob
 for d in "$BULLET_DIR"/runs/*;do [[ -d "$d" && ! -L "$d" ]] && ids+=("${d##*/}");done
fi
((${#ids[@]}>0)) || { echo 'Indicar --run o --all' >&2;exit 2; }
[[ ! -L "$BASE/runs" ]] || { echo 'Destino runs es un enlace simbólico' >&2;exit 2; }
mkdir -p "$BASE/runs"
for id in "${ids[@]}";do
 [[ "$id" =~ ^[A-Za-z][A-Za-z0-9_-]*$ ]] || { echo "RUN_ID inválido: $id" >&2;exit 2; }
 from="$BULLET_DIR/runs/$id"; to="$BASE/runs/$id"
 [[ -d "$from" && ! -L "$from" ]] || { echo "Origen ausente o symlink: $from" >&2;exit 2; }
 [[ ! -e "$to" && ! -L "$to" ]] || { echo "Destino ya existe: $to (no se mezcla)" >&2;exit 2; }
 # copy to a temporary directory inside destination volume, then verify.
 stage="$BASE/runs/.${id}.migrating.$$"
 [[ ! -e "$stage" ]] || exit 2
 echo "⚙️ Copiando $from → $to"
 mkdir "$stage"
 # cp -pR src/. dest/ preserves all content, including optimiser state.
 if ! cp -pR "$from/." "$stage/";then
   echo "ERROR de copia; inspeccionar $stage" >&2;exit 3
 fi
 if ! diff -qr "$from" "$stage";then
   echo "ERROR: copia difiere del origen; inspeccionar $stage" >&2;exit 3
 fi
 mv "$stage" "$to"
 echo "✅ Migración verificada: $to"
done
