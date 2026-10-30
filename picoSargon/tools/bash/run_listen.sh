#!/usr/bin/env bash
set -Eeuo pipefail

# Akkad / picoSargon - Servidor UCI TCP Debian / Raspberry Pi
# Ubicacion: Akkad/picoSargon/tools/bash/run_listen.sh
# Uso: ./run_listen.sh [brain_id] [puerto] [host]
# Ejemplo: ./run_listen.sh tinySargon 6200 0.0.0.0

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
AKKAD_ROOT="$(cd -- "$SCRIPT_DIR/../../.." && pwd -P)"
SARGON_ROOT="$AKKAD_ROOT/Sargon-NNUE"
BRAINS_JSON="$SARGON_ROOT/data/brains/brains.json"

BRAIN_ID="${1:-${LISTEN_BRAIN:-tinySargon}}"
PORT="${2:-${LISTEN_PORT:-6200}}"
HOST="${3:-${LISTEN_HOST:-0.0.0.0}}"
PYTHON_BIN="${LISTEN_PYTHON:-${VIRTUAL_ENV:+$VIRTUAL_ENV/bin/python}}"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"

[[ -f "$BRAINS_JSON" ]] || { echo "ERROR: No existe $BRAINS_JSON" >&2; exit 1; }
[[ "$PORT" =~ ^[0-9]+$ ]] && (( 10#$PORT >= 1 && 10#$PORT <= 65535 )) || {
  echo "ERROR: puerto TCP invalido: $PORT" >&2; exit 2;
}
[[ -x "$PYTHON_BIN" ]] || { echo "ERROR: interprete Python no ejecutable: $PYTHON_BIN" >&2; exit 1; }
PYTHON_BIN="$("$PYTHON_BIN" -c 'import sys; print(sys.executable)')"

# La ruta de Sargon-NNUE/src debe estar registrada en la venv.
"$PYTHON_BIN" -c 'import sargon_nnue.sargon_listen' || {
  echo 'ERROR: No se encuentra sargon_nnue.sargon_listen en esta venv.' >&2
  exit 1
}

# Validar el perfil usando el resolvedor del proyecto (incluye seleccion de rutas Debian).
"$PYTHON_BIN" - "$BRAINS_JSON" "$BRAIN_ID" <<'PY'
import sys
from pathlib import Path
from sargon_nnue.brains import get
p, name = sys.argv[1:3]
try:
    cfg = get(p, name)
    if cfg.get('player') != 'picosargon':
        raise ValueError(f"{name} usa player={cfg.get('player')!r}, se esperaba 'picosargon'")
    for key in ('engine-path', 'network'):
        path = cfg.get(key)
        if not path or not Path(str(path)).is_file():
            raise ValueError(f'{key} no existe: {path}')
    print(f"Brain        : {name}")
    print(f"Executable   : {cfg['engine-path']}")
    print(f"Grumpy       : {cfg['network']}")
except (ValueError, OSError, KeyError) as exc:
    sys.exit(f'ERROR: configuracion de brain: {exc}')
PY

echo '============================================'
echo ' Akkad / picoSargon - UCI TCP Listener'
echo '============================================'
echo "Python       : $PYTHON_BIN"
echo "Brains JSON  : $BRAINS_JSON"
echo "Host         : $HOST"
echo "Port         : $PORT"
echo "Conexiones   : multisesion; Ctrl+C para detener"
echo
if [[ "$HOST" == '0.0.0.0' ]]; then
  echo 'AVISO: accesible desde las interfaces de red de la Raspberry Pi.'
  echo 'Usar solo en LAN confiable o restringir acceso con firewall.'
  echo
fi

cd "$SARGON_ROOT"
exec "$PYTHON_BIN" -m sargon_nnue.sargon_listen \
  --mode TCP \
  --host "$HOST" \
  --port "$PORT" \
  --brain "$BRAINS_JSON" \
  --id "$BRAIN_ID"
