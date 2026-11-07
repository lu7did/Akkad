# picoSargon v0.2.46 - cabeceras compartidas

Corrige la ausencia de `picoSargon/x86/include/grumpy.hpp` reportada al compilar con AppleClang.
Restituye las tres cabeceras del host (`board.hpp`, `engine.hpp`, `grumpy.hpp`) de la linea de base autorizada `akkad(20261107-022632).zip` y valida fuentes y cabeceras antes de invocar CMake en macOS.
No modifica la implementacion C++ de la busqueda, MULTICORE ni STEROIDS.
El parche debe extraerse en la raiz `akkad` sobre v0.2.45.
