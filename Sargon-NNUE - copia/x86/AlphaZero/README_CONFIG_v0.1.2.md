# AlphaZero-X86: configuración y telemetría

`src/config.h` centraliza los defaults compilados. Precedencia: **`config.h` < argumentos CLI < `setoption` UCI < límites `go`** (únicamente `nodes` y `movetime`).

- `kWeightsFile`: ruta de la red LC0 `.pb.gz`, vacía por defecto; se exige antes de evaluar.
- `kBackend`/`kBackendOptions`: `onnx-dml` / `gpu=0` por defecto; `--backend eigen` permite CPU.
- `kSimulations`: 1000 simulaciones MCTS; UCI `info nodes` contabiliza **simulaciones completadas** igual que `MoveChoice.nodes` de Python.
- `kMaxTreeNodes`: 0 (sin límite); cuenta expansiones incluida la raíz; se informa como `tree_nodes` en `info string`.
- `kTMaxMs`: 10000 ms por búsqueda; `kTimeoutMs`: 60000 ms, techo de tiempo por búsqueda (0 lo desactiva).
- `kCpuct`: 1.5; `kVerbose`: 1; `kUciName`/`kUciAuthor`: nombre y autor del protocolo.

Ejemplo:

```powershell
.\build.ps1
.\build\AlphaZero.exe --weights "C:\nets\t1.pb.gz" --backend onnx-dml --backend-options gpu=0 --simulations 1000 --max-tree-nodes 0 --tmax 10000 --timeout 60000
```

Opciones UCI: `WeightsFile`, `Backend`, `BackendOptions`, `Simulations`, `MaxTreeNodes`, `Cpuct`, `TMax`, `Timeout`, `Verbose`.

Ejemplo de respuesta:

```text
info depth 0 nodes 1000 time 6200 score cp 37 string ALPHAZERO simulations=1000 tree_nodes=722 elapsed_ms=6200 best_visits=540 q=0.09
bestmove e2e4
```

Los números del ejemplo ilustran el formato, no son medidas de una ejecución real. `info nodes` y `simulations` son el mismo contador deliberadamente. La búsqueda sigue siendo autónoma y la inferencia se realiza mediante la API de LCZero, no mediante `lc0.exe`.
