# AlphaZero en Debian Raspberry Pi ARM64 (parche incremental)

Esta variante recompila **el mismo `src/akkad_alphazero_main.cc`** que Windows con el backend CPU `eigen`/OpenBLAS de LC0. DirectML es exclusivo de Windows y no está habilitado en Debian. LC0 se fija inicialmente a la etiqueta v0.32.1. No usa `lc0.exe` como motor externo: enlaza sus bibliotecas C++ directamente.

## Preparación y compilación

Desde la raíz de Akkad, tras extraer el parche:

```bash
cd AlphaZero
bash tools/bash/build.sh
```

El instalador solicita sudo para instalar dependencias por `apt-get`; necesita conexión a Internet para descargar las fuentes de LC0 y dependencias Meson. Para administrar paquetes por separado `SKIP_APT=1 bash tools/bash/build.sh`. En placas con poca memoria usar `BUILD_JOBS=1`. El ejecutable queda en `AlphaZero/build/AlphaZero`. En esta implementación se requiere Debian ARM64 (`uname -m` = `aarch64`).

## Verificación y operación

```bash
bash tools/bash/diagnostics.sh
bash tools/bash/uci_smoke.sh /ruta/red-lc0.pb.gz
bash tools/bash/run.sh /ruta/red-lc0.pb.gz
```

El `uci_smoke.sh` envía `uci`, `isready`, `position startpos` y `go nodes 30`, espera efectivamente `bestmove` y después cierra el proceso. Una red `.pb.gz` debe copiarse o instalarse por separado (no se incluye en este parche). El backend `eigen` es CPU, puede ser más lento que el DirectML de Windows. `OPENBLAS_NUM_THREADS=1` evita sobresuscripción inicial.

## Integración Sargon-NNUE

En `brains.json`, conservar la ruta Windows existente y configurar el campo Debian del brain `emma` para apuntar al ejecutable ARM y la red local correspondiente. El backend de `emma` debe elegirse también por plataforma: `onnx-dml` en Windows frente a `eigen` en Debian. Si el resolvedor de `brains.json` **no admite mapas de plataforma para `lc0-backend`**, no reemplazar el campo común: utilizar un identificador de brain Debian separado (p. ej. `emmaPi`) hasta incorporar soporte de variantes de configuración para el backend.

## Alcance

Parche no probado en hardware ARM en este entorno. Los pasos de instalación y compilación deben verificarse en la Raspberry Pi. En particular, la API y opciones Meson de LC0 pueden requerir ajustes según las fuentes descargadas. No se modifica el motor C++ compartido ni `build.ps1` de Windows.
