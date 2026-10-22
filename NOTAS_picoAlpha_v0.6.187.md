# Akkad picoAlpha v0.6.187 - parche incremental

Problema confirmado: `MemoryStat read_memory()` en `src/pico_main.cpp` empleaba un tipo no definido.
La función no tenía llamadas en el firmware. Se retira solo esa función muerta, sin modificar MCTS, inferencia, WiFi, UCI ni telemetría utilizada.

Aplicar sobre v0.6.186 en la raíz que contiene `Akkad`, sobreescribiendo el archivo.
Repetir: `cd Akkad\picoAlpha; .\build.ps1`.

Verificaciones: inspección del único uso de MemoryStat y de read_memory, ausencia de las referencias en el parche; ZIP íntegro. No se dispone del toolchain ARM para certificar la compilación UF2.
