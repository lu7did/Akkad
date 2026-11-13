# MCTSP / MCTSE — v0.1.2

El brain `picoalpha_mcts` es `type=nurse`, player `MCTSP`, evaluator `MCTSE`.
La red `network` debe señalar a `best.pt` producido por `picoAlpha/tools/train/train.py`.
En `nurse/etc/brains/brains.json`, ruta relativa a `nurse/etc/brains/`:
`../../../picoAlpha/assets/checkpoints/best.pt`. Si no existe, Nurse falla de forma explícita.

Parámetros: `arguments.sims` (presupuesto de simulaciones), `arguments.depth` (máximo de plies MCTS), `arguments.cpuct` (exploración); `tmax` presupuesto de pensamiento y `timeout` máximo adicional de seguridad (el MCTSP corta en `min(tmax,timeout)`). La capa Nurse sigue tratando `timeout` como límite de comunicación.

La NNUE FP32 780×16 se carga **una vez** al iniciar; no se admiten redes aleatorias de respaldo. Política: `softmax(from[src]+to[dst])` sólo en jugadas legales; valor en [-1,1] desde perspectiva del turno. PUCT selecciona por `Q+U` y retropropaga cambiando signo por ply. Terminales: mate/tablas usando python-chess. Control de profundidad, sims y reloj monotónico. No modifica la implementación legacy de Nurse ni `picoAlpha/Crypt`.

`info depth ... nodes ... time ... nps ... score cp ...` y `info string MCTSP simulations=... nodes=... time=... value=...` se emiten por UCI; logs detallados por stderr. `nodes` representa nodos asignados al árbol, no nodos explorados una vez cada uno; `simulations` cuenta simulaciones completas. `score cp` es aproximación monotónica `400*atanh(value)` para UCI, **no** una evaluación Stockfish.

Limitaciones: checkpoint FP32 (INT8 queda para ARM); la política factoriza origen/destino y no diferencia promociones con casillas iguales; python-chess recibe FEN, por lo que una posición cargada sólo mediante FEN no conserva historial de repetición previo a la raíz. El límite temporal se verifica entre operaciones: una evaluación PyTorch en curso no puede interrumpirse inmediatamente. La ruta configurada es ejemplo y debe existir antes de usar el brain.
