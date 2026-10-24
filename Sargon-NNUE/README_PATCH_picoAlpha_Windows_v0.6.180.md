# picoAlpha Windows C++ v0.6.180 — parche incremental

## Base y alcance
Se aplica a `Sargon-NNUE(6).zip`, exclusivamente en `Sargon-NNUE/native/picoAlpha/`. No modifica `native/picoSargon`, Python, datos ni documentación de la base.

## Auditoría Pico → Windows
- **Transferido**: cuantización por tensor INT8 existente, uso de scratch `thread_local` reciclado para parches de convolución, cálculo de un parche por casilla y reutilización de ese parche en todos los filtros, producto entero de cuatro acumuladores, agrupación de nodos MCTS en `std::deque` con punteros estables (sin `new` individual por nodo), reserva explícita de capacidad de hijos antes de expansión.
- **Ya presente en Windows**: carga LINEAR16, precomputación de pesos INT8, softmax legal, PUCT, `push/pop`, convolución INT8; no se reimplementan.
- **No transferido**: instrucciones ARM SMLAD, buffers SRAM globales de Pico, red FC1 específica de Pico, caché y reutilización de subárboles con comprobación de historial. Windows usa contenedores dinámicos y una arquitectura de MCTS diferente; adaptarlos a ciegas alteraría semántica o privacidad del historial.

## Diferencia de memoria
Antes: conv INT8 crea parches `64 * K` bytes, más activaciones; con K=1008 utiliza 64.512 bytes de parches. Ahora utiliza `K` bytes (1008), reciclados durante todas las convoluciones del hilo. FP32: de `64*K*sizeof(float)` a `K*sizeof(float)`. Los vectores de salida por capa siguen asignándose: NO es una implementación sin heap.
Los hijos MCTS antes estaban en objetos `unique_ptr<Node>` individuales; ahora se ubican en bloques amortizados de `std::deque<Node>`, preservando estabilidad de punteros durante la búsqueda.

## Validación
- Compilación Linux CMake / GCC C++17 de `picoAlpha` INT8 y `picoAlpha32` FP32, correcta.
- Mismo TinyGyal-8 del ZIP proporcionado, misma entrada UCI (`uci`, `isready`, `position startpos`, `eval`, `go nodes 3`). Las líneas `info` y `bestmove` son idénticas a la base para ambos modos en esa prueba.
- No se realizó compilación con MSVC en Windows ni benchmark confiable de velocidad en Windows; debe medirse antes de afirmar aceleración.

## Aplicación
Sobrescribir los dos archivos del ZIP en `Sargon-NNUE/native/picoAlpha/src/`, preservando el resto del proyecto. Configurar con CMake como de costumbre. Este archivo contiene solamente el parche incremental.
