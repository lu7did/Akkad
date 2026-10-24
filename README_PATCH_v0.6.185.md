# Sargon-NNUE v0.6.185 — Configuración AlphaZero-X86 unificada

Este parche aplica sobre v0.6.184 y el adaptador AlphaZero-X86 de v0.1.1. No altera el motor C++ ni Sophie.

AlphaZero-X86 acepta los mismos campos de red y búsqueda que Sophie: `lc0-weights`, `lc0-backend`, `lc0-backend-options`, `az-simulations`, `az-cpuct`, `tmax`. Se incluye `timeout` para controlar espera de respuesta del proceso UCI independiente. El motor C++ recibe además su UCI `setoption Timeout`.

## Emma

```json
"emma": {
  "player": "AlphaZero-X86",
  "evaluator": "null",
  "engine-path": "../x86/AlphaZero/build/AlphaZero.exe",
  "lc0-weights": "../data/runs/lc0/t1-256x10-distilled-swa-2432500.pb.gz",
  "lc0-backend": "onnx-dml",
  "lc0-backend-options": "gpu=0",
  "az-simulations": 1200,
  "az-cpuct": 1.5,
  "tmax": 10000,
  "timeout": 60000,
  "rating_elo": 400
}
```

Se preserva `network` como alias antiguo de `lc0-weights` para compatibilidad, y se prioriza `lc0-weights` si ambos existen.

`engine-path` no es un camino hacia LC0: identifica a `AlphaZero.exe`, proceso UCI autónomo que implementa su propio MCTS y llama a la API neuronal LCZero internamente. No se invoca `lc0.exe`.

`az-simulations` controla el máximo de simulaciones (UCI `go nodes`); `info nodes` contabiliza simulaciones completas y los nodos reales de árbol se informan por separado. `tmax` es el presupuesto de búsqueda; `timeout` es el máximo de espera del adaptador. La igualdad de parámetros no implica idénticos nodos recorridos ni duración por usar runtimes diferentes.

Para igualar el límite del adaptador también en Sophie, puede agregarse `"timeout": 60000` al brain Sophie si el launcher lo utiliza como timeout operativo.
