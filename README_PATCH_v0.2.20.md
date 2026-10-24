# picoAlpha v0.2.20 — Fix integración MCTS segmentado (incremental)

## Defecto reproducible
Los logs muestran capacidad inicial 1600, incrementos 512 y requested_bytes 63232: es la rama monolítica. El parche v0.2.19 no contenía `src/mcts.cpp`; por ello una instalación incompleta conservaba una implementación antigua pese a configurar CMake con `PA_SEGMENTED_TREE=ON`.

## Solución
Se incluyen juntos `src/mcts.cpp`, `src/pico_main.cpp` y `CMakeLists.txt`. CMake obliga la ruta segmentada a menos que se solicite expresamente `-DPA_LEGACY_MCTS_TREE=ON`; esta nueva opción evita heredar la caché anterior `PA_SEGMENTED_TREE=OFF`. Hay errores de compilación si faltan las definiciones de CMake para la modalidad elegida. El firmware se identifica como v0.2.20 y emite `BUILD version=0.2.20 MCTS_STORAGE=SEGMENTED initial_capacity=1664 growth_step=128` y `MCTS_STORAGE=SEGMENTED search=N`. No tocar la red neuronal ni el perfilador.

## Instalación
Extraer sobre la **base con v0.2.19 aplicada** respetando la carpeta picoAlpha/. No reemplazar con fuentes anteriores. Reconfigurar CMake y recompilar. Comprobar `-- picoAlpha v0.2.20 MCTS_STORAGE=ON` en CMake y `BUILD ... MCTS_STORAGE=SEGMENTED` en la placa. La telemetría deberá tener capacidad inicial 1664, aumentos de 128 y solicitudes pequeñas. Si persisten 1600/512, el UF2 no corresponde al nuevo build.

## Reversión excepcional
Configurar `-DPA_LEGACY_MCTS_TREE=ON` para seleccionar el algoritmo previo de modo intencional; para restaurar segmentado `-DPA_LEGACY_MCTS_TREE=OFF`. Nunca cambiar `PA_SEGMENTED_TREE` a mano (es variable derivada).

## Alcance / validación
No cambia `net.cpp`, el evaluador TinyGyal, cpuct, tiempo o simulaciones. Se verifican rutas de sintaxis nativas con opciones forzadas, pero no se ha compilado con ARM/Pico SDK ni probado en la placa. No asegura eliminar todo memory_limit; obliga a ejecutar la corrección estructural prevista.
