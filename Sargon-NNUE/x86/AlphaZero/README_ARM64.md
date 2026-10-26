# AlphaZero v0.1.4 — Apple Silicon / Raspberry Pi 4 Debian ARM64

Este parche incremental se extrae desde `Akkad/`, y modifica exclusivamente los scripts de `sargon-NNUE/x86/AlphaZero/`. No modifica C++ ni Windows. `x86` es el nombre histórico de la carpeta, **no** una restricción de la arquitectura compilada.

## macOS Apple Silicon (arm64)
Instalar herramientas de Xcode (`xcode-select --install`) y Homebrew arm64 (usualmente `/opt/homebrew`):

```bash
brew install cmake meson ninja pkg-config git protobuf eigen
cd sargon-NNUE/x86/AlphaZero
chmod +x build_*.sh
./build_macos.sh
```

No correr mediante Rosetta. Utiliza BLAS/Accelerate y el backend `eigen` de inferencia LC0 C++ de forma predeterminada. El ejecutable se genera en `build/AlphaZero` (Mach-O arm64).

## Raspberry Pi 4 — Debian 13.2 ARM64
Confirmar `uname -m` = `aarch64` y `getconf LONG_BIT` = `64`. En Debian ARM32 no corre este flujo. La compilación local puede requerir varios GB de espacio de almacenamiento y swap si la placa dispone de poca RAM.

```bash
sudo apt update
sudo apt install -y build-essential cmake git meson ninja-build pkg-config python3 \
  libopenblas-dev libeigen3-dev zlib1g-dev libprotobuf-dev protobuf-compiler
cd sargon-NNUE/x86/AlphaZero
chmod +x build_*.sh
./build_raspberrypi.sh
```

`BUILD_JOBS=2` es el default de Raspberry Pi para limitar presión de memoria. Con 2GB o menos probar `BUILD_JOBS=1 ./build_raspberrypi.sh`; con 8GB se puede aumentar prudentemente. La inferencia corre en CPU OpenBLAS (`--backend eigen`). No se usa `lc0.exe` ni bindings Python LC0, aunque se compilan componentes C++ de LC0.

## Red neuronal y prueba

Ejecutable: `build/AlphaZero`. Probar usando una red LC0 `.pb.gz` compatible:

```bash
./build/AlphaZero --weights /ruta/modelo.pb.gz --backend eigen --help
# Prueba básica de handshake UCI:
printf 'uci\nisready\nquit\n' | ./build/AlphaZero --weights /ruta/modelo.pb.gz --backend eigen
file build/AlphaZero
```

Para verificar `bestmove` utilizar cliente UCI interactivo y esperar respuesta antes de enviar `quit`. El proceso es un ejecutable independiente del sistema Windows: transferir **los fuentes**, nunca copiar `AlphaZero.exe`.

## Reproducibilidad y limitaciones

La versión de LC0 predeterminada es `v0.32.1` para evitar seguir el movimiento de `master`. Puede establecerse `LC0_REF` antes de la primera descarga o `LC0_SOURCE` para clonar una versión local. Si la versión de LC0 ya está descargada en `build/lc0-src`, se reutiliza; para cambiarla hay que eliminar esa carpeta deliberadamente (no toca otros datos).

La preparación sustituye `src/main.cc` y `src/config.h` **solo dentro de la copia de trabajo** `build/lc0-src`. El original `src/` de AlphaZero queda intacto. La configuración Meson se rehace cada ejecución. La compatibilidad de las API LC0, los switches Meson y las redes debe verificarse físicamente en ambos equipos. La versión LC0 seleccionada puede diferir de la que utilizó previamente Windows. No se ha probado compilación nativa ni funcionamiento de inferencia en macOS/Raspberry Pi en este entorno.
