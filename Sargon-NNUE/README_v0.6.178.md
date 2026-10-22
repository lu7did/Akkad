# Sargon-NNUE v0.6.178 — tinyAlpha INT8/INT32

Aplicar sobre v0.6.177. **Cambios aislados al motor C++**: `net.hpp`, `net.cpp`, `main.cpp`, `CMakeLists.txt` y script de compilación Windows. No modifica tablero Mailbox-120, búsqueda MCTS ni registros Python.

## Implementación

- Carga la red externa original `tinygyal-8.pb.gz`, sin LC0 ni PyTorch.
- Convierte los pesos convolucionales a INT8 simétrico con escala **por canal de salida** al inicializar el motor.
- Cuantiza dinámicamente cada tensor de entrada a INT8 (escala simétrica por tensor); hace producto INT8×INT8 con **acumulador `int32_t`**; reescala y suma sesgo en FP32.
- ReLU residual/SE, conexión skip, cabezales densos, softmax y tanh permanecen FP32. Esta es una implementación mixta INT8/FP32: no se afirma cuantización integral de toda la red.
- Modos `--precision fp32|int8`. `tinyAlpha.exe` usa FP32 por defecto; `tinyAlphaInt8.exe` usa INT8 por defecto. Ambos admiten `--precision` para pruebas directas.
- No se cambia `Board`, ni Mailbox-120, ni la legalidad, ni UCI.

## Compilar Windows (Visual Studio 2026 + vcpkg/ZLIB instalados)

```powershell
cd C:\Users\pedro\github\Bobby\Akkad\Sargon-NNUE\native\tinyAlpha
.\build_windows.ps1 -VcpkgRoot 'C:\Users\pedro\vcpkg'
```

En `build_windows\Release` quedarán `tinyAlpha.exe` (FP32) y `tinyAlphaInt8.exe` (INT8), si CMake y MSVC completan ambas compilaciones. Alternativamente: `cmake --build build_windows --config Release`.

## BENCHMARK de Sargon-NNUE

Mantener `player=tinyalpha`, `evaluator=null`, misma `network`, `az-simulations`, `az-cpuct`, `tmax` y posiciones. Definir dos brains idénticos salvo:

```
"engine-path": "C:\\...\\tinyAlpha.exe"       // FP32
"engine-path": "C:\\...\\tinyAlphaInt8.exe"   // INT8
```

Ambos usan el adaptador Python `TinyAlphaUCIPlayer` de la v0.6.176 sin cambios. No usar simultáneamente el mismo executable para los dos brains. Comprobar que se recompilaron **ambos** EXE tras extraer el parche.

## Validación efectuada aquí (Linux GCC Release)

- Compilación de ambos ejecutables y comandos UCI `position startpos`, `go nodes 20/100`, `bestmove e2e4`.
- 100 simulaciones, misma máquina y red, tiempo de proceso total orientativo: FP32 0.21–0.23 s, INT8 0.068–0.070 s. Es una medición local que **no predice** el rendimiento en Windows; incluye arranque y carga.
- Frente a LC0/Eigen, con ocho casos ajedrecísticamente válidos de las nueve referencias: FP32 máximo error de política ~0.000504; INT8 máximo error de política ~0.0995 y máximo error de Q ~0.0385. La nueva ruta **no es equivalente numéricamente** y puede cambiar jugadas, especialmente con 2.000 simulaciones.
- La referencia n.º 7 es un FEN ilegal; queda excluida del conjunto nativo como en las pruebas previas.
- No fue compilada ni medida una versión `.exe` Windows en este entorno Linux: el parche incluye fuentes y compilación Windows, no un EXE Windows precompilado.

## Próximas decisiones basadas en datos

Comparar tiempos/nodo, decisiones y resultados de partida; si el cambio neuronal afecta demasiado la calidad, calibrar con posiciones representativas, probar cuantización de activaciones por canal y estudiar kernel SIMD. Evitar prometer paridad con LC0 tras cuantizar.
