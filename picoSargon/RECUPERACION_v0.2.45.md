# picoSargon v0.2.45 - reparacion de fuente compartido

- Restituye `x86/src/grumpy.cpp` con el contenido de la linea de base `akkad(20261107-022632).zip`.
- Actualiza la version de CMake en macOS, Debian y x86 y la version de respaldo C++.
- Antes de configurar CMake, `macOS/build.sh` verifica los cuatro fuentes compartidos.
- No toca `build/` ni mueve fuentes; no se requiere un cleanup.

Aplicar desde la raiz `akkad`, y construir con `./picoSargon/macOS/build.sh`.

Diagnostico adicional: si `git status` muestra `D picoSargon/x86/src/grumpy.cpp`,
la version publicada en Git puede haber borrado el archivo en otra computadora.
Verificar con `git ls-files picoSargon/x86/src/grumpy.cpp`.
