# Sargon-NNUE v0.6.169 — TinyGyal PyTorch independiente (beta para validación)

Este parche REEMPLAZA el wrapper tinygyal de v0.6.167 por inferencia PyTorch independiente. No invoca `lc0.exe`, `lczero-bindings` ni `LC0Evaluator`; implementa localmente el tipo de resultado y la conversión WDL compatibles con AlphaZero. Carga `tinygyal-8.pb.gz` externo.

## Estado y advertencia
Es un **evaluador ejecutable experimental**, no se garantiza aún paridad LC0/Eigen. Los 112 planos, tratamiento de historial y política se implementaron desde los formatos LC0, pero deben contrastarse con las nueve referencias del usuario. No usar para clasificación ELO definitiva antes de esa prueba. El motor puede seleccionar jugadas diferentes hasta cerrar la paridad de codificación/política. No se han ejecutado aquí MATCH ni inferencia con python-chess (dependencia ausente en el contenedor).

## Requisitos
Python con `numpy`, `torch`, `python-chess` (existentes en el entorno Sargon-NNUE del usuario). Mantener red real externa; el ZIP no la incorpora.

## Configuración
Se usa el mismo perfil v0.6.167 y `evaluator=tinygyal`, `network=<ruta>/tinygyal-8.pb.gz`. `lc0-backend` acepta `eigen`, `auto` o `cpu` -> PyTorch CPU, y `xpu` -> PyTorch Intel XPU cuando está disponible. El nombre de parámetro se conserva por compatibilidad con brains.json; no se usa backend LC0.

## Ejecutar prueba de paridad
`python scripts/test_tinygyal_parity.py --network RUTA/tinygyal-8.pb.gz --reference tinygyal_lc0_eigen_reference.json`

La prueba reporta para cada FEN el error de Q, el máximo error de P, y si los movimientos legales coinciden; devuelve error si no pasa tolerancias (`--q-tol`, `--p-tol`). No corrige ni disimula discrepancias. Primero ejecutar esto, después BENCHMARK y MATCH.

## No modificados
`players/alphazero.py`, `evaluators/lc0.py`, directorios `data` y `docs`. Registro del evaluador se conserva de v0.6.167 y no necesita cambios adicionales cuando esa versión está aplicada.
