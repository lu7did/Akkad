#!/usr/bin/env bash
set -Eeuo pipefail

# AlphaZero ARM64 / Akkad - Benchmark de emma en Sargon-NNUE.
# No modifica el brains.json original: crea una configuracion temporal.
# Uso: ./run_benchmark.sh [numero_de_posiciones]
# Variables: BENCH_POSITIONS, BENCH_ROUNDS, BENCH_WARMUP, BENCH_TIMEOUT,
#            AZ_SIMULATIONS, AZ_TMAX, AZ_BACKEND, AZ_WEIGHTS, ALPHAZERO_EXE,
#            BRAINS_JSON, PYTHON_BIN, BENCH_VERBOSE.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
AKKAD_ROOT="$(cd -- "${SCRIPT_DIR}/../../.." && pwd -P)"
SARGON_ROOT="${AKKAD_ROOT}/Sargon-NNUE"

if [[ ! -d "${SARGON_ROOT}/src/sargon_nnue" ]]; then
  echo "ERROR: No existe Sargon-NNUE/src/sargon_nnue en ${SARGON_ROOT}" >&2
  exit 1
fi

BRAINS_JSON="${BRAINS_JSON:-${SARGON_ROOT}/data/brains/brains.json}"
ALPHAZERO_EXE="${ALPHAZERO_EXE:-${AKKAD_ROOT}/AlphaZero/build/AlphaZero}"
AZ_WEIGHTS="${AZ_WEIGHTS:-${SARGON_ROOT}/data/runs/lc0/t1-256x10-distilled-swa-2432500.pb.gz}"
AZ_BACKEND="${AZ_BACKEND:-eigen}"
AZ_SIMULATIONS="${AZ_SIMULATIONS:-8}"
AZ_TMAX="${AZ_TMAX:-30000}"
BENCH_POSITIONS="${1:-${BENCH_POSITIONS:-3}}"
BENCH_ROUNDS="${BENCH_ROUNDS:-1}"
BENCH_WARMUP="${BENCH_WARMUP:-1}"
BENCH_TIMEOUT="${BENCH_TIMEOUT:-180}"
BENCH_VERBOSE="${BENCH_VERBOSE:-1}"

if [[ -z "${PYTHON_BIN:-}" ]]; then
  if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
    PYTHON_BIN="${VIRTUAL_ENV}/bin/python"
  elif [[ -x "/home/pi/chess/picoSargon/bin/python" ]]; then
    PYTHON_BIN="/home/pi/chess/picoSargon/bin/python"
  else
    PYTHON_BIN="$(command -v python3 || true)"
  fi
fi

for target in "$BRAINS_JSON" "$ALPHAZERO_EXE" "$AZ_WEIGHTS"; do
  [[ -f "$target" ]] || { echo "ERROR: No existe $target" >&2; exit 1; }
done
[[ -x "$ALPHAZERO_EXE" ]] || { echo "ERROR: AlphaZero no es ejecutable: $ALPHAZERO_EXE" >&2; exit 1; }
[[ -n "$PYTHON_BIN" && -x "$PYTHON_BIN" ]] || { echo "ERROR: Python no encontrado" >&2; exit 1; }
for item in "$AZ_SIMULATIONS" "$AZ_TMAX" "$BENCH_POSITIONS" "$BENCH_ROUNDS" "$BENCH_WARMUP" "$BENCH_TIMEOUT"; do
  [[ "$item" =~ ^[0-9]+$ ]] || { echo "ERROR: Se esperaba un entero no negativo: $item" >&2; exit 1; }
done

# tmp junto a brains.json, para mantener la resolucion de rutas relativas
# en los otros brains; emma se reescribe completamente con rutas absolutas.
TMP_BRAINS="$(mktemp "$(dirname "$BRAINS_JSON")/.emma_arm64_XXXXXXXX.json")"
trap 'rm -f -- "$TMP_BRAINS"' EXIT

"$PYTHON_BIN" - "$BRAINS_JSON" "$TMP_BRAINS" "$ALPHAZERO_EXE" "$AZ_WEIGHTS" "$AZ_BACKEND" "$AZ_SIMULATIONS" "$AZ_TMAX" <<'PY'
import json
import sys
from pathlib import Path

source, target, exe, weights, backend, simulations, tmax = sys.argv[1:]
with open(source, encoding="utf-8") as f:
    data = json.load(f)
brains = data.get("brains", {})
if "emma" not in brains:
    raise SystemExit("ERROR: No existe el brain emma en brains.json")
emma = brains["emma"]
emma.update({
    "player": "AlphaZero-X86",
    "evaluator": "null",
    "engine-path": str(Path(exe).resolve()),
    "lc0-weights": str(Path(weights).resolve()),
    "lc0-backend": backend,
    "az-simulations": int(simulations),
    "tmax": int(tmax),
})
# Evitar opciones propias de DirectML (gpu=0) en el backend CPU.
emma.pop("lc0-backend-options", None)
with open(target, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
PY

export PYTHONPATH="${SARGON_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"
"$PYTHON_BIN" -c 'import sargon_nnue.sargon_benchmark' || {
  echo "ERROR: No se puede importar sargon_nnue.sargon_benchmark" >&2; exit 1;
}

printf '\n===== Benchmark emma / Debian ARM64 =====\n'
printf 'Python       : %s\n' "$PYTHON_BIN"
printf 'Ejecutable   : %s\n' "$ALPHAZERO_EXE"
printf 'Pesos        : %s\n' "$AZ_WEIGHTS"
printf 'Backend      : %s\n' "$AZ_BACKEND"
printf 'Simulaciones : %s\n' "$AZ_SIMULATIONS"
printf 'Posiciones   : %s\n' "$BENCH_POSITIONS"
printf 'Rondas       : %s\n' "$BENCH_ROUNDS"
printf 'Calentamiento: %s\n' "$BENCH_WARMUP"
printf 'Timeout      : %s s\n\n' "$BENCH_TIMEOUT"

cmd=("$PYTHON_BIN" -m sargon_nnue.sargon_benchmark
  --brain "$TMP_BRAINS" --ids emma --mode positions
  --positions "$BENCH_POSITIONS" --rounds "$BENCH_ROUNDS"
  --warmup "$BENCH_WARMUP" --timeout "$BENCH_TIMEOUT"
  --python "$PYTHON_BIN")
if [[ "$BENCH_VERBOSE" == 1 ]]; then cmd+=(--verbose); fi
cd -- "$SARGON_ROOT"
"${cmd[@]}"

