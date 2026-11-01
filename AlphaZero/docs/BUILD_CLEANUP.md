# AlphaZero - construcción desde la nueva estructura Akkad

## Windows (PowerShell)

Desde `Akkad/AlphaZero`, ejecutar `./build.ps1` sin argumentos. El backend
predeterminado es `onnx`, y el script detecta e inicializa automáticamente
MSVC mediante `vswhere` y `vcvars64.bat` si no está disponible en la sesión.
Compila Abseil local dentro de `AlphaZero/build/deps`; no copia bibliotecas de
Anaconda. `-Backend eigen` y `-RebuildAbseil` siguen siendo opciones explícitas.

## Debian ARM64 / Raspberry Pi

Desde `Akkad/AlphaZero`, ejecutar `./build.sh --OS Debian` o `./build.sh --OS RBPi`.
El wrapper legado `./tools/bash/build.sh` ahora delega al constructor
unificado y, sin argumentos, equivale a `./build.sh --OS RBPi`.

Rutas relativas a `AlphaZero` (no al directorio desde el que se invoca):

- `build/lc0-src` — fuentes LC0
- `build/lc0-build-debian-arm64` — build Meson de Debian / RBPi
- `build/AlphaZero` — ejecutable Linux

El backend Debian es `eigen`/OpenBLAS; no necesita `abseil_dll.dll`, que es
una dependencia binaria específica de Windows. En RBPi se mantiene la opción
`SKIP_APT=1` para omitir instalación de paquetes. Si el árbol Meson antiguo
fue movido y falla su caché, usar `CLEAN_BUILD=1 ./build.sh --OS RBPi`
para recrear solamente la configuración Meson correspondiente.

Los scripts de pruebas y ejecución leen `build/AlphaZero`. No se cambió el
núcleo C++ ni la configuración de redes.
