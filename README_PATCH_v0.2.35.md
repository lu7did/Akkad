# picoAlpha v0.2.35 — Optimización TinyGyal y continuidad MCTS

Parche **incremental** sobre v0.2.34. No incluye datos, pesos originales adicionales ni una línea de base completa. Núcleo único; 8576 nodos estáticos, 20 bytes por nodo, sin modificación de PUCT.

## Intervenciones

1. **DSP INT8:** se mantiene el ensamblador ARM `SMLAD` para productos de pares INT16 empaquetados, y se usa en cuatro filas FC1, por bloques, mediante `dot_int8`. En compilación no ARM se usa el producto escalar equivalente. La ruta SIMD ya existía en v0.2.34; esta versión cambia su integración con FC1 y su patrón de memoria, no inventa una nueva instrucción.
2. **Pesos FC1 en Flash:** el mismo conjunto de 262144 INT8 se permuta **una sola vez** en el encabezado generado. Grupos de cuatro filas con subbloques de 32 bytes, recorridos secuencialmente por `fc_int8_into`. **No** duplica ni cuantiza otra vez la matriz. **Importante:** el archivo de pesos generado es necesario en el parche por el cambio de disposición.
3. **Cuantización sin cálculo repetido:** `conv_into` reutiliza el buffer cuantizado y el factor de escala de las activaciones `w.b` en las dos ramas (política `p1_` y valor `vconv_`). Se agrega `Workspace::quant_b` (2048 B). Los pasos de redondeo siguen siendo los mismos. No elimina las cuantizaciones de activaciones que efectivamente cambiaron.
4. **Primer filtro disperso/denso:** para más de 700 elementos activos de 1008 posibles, ruta densa INT8; en otro caso se conserva ruta dispersa. Ambas acumulan exactamente productos enteros. No requiere heap.
5. **Caché de inferencias:** 8 entradas de capacidad fija con claves dobles de 64 bits que cubren los 112 planos `float` y la secuencia ordenada de índices de política solicitada. Se devuelve el mismo valor y los mismos logits; en caché hit no se invoca TinyGyal. Se excluye la evaluación de política completa (4672 logits). La caché es temporal en SRAM y no sobrevive reinicios.
6. **Reutilización de MCTS:** se conserva el árbol entre búsquedas **solo** si el nuevo historial compacto extiende exactamente dos posiciones el anterior, y el tablero coincide con una respuesta del oponente en el subárbol de la jugada elegida. Preserva la perspectiva y estadísticas originales. Sin copiar la arena; si quedan menos de 4096 nodos libres no reutiliza y empieza de cero. No compacta ni recicla los nodos inaccesibles dentro de una búsqueda reutilizada: es una limitación deliberada para evitar sobrescribir índices de hijos.

## Compilación reversible

- `PA_NN_CACHE=ON|OFF` (ON por defecto)
- `PA_MCTS_REUSE=ON|OFF` (ON por defecto)
- `PA_NN_DSP=ON|OFF` (ON por defecto)
- `PA_DUAL_CORE_NN=OFF` forzado, como v0.2.34.

`PA_NN_DSP=OFF` desactiva SMLAD; no restaura la disposición antigua de FC1: el kernel nuevo funciona también sin DSP.

## Verificación realmente realizada

- Compilación C++17 nativa de `board.cpp`, `net.cpp`, `mcts.cpp`.
- Seis posiciones: valor neuronal y checksum ponderado de logits legales idénticos entre v0.2.34 y v0.2.35.
- Caché: 1 acierto y 1 fallo tras evaluar dos veces la misma entrada, mismo valor.
- Reutilización: búsqueda de 128 simulaciones y continuación del rival; siguiente búsqueda reutilizó el árbol anterior (3721 nodos), no lo reinició.
- Prueba nativa de tres búsquedas y 100 movimientos: cero llamadas nuevas a `operator new` dentro del intervalo auditado.

**No se realizó compilación ARM ni prueba física de rendimiento.** No hay evidencia aún de mejora de tiempo en RP2350 ni garantía de aumento de simulaciones. La reutilización puede consumir arena antes que el inicio fresco, motivo de la reserva conservadora de 4096 nodos y la desactivación por CMake. La caché usa doble hash de 64 bits, por lo que existe una probabilidad teórica (extremadamente baja) de colisión; no es una comparación bit a bit de toda la entrada. Ante equivalencia estricta sin esa salvedad, compilar con `PA_NN_CACHE=OFF`.

## Nueva telemetría bajo PA_TELEM_MCTS

`MCTS REUSE prior_nodes=... root=... cache_hits=... cache_misses=...`

Todos los identificadores UCI y líneas obligatorias de v0.2.34 se mantienen.
