# picoSargon v0.2.22 — Identificación UCI

En Linux/Debian, el comando `uci` anuncia `id name picoSargon C++ v0.2.22 (debian <PRETTY_NAME> / <RAM total> GiB RAM)`. PRETTY_NAME proviene de `/etc/os-release`; MemTotal de `/proc/meminfo`. La memoria mostrada es RAM física total detectada por el kernel, no RAM libre ni memoria disponible para procesos.

En Windows se anuncia `id name picoSargon C++ v0.2.22 (Windows)` sin tocar las dependencias Win32.

El literal `id name` es parte del protocolo UCI: no se debe anteponer `uci` a la respuesta. La versión se define mediante `PROJECT_VERSION` de CMake.

Aplicar en la raíz de Akkad, reconstruir con `bash picoSargon/tools/bash/build.sh`, ejecutar con `bash picoSargon/tools/bash/run.sh` y enviar `uci`.
