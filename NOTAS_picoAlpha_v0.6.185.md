# Parche incremental v0.6.185 — picoAlpha

Se corrige el error `,,` en `generated_tinygyal.hpp` y el generador `convert_tinygyal.py`, que ahora divide por grupos completos de 32 bytes.

Se verificaron 1.097.572 literales de bytes, sin comas duplicadas, y sintaxis correcta mediante compilacion C++17 (`g++ -fsyntax-only`).
No se altera el contenido binario de la red ni los algoritmos del firmware.
Extraer sobre la carpeta que contiene `Akkad/`, reemplazando los archivos.
