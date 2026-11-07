# AlphaZero v0.2.2 / Sargon-NNUE v0.6.198 — telemetría a través de TCP

## Corrección de integración

- `ExternalUCIPlayer` permite optativamente heredar stderr del proceso nativo; sólo AlphaZero-X86 activa esta opción (los demás players no cambian).
- `AlphaZeroX86UCIPlayer` conserva las líneas `info` emitidas por el motor C++ durante cada `go`.
- `UCISession` reenvía esas líneas `info` al cliente UCI TCP, antes de `bestmove`, y registra una copia `📊 UCI` por stderr del listener; no mezcla ambos canales.
- `stderr` del proceso C++ llega a la consola del listener, por lo que son visibles los encabezados ⚙️ y análisis 🧠 de v0.2.1.
- `stdout` del motor nativo sigue siendo leído sólo por el wrapper UCI, nunca redirigido a stderr.

## Instalación

Descomprimir en la raíz `akkad` tras aplicar parches v0.2.0 y v0.2.1. Reconstruir AlphaZero en cada plataforma para que el binario anuncie v0.2.2 y conserve los informes nativos v0.2.1. Reiniciar el listener para cargar los cambios Python.

## Verificación

`bash AlphaZero/tools/macOS/build.sh`; `bash AlphaZero/tools/macOS/run_listen.sh`. Conectar un cliente UCI: `uci`, `isready`, `position startpos`, `go movetime 500 nodes 50`. Confirmar que `info ... nodes ... time ... nps ... string ALPHAZERO simulations=...` y `bestmove` llegan por TCP; ⚙️ y 🧠 aparecen sólo en la consola del listener. En conexión TCP, `go wtime ... btime ...` usa la configuración del perfil `emma` (no controla directamente el límite del wrapper), que ya era el comportamiento anterior.

Nota: una compilación limpia y un cliente TCP real siguen pendientes de validarse en Mac/Windows/Debian.
