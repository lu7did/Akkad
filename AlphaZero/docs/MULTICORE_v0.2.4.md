# AlphaZero v0.2.4 — CPU MULTICORE (root parallel)

## Alcance

MULTICORE está compilado por defecto (`AZ_MULTICORE=ON` en macOS/Debian;
`-MultiCore ON` en Windows). Desactivar: `AZ_MULTICORE=OFF` al compilar
Unix o `-MultiCore OFF` en Windows. La opción `--cores N` selecciona a lo sumo
min(N, hardware_concurrency) trabajadores. Cores=1 y backends no CPU usan
un solo árbol. Los valores efectivos figuran en `stderr`.

En CPU, para N>1, cada trabajador dispone de un árbol MCTS privado y un backend
LC0 privado. La inferencia inicial de la raíz se comparte para asegurar
prioridades iniciales consistentes. El presupuesto global se reparte en cuotas
enteras, el plazo temporal es común y se agregan visitas y sumas Q por jugada
antes de elegir el `bestmove`. Ningún trabajador modifica un nodo ajeno.

**Limitación:** esto es *root parallelization*, no un árbol compartido con
virtual loss entre threads. Los trabajadores no se comunican sus visitas durante
la búsqueda, sólo al sincronizar al final. Su beneficio depende del coste de
crear varios backends; en Raspberry Pi la memoria puede impedir N grande.

## UCI y scripts

- Motor: `--cores 4` o `setoption name Cores value 4` (antes de `go`).
- Listener: `run_listen.sh --cores 4` o `run_listen.ps1 -Cores 4`.
- Para probar mononúcleo, `--cores 1`.
- CPU `eigen`, `blas`, `dnnl`: se habilita multihilo si compilado ON.
- GPU `onnx-dml`: se mantiene un solo árbol por seguridad y política.
- `stdout`: exclusivamente `uciok`, `readyok`, `info ...`, `bestmove ...`.
- `stderr`: configuración ⚙️, por-core 🧠 y agregados 🧠.

## Validación obligatoria en plataforma

Comparar la misma FEN con `--cores 1/2/4`, simulaciones y límites iguales;
verificar sumatoria simulaciones por núcleo <= presupuesto,
`bestmove` legal, terminación ante `stop`, comportamiento por TMax y memoria
residente. No se garantiza aceleración lineal ni compilación LC0 sin probar.
