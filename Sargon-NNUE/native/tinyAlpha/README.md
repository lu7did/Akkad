# tinyAlpha C++ 0.1.0 — PUCT + TinyGyal-8, UCI

**Implementación nativa independiente**, sin `lc0.exe`, `lczero-bindings`, bibliotecas de LC0 ni PyTorch. Motor de legalidad C++ reutilizado de picoSargon; MCTS/PUCT e inferencia TinyGyal en C++17. La red **es obligatoriamente externa** y se recibe mediante `--network fichero.pb.gz`.

## Compilación

### Windows 11 (VS2022/VS2026, MSVC, CMake, Ninja)

Necesita **zlib** con headers y biblioteca de enlace. Recomendado mediante vcpkg:

```powershell
vcpkg install zlib:x64-windows
cmake -S . -B build_windows -G Ninja -DCMAKE_BUILD_TYPE=Release `
  -DCMAKE_TOOLCHAIN_FILE="C:\ruta\vcpkg\scripts\buildsystems\vcpkg.cmake"
cmake --build build_windows --config Release
```

Ejecutar desde un PowerShell que tenga cargado el entorno MSVC (`vcvars64.bat`) y Ninja en PATH. La compilación en esta entrega fue realizada y probada en Linux con GCC; **no se incluye un ejecutable Windows precompilado**.

### Linux

```bash
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
```

## Uso UCI

```powershell
.\build_windows\tinyAlpha.exe --network "C:\ruta\tinygyal-8.pb.gz" --simulations 2000 --cpuct 1.5
```

Enviar por stdin: `uci`, `isready`, `ucinewgame`, `position startpos moves e2e4`, `go nodes 2000 movetime 15000`, `stop`, `quit`. Las respuestas UCI se envían a stdout; errores fatales a stderr.

**Limitación importante de la versión 0.1.0:** `go` es sincrónico. `stop` se procesa después de que finalice la búsqueda; para interrupciones usar un límite `movetime`. No se deben interpretar `depth`, `wtime` y `btime` como límites de búsqueda: la configuración operativa es `nodes` y `movetime`.

## Integración Sargon-NNUE

1. Extraer el parche en la raíz del repositorio actual.
2. Ejecutar `python scripts/install_tinyalpha_v06174.py` (hace copias `*.tinyalpha_before` de los archivos modificados). El script comprueba los patrones de integración para no sobreescribir versiones antiguas completas.
3. Compilar el ejecutable nativo y configurar el brain:

```json
{
  "player": "tinyalpha",
  "evaluator": "null",
  "engine-path": "C:\\ruta\\tinyAlpha.exe",
  "network": "C:\\ruta\\tinygyal-8.pb.gz",
  "az-simulations": 2000,
  "az-cpuct": 1.5,
  "tmax": 15000,
  "timeout": 30000
}
```

El player Python lanza el EXE por UCI con `--network` y parámetros MCTS. Mantiene la historia desde `board.root()` más `move_stack`, lo que evita convertir arbitrariamente toda posición en un FEN sin historial. Los registros centrales se comparten entre servicios Sargon-NNUE; el script de integración ajusta `players/__init__.py`, `brains.py`, `factory.py` y `cli_common.py`.

## Validación

Ejecutado en Linux con la red original: `uci`, `isready`, `position startpos`, `go nodes 2`, `go nodes 64`; la segunda búsqueda devolvió `e2e4`. Para comparar Q y política contra el JSON de referencia:

```powershell
python tests/test_native_reference.py "ruta/al/ejecutable" "ruta/tinygyal-8.pb.gz" "ruta/tinygyal_lc0_eigen_reference.json"
```

En ocho casos de referencia con posiciones consistentes se encontraron diferencias de política < 0.00051 y |Q| < 0.000002. **La posición 07 contiene un FEN ajedrecísticamente ilegal**: peón blanco en c5 atacando al rey negro en d6. La referencia creada con python-chess permite capturar ese rey; el motor nativo intencionalmente prohíbe la captura. La prueba excluye esa posición e informa `SKIP INVALID_FEN`.

## Limitaciones y siguientes pruebas

- Este es un **primer motor nativo funcional** y no una conversión línea por línea de las optimizaciones del MCTS Python: no implementa paralelismo, reutilización de árbol entre jugadas, ruido Dirichlet ni caché de inferencias.
- Falta validar rendimiento y juego completo en Windows bajo la configuración real de MATCH/BENCHMARK/RALLY/LISTEN.
- La implementación de inferencia C++ usa convoluciones directas, sin BLAS ni kernels SIMD; prioriza trazabilidad y equivalencia funcional sobre velocidad.
- `stop` diferido y gestión de reloj todavía son limitaciones de protocolo que requieren mejoras antes de considerar el motor apto para torneos con reloj estricto.
- Dado que el código de legalidad proviene del proyecto picoSargon, verificar que el proyecto tenga licencia compatible con su redistribución.
