#!/usr/bin/env bash
# Native Debian/Raspberry Pi UCI/TCP listener, v0.2.51. No Python.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT="$(cd -- "$HERE/../.." && pwd -P)"
LISTENER="$PROJECT/debian/build/picoSargon_listen"
ENGINE="$PROJECT/debian/build/picoSargon"
WEIGHTS="$PROJECT/debian/assets/grumpy.bin"
# Forward --help even before binaries have been built.
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'HELP'
picoSargon Debian/Raspberry Pi v0.2.51, listener TCP nativo (C++)
Uso: ./picoSargon/tools/bash/run_listen.sh [opciones]
  --host IP        IP de escucha, por defecto 0.0.0.0
  --port N         Puerto, por defecto 6200
  --cores N        Obligatorio si MULTICORE=ON
  --depth N        Profundidad maxima de busqueda (1..40)
  --qdepth N       Profundidad quiescencia (0..32)
  --timeout MS     Tiempo maximo (milisegundos)
  --brains FILE    Perfil brains.json (alternativo a --weights)
  --brain NAME     Perfil dentro de brains.json
  --weights FILE   Red NNUE; default debian/assets/grumpy.bin
  --help           Mostrar ayuda
Los parametros se transmiten al motor C++ por conexion TCP.
stdout del motor = UCI puro al cliente; stderr = diagnostico humano.
HELP
  exit 0
fi
[[ -x "$LISTENER" && -x "$ENGINE" ]] || {
 echo "Falta ejecutable nativo: ejecutar picoSargon/tools/bash/build.sh" >&2;exit 1;
}
ARGS=(--engine "$ENGINE")
if [[ " $* " == *" --brains "* ]]; then
  : # The native listener will use the selected brains.json profile.
elif [[ " $* " == *" --weights "* ]]; then
  :
else
  ARGS+=(--weights "$WEIGHTS")
fi
exec "$LISTENER" "${ARGS[@]}" "$@"
