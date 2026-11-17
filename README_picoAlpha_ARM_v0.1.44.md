# picoAlpha ARM — parche incremental v0.1.44

## Alcance
Corrección puntual de incompatibilidades de tipos en `std::max` para el toolchain ARM GCC 15.2.1 de Pico 2W. Aplicar extrayendo el ZIP en la raíz de `akkad`, sobre v0.1.43.

### Archivos modificados
- `picoAlpha/ARM/src/mcts_arm.cpp`, línea 48: sustituye `std::max(1u,pool_[node].visits)` por `std::max(uint32_t{1},pool_[node].visits)`.
- `picoAlpha/ARM/src/search_coordinator.cpp`, cálculo de profundidad máxima: sustituye `0u` por `uint32_t{0}`.

No se modifica el comportamiento de MCTS/PUCT ni la red NNUE. Los cambios fuerzan coincidencia de tipos exacta para compiladores que definen `uint32_t` como `unsigned long`.

## Validación efectuada
- `tests/run_host.sh`: PASS.
- `tests/run_host_multicore.sh`: PASS (10 iteraciones, 120 simulaciones cada una).
- `tests/run_host_syntax.sh`: PASS (advertencia deprecación `mallinfo()`).

**No se ejecutó compilación con Pico SDK ni pruebas en hardware RP2350.**

## Compilación en Windows
Desde `akkad/picoAlpha/ARM`:

```powershell
.\build.ps1
```

Si CMake mantiene una compilación anterior, reconstruir desde cero el directorio `build` que utilice el script.
