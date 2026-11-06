# picoSargon macOS v0.2.34

Portación nativa Apple Silicon e Intel, compilada desde **los mismos cuatro fuentes C++** de `x86/picoSargon/src/`. No se duplica el motor ni se modifica la arquitectura NNUE.

## Requisitos

macOS, Xcode Command Line Tools (`xcode-select --install`) y CMake >= 3.16 (`brew install cmake` si es necesario).

## Compilar y probar

```bash
cd akkad/picoSargon/macOS/picoSargon
chmod +x build.sh run.sh uci_smoke.sh
./build.sh
./uci_smoke.sh
./run.sh
```

`STEROIDS=ON ./build.sh` habilita optimizaciones experimentales, desactivadas por defecto como en x86.

## Integración Sargon-NNUE

Desde `akkad/Sargon-NNUE`, el perfil `tinySargon` de `etc/brains/brains.json` resuelve `engine-path` y `network` con clave `macos`. Las rutas relativas suponen que el directorio de trabajo es `akkad/Sargon-NNUE`, al igual que los comandos documentados. Otros perfiles no fueron alterados.

La identificación UCI usa `sysctlbyname` para obtener versión de macOS y RAM. Se compila con `-std=c++17`; el modelo Grumpy externo es el binario existente, no se inserta en el ejecutable.

**Validación pendiente:** compilar y ejecutar en macOS real (no disponible en este entorno Linux). No se garantiza aún integración funcional de benchmark/listen/match/rally fuera del perfil `tinySargon`.
