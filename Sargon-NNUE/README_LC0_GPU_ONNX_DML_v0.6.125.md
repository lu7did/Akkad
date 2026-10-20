# Sargon-NNUE — Experimento ONNX-DML (herramientas v0.6.125)

## Alcance y seguridad

La versión **no modifica código Python de Sargon-NNUE, no instala ningún wheel** y no sustituye los bindings LC0/Eigen que ya funcionan. Proporciona:

- `scripts/sargon_lc0_gpu_build.ps1`: descarga **Microsoft.ML.OnnxRuntime.DirectML 1.24.4** y **Microsoft.AI.DirectML 1.15.4** de NuGet; verifica que existan bibliotecas y encabezados; genera un wheel de bindings LC0 con backend ONNX-DML **sin instalarlo**.
- `scripts/sargon_lc0_gpu_benchmark.py`: compara el tiempo de inferencia sobre las mismas posiciones entre `eigen` y `onnx-dml`, una vez esté instalado y operativo el backend GPU.

La compilación se realiza sobre el checkout que ya fue reparado manualmente en Windows (`%TEMP%\lc0-bindings-dab9898`), con las correcciones de `python_chess.cc` y `pyproject.toml`. El script se detiene si no están.

## Fase 1 — Compilar wheel sin instalar

En PowerShell con `ufasta` activo, desde la raíz del proyecto:

```powershell
.\scripts\sargon_lc0_gpu_build.ps1
```

Al terminar, el manifiesto `%TEMP%\sargon-lc0-onnx-dml\GPU_BUILD_PATHS.txt` indica el wheel y las DLL nativas. Si hay errores, conservar el registro. **No instalar ni copiar todavía los archivos sin inspeccionar el manifiesto.**

Para preparar ONNX-DML no basta `pip install onnxruntime-directml`, porque LC0 se construye mediante C++ y requiere `onnxruntime.lib`, `onnxruntime_cxx_api.h`, `dml_provider_factory.h` y las DLL correctas. Estas rutas se obtienen de los paquetes NuGet.

## Fase 2 — Validar en entorno Python con GPU

*Pendiente una vez compilado el wheel*: hacer una copia de seguridad del `.pyd` que funciona, instalar el wheel en un entorno de prueba o con un rollback preparado, hacer accesibles las DLL de ONNX Runtime y DirectML y comprobar:

```python
from lczero.backends import Backend
print(Backend.available_backends())
```

Exigir la presencia de `onnx-dml`; no asumirla. Luego ejecutar:

```powershell
.\scripts\sargon_lc0_probe.ps1 --lc0-weights "data\lc0\model.pb.gz" --lc0-backend onnx-dml --lc0-backend-options "gpu=0"
```

Si pasa, comparar:

```powershell
& "C:\Users\pedro\ufasta\Scripts\python.exe" .\scripts\sargon_lc0_gpu_benchmark.py `
  --lc0-weights "data\lc0\model.pb.gz" --gpu-options "gpu=0" --positions 25 `
  --output "data\test\lc0_cpu_gpu_benchmark.json"
```

Si `data\test` no existe, crearlo previamente.

## Consideraciones

- ONNX-DML sobre GPU Intel Arc depende de la disponibilidad de DirectML y un driver compatible.
- El mismo modelo, la misma lista de posiciones y las mismas simulaciones MCTS deben utilizarse al comparar tiempos de juego.
- La mejora no está garantizada: MCTS evalúa a menudo lotes de tamaño 1 y el coste de GPU puede superar a Eigen con redes pequeñas. Si el backend funciona, comparar `gpu=0` con `gpu=0,batch=1,steps=1`; esas opciones existen en el backend ONNX de LC0, pero su mejora de latencia no está demostrada.
- Para el backend `dx12` de LC0, las redes recientes de política con atención/Transformer no están soportadas. Por eso priorizamos ONNX-DML.
- No modificar `--cache`: la persistencia de estadísticas MCTS sigue explícitamente pospuesta.
- Los scripts de este paquete no han podido ejecutarse en Windows en el entorno de creación. Los paquetes descargados se verifican por su estructura, no se da por validada la compilación GPU.

Fuentes:
- https://github.com/LeelaChessZero/lc0/blob/dab9898f33f63fa58c567daf0b33994d45d12135/meson.build
- https://www.nuget.org/packages/Microsoft.ML.OnnxRuntime.DirectML/1.24.4
- https://www.nuget.org/packages/Microsoft.AI.DirectML/1.15.4
- https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html
