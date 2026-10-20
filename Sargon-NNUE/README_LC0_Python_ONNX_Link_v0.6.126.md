# LC0 GPU Python ONNX Link — v0.6.126

## Diagnóstico
En LC0 `dab9898`, el objetivo `lc0.exe` incorpora `objects: backend_objects`, pero la extensión `python.extension_module('backends', ...)` no. El backend ONNX se compila en una biblioteca estática separada y no queda registrado dentro del módulo Python. Los bindings GPU compilados con v0.6.125, incluso si detectan ONNX Runtime, pueden mostrar únicamente `eigen` y los backends auxiliares.

El nombre `onnx-dml` solo se registra si, adicionalmente, `USE_DML` se define al compilar `src/neural/backends/onnx/network_onnx.cc`.

## Secuencia
Desde la raíz de Sargon-NNUE:

```powershell
.\scripts\sargon_lc0_gpu_rebuild_v0.6.126.ps1
.\scripts\sargon_lc0_gpu_verify_v0.6.126.ps1
```

El primero modifica **solo la copia local del código fuente de LC0** dentro de `%TEMP%`, con una inserción idempotente en `meson.build`, y reconstruye un nuevo wheel dentro de `%TEMP%\sargon-lc0-onnx-dml\dist-v126`. Exige que Meson declare `onnx_backend` y que `onnx_conf.h` contenga `USE_DML`.

El segundo instala el wheel **solo** en `%TEMP%\lc0-gpu-test`, añade temporalmente los directorios DLL y comprueba `Backend.available_backends()`. **No modifica `ufasta`, Sargon-NNUE ni los pesos**.

### Cambio de Meson

En el objetivo Python agregar:

```meson
    cpp_args: ['-fvisibility=hidden'],
    objects: backend_objects,
    subdir: 'lczero',
```

Se conserva el parámetro `objects: backend_objects` que ya existía en `executable('lc0', ...)`.

## Estado de la validación
Revisión estática de Meson y código fuente de la revisión `dab9898`: realizada. El script comprueba condiciones necesarias después de la compilación. **No está probado en Windows en esta entrega.** Es posible que aparezcan errores de compilación, dependencias, empaquetado, carga de DLL o ejecución del modelo. La aparición de `onnx-dml` en la lista confirma registro, no rendimiento ni uso efectivo de Intel Arc; para eso falta una inferencia real y mediciones CPU/GPU.
