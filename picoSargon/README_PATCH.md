# picoSargon x86 v0.2.15 — lectura nativa de brains.json

Este parche pertenece al **proyecto picoSargon**, no a Sargon-NNUE. Se aplica en la raíz del proyecto `picoSargon` y cambia `x86/picoSargon/src/host_main.cpp` y `x86/picoSargon/CMakeLists.txt`.

## Modificación

El ejecutable **C++** puede leer directamente `brains.json` y extraer `brains[tinySargon].network` para cargar el binario Grumpy mediante `Grumpy::load()`. No ejecuta Python ni LC0. Mantiene interfaz UCI y carga de Grumpy desde archivo binario externo.

```powershell
# Invocación nativa independiente
.\build\picoSargon.exe --brains "C:\ruta\Sargon-NNUE\data\brains.json" --brain tinySargon

# Compatibilidad anterior
.\build\picoSargon.exe "C:\ruta\grumpy.bin"

# Opcional, ruta explícita
.\build\picoSargon.exe --weights "C:\ruta\grumpy.bin"
```

`network` relativo se resuelve primero según el directorio de trabajo; luego en relación con el directorio del JSON y ubicaciones habituales de `scripts/`. Se rechazan rutas inexistentes o claves ausentes. El propio lector Grumpy valida el formato de la red.

## Integración con match

Importante: Sargon-NNUE sigue siendo quien arranca el proceso. El adaptador Python de Sargon-NNUE v0.6.180 ya lee `network` y lo pasa como argumento posicional; esa modalidad se mantiene compatible. El nuevo `--brains` permite ejecutar `picoSargon.exe` leyendo directamente el archivo JSON; **no cambia por sí solo cómo el adaptador de match crea el proceso**. Si querés que match utilice necesariamente `--brains`, habrá que modificar la invocación en ese adaptador. No son cambios internos del motor C++.

## Validación

Compilación local C++17 con GCC; arranque UCI, `isready`, y búsqueda a profundidad 1 cargando `network` desde JSON; además, carga previa mediante argumento posicional. No probado con Visual Studio/MSVC.
