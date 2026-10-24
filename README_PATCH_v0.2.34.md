# picoAlpha v0.2.34 — Limpieza de telemetría

Parche incremental sobre v0.2.33. Mantiene kernels neuronales, búsqueda, configuración de un núcleo y Node de 20 bytes.

- Cabecera única con estado watchdog, simulaciones, cpuct, timeout y capacidad compilada.
- Si el reboot proviene del watchdog, WD_LAST aparece inmediatamente después de cabecera.
- SEARCH ID / MCTS begin / MCTS done / MEM BEFORE / MEM AFTER siempre disponibles con DEBUG=ON.
- Tres opciones de compilación independientes: PA_TELEM_MCTS, PA_TELEM_MEM, PA_TELEM_NN, todas ON por defecto; NN_PROFILE depende también de PA_NN_PROFILE.
- UCI trace sale con UCI o DEBUG habilitado.
- AZ_MAX_NODES=8576 en Pico 2 W, alineado con PA_STATIC_TREE_NODES=8576. La Pico W experimental conserva su valor 320.
- MCTS GUARDS usa depth_err (contador) y depth (máximo) para evitar dos campos con el mismo nombre.
- El valor de scratch y el progreso del watchdog se preservan; no se altera la lógica de recuperación.

Verificación: compilación de sintaxis nativa para MCTS, Board, Network; revisión automática de cadenas de formato. La compilación de firmware ARM no se ejecutó.
