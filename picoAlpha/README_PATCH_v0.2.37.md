# picoAlpha v0.2.37 — prueba experimental 1×8

Aplicar estos archivos sobre la línea de base picoAlpha recibida, conservando el resto.

La compilación predeterminada usa `PICOALPHA_NET=1x8`; para volver al original: `cmake -S . -B build-pico2-w -DPICOALPHA_NET=2x16`.

## Alcance
- Evaluador 1×8 independiente con pesos INT8 en flash, BN fusionado, activaciones FP32 y cabezas P/V.
- Reproduce los **13 planos** de distiller.py a partir de la codificación actual, sin modificar net.cpp.
- Reproduce literalmente `((from*64+to) % 1968)` para la política experimental. **Los índices son ambiguos y las probabilidades NO son la P de LC0**; esto afecta la calidad de ajedrez.
- 2×16 original inalterado; MCTS/UCI inalterados.
- No se incluye el checkpoint PT, solo los parámetros embebidos.

## Precaución
Este parche está diseñado para pruebas funcionales y medición de velocidad, no como red validada ajedrecísticamente. No se ha compilado sobre SDK de Raspberry Pico en este entorno. Cualquier error de compilación o de operación física debe considerarse pendiente de validación.

## Pruebas iniciales
1. Configurar CMake sobre el directorio build existente con `-DPICOALPHA_NET=1x8`.
2. Compilar y verificar el tamaño de UF2 y uso de SRAM.
3. Probar protocolo `uci`, `isready`, `position startpos`, `go movetime 16000`.
4. Comparar conteo de inferencias y tiempo NN con 2×16 usando la misma posición.
