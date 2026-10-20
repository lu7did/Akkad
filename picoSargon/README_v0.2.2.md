# picoSargon v0.2.2 — parche de compilación

Corregido el fallo observado `fatal error: lwipopts.h: No such file or directory` al compilar la Pico W con SDK 2.3.1.

## Instalar

Copiar `CMakeLists.txt` a la raíz de picoSargon y crear `config/lwipopts.h` usando el archivo del ZIP.
No modificar `build.ps1`, el SDK, compiladores, datos, Grumpy ni el núcleo ajedrecístico.

El CMakeLists ahora añade `config/` al include path del firmware y habilita excepciones de C++ para el código preexistente que emplea `throw` y `try/catch`. Las excepciones se habilitan **solo en el firmware**; no hay modificación de algoritmos.

## Construcción

```powershell
.\build.ps1
```

CMake debe reconfigurar automáticamente al detectar cambios de CMakeLists. Si no lo hace, eliminar únicamente `build-pico-w` y ejecutar de nuevo. Dejar intacta la configuración generada de Wi-Fi.

## Validación

Parche revisado estáticamente contra los archivos exactos de v0.2.1. No fue compilado con Pico SDK en este entorno. Si surge un error diferente, conservar la salida completa de Ninja.
