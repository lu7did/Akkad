
#!/usr/bin/env bash
set -euo pipefail

# ----------------------------------------------------------
# picoSargon - Debian/Raspberry Pi
# Test de integración Python -> UCI -> picoSargon
# ----------------------------------------------------------

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
AKKAD_ROOT="$(cd -- "${SCRIPT_DIR}/../../.." && pwd)"

export AKKAD_ROOT

echo "=============================================="
echo " picoSargon - UCI Integration Test"
echo "=============================================="
echo "Akkad root : ${AKKAD_ROOT}"
echo "Platform   : $(uname -s)"
echo "Machine    : $(uname -m)"
echo

python3 - <<'PY'
import os
import pathlib
import subprocess
import sys
import time

root = pathlib.Path(os.environ["AKKAD_ROOT"]).resolve()

exe = (
    root
    / "picoSargon"
    / "debian"
    / "picoSargon"
    / "build"
    / "picoSargon"
)

weights = (
    root
    / "picoSargon"
    / "debian"
    / "picoSargon"
    / "assets"
    / "grumpy.bin"
)

print(f"Executable : {exe}")
print(f"Network    : {weights}")
print()

if not exe.is_file():
    sys.exit(f"ERROR: No existe el ejecutable: {exe}")

if not weights.is_file():
    sys.exit(f"ERROR: No existe la red neuronal: {weights}")

if not os.access(exe, os.X_OK):
    sys.exit(f"ERROR: El ejecutable no tiene permisos: {exe}")

commands = (
    "uci\n"
    "isready\n"
    "ucinewgame\n"
    "position startpos\n"
    "go depth 3\n"
    "quit\n"
)

print("Iniciando picoSargon...")
print()

start = time.monotonic()

try:
    result = subprocess.run(
        [str(exe), "--weights", str(weights)],
        input=commands,
        text=True,
        capture_output=True,
        timeout=60,
        cwd=str(exe.parent),
    )
except subprocess.TimeoutExpired:
    sys.exit("ERROR: Timeout de 60 segundos")
except OSError as exc:
    sys.exit(f"ERROR: No se pudo iniciar picoSargon: {exc}")

elapsed = time.monotonic() - start

print("--------------- STDOUT ----------------")
print(result.stdout)

if result.stderr:
    print("--------------- STDERR ----------------")
    print(result.stderr)

print("---------------------------------------")
print(f"Exit code : {result.returncode}")
print(f"Elapsed   : {elapsed:.3f} s")
print()

checks = {
    "Proceso finalizado correctamente": result.returncode == 0,
    "UCI inicializado": "uciok" in result.stdout,
    "Motor preparado": "readyok" in result.stdout,
    "Busqueda completada": "bestmove " in result.stdout,
    "Jugada disponible": "bestmove (none)" not in result.stdout,
}

failed = False

for name, passed in checks.items():
    print(f"{'OK' if passed else 'FAIL'} - {name}")
    if not passed:
        failed = True

print()

if failed:
    sys.exit("RESULTADO: INTEGRACION FALLIDA")

print("RESULTADO: INTEGRACION UCI CORRECTA")
PY


