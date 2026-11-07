# AlphaZero v0.2.1 — Telemetría compartida (X86, Debian, macOS)

El motor reserva **stdout** para UCI. La telemetría humana va exclusivamente a **stderr**.

Al iniciar el motor (después de procesar los argumentos CLI):

```text
⚙️ AlphaZero v0.2.1
⚙️ executable=/ruta/absoluta/AlphaZero
⚙️ network=/ruta/absoluta/weights.pb.gz
```

Si el motor arranca sin un archivo de pesos definido, aparece `(not configured)`. Cuando se recibe `setoption name WeightsFile value ...`, se informa la nueva ruta en **stderr**. El ejecutable se identifica mediante la API del sistema operativo siempre que sea posible. Las rutas relativas de pesos se resuelven desde el directorio de trabajo del proceso, como en el comportamiento original.

Al terminar cada búsqueda iniciada con `go`, **stdout** emite la línea UCI `info ... nodes N time MS nps ... string ALPHAZERO simulations=S tree_nodes=N ...`, seguida de `bestmove ...`. Aquí `nodes` son **expansiones del árbol de búsqueda MCTS (incluida la raíz)** y `nps` usa ese mismo contador; `simulations` son las iteraciones efectivas de MCTS y pueden diferir de `nodes`. Son métricas diferentes, no intercambiables.

**stderr** emite `🧠 AlphaZero analysis ply=P nodes=N simulations=S elapsed_ms=MS nps=... best_visits=...`. Las búsquedas abortadas por error mantienen la ruta UCI `info string ERROR ...` y `bestmove 0000`; no se inventan métricas de una búsqueda fallida.

## Compilación e instalación

Aplicar el ZIP desde `akkad/` y **recompilar cada plataforma**, ya que el cambio está en el archivo C++ compartido:

- macOS: `bash AlphaZero/tools/macOS/build.sh`
- Debian ARM64: `bash AlphaZero/tools/bash/build.sh`
- Windows X86: `powershell -ExecutionPolicy Bypass -File AlphaZero/tools/ps/build.ps1`

No es necesario modificar los scripts `run_listen`: estos invocan al motor C++ por el orquestador Python. Que el listener del orquestador exponga o capture el stderr depende de cómo lance al subproceso.

## Prueba de separación de canales

Con el motor compilado y los pesos presentes:

```bash
{ printf 'uci\nisready\nposition startpos\ngo nodes 10\n'; sleep 3; printf 'quit\n'; } | ./AlphaZero/macOS/build/AlphaZero --weights /ruta/weights.pb.gz --backend eigen >uci.stdout 2>telemetry.stderr
```

Comprobar `uciok`, `readyok`, `info`, `bestmove` solamente en stdout y el encabezado `⚙️` y detalle `🧠` en stderr.
