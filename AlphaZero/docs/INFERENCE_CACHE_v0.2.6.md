# AlphaZero v0.2.6 — verificación de pool persistente

El código v0.2.5 conserva las instancias `LC0Inference` por proceso. Una carga de pesos ocho veces después de cada `go` no coincide con ese código cuando el pool ya está preparado. La causa más probable es un binario desactualizado; también debe descartarse que se inicie un proceso nuevo por jugada.

El lanzador macOS bloquea binarios que no respondan `id name AlphaZero v0.2.6` al comando UCI `uci`. Esto evita ejecutar silenciosamente una versión anterior.

El motor emite `⚙️ AlphaZero backend_pool new=N reused=M` a stderr en cada búsqueda. Con `--cores 8` la primera búsqueda tendrá normalmente `new=7 reused=1` (la instancia principal se preparó previamente); las siguientes deben mostrar `new=0 reused=8` salvo cambio de pesos o backend. `ucinewgame`, `position`, `BatchSize`, `Cores` no invalidan la caché.

Validación: después de instalar desde la raíz del repositorio, ejecutar `bash AlphaZero/tools/macOS/build.sh` y reiniciar el listener. Confirmar que el cliente TCP permanece conectado durante varias jugadas. Si se observan nuevas cargas, adjuntar las líneas `backend_pool`, `network`, `id name` y la hora de inicio de proceso.

Nota: esta verificación prueba reutilización de objetos, no garantiza compartir memoria física de pesos entre trabajadores ni ausencia de cargas por otras instancias simultáneas del motor.
