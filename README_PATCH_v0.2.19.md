# picoAlpha v0.2.19 — perfilado y optimizacion reversible de TinyGyal

**Base requerida:** v0.2.18 (historial compacto v0.2.16, árbol segmentado v0.2.17 y CMake ON en v0.2.18). Parche incremental, no sustituye los otros archivos.

## Cambios
- Medición acumulada por inferencia (`NN_PROFILE`) en microsegundos: bloque convolucional/residual (`conv_res_us`, que tambien incluye SE), rama de politica (`policy_us`), conv de valor (`value_conv_us`), FC grande (`fc1_us`), FC final (`fc2_us`), `total_us`, número de inferencias. Cero telemetría serial dentro del cálculo.
- Vectores de trabajo reutilizados **dentro de cada búsqueda**, con entrada de 7168 floats procesada directamente sin copia auxiliar; los buffers se liberan al finalizar `go`, para no incrementar el heap residual de partida.
- Kernel FP32 con cuatro acumuladores (mismo modelo, puede variar el redondeo IEEE754).
- Kernel INT8 alternativo para la FC1 principal: pesos simétricos cuantizados offline con escalas por fila, activaciones cuantizadas dinámicamente y acumulación INT32; pesos auxiliares en Flash. **INT8 está OFF por defecto** hasta validación de calidad. El modelo FP32 original no se elimina de la Flash: la variante INT8 ocupa Flash adicional.
- Dot-products de convoluciones con `smlad` en Cortex-M cuando el compilador declara `__ARM_FEATURE_DSP`; fuera de esa plataforma vuelve al bucle entero estándar.

## Reversión/configuración (CMake)
Todas las opciones se aplican con `-D...=ON/OFF` en la configuración de CMake. Los valores predeterminados:

```
PA_NN_PROFILE=ON
PA_NN_WORKSPACE=ON
PA_NN_FC_FAST=ON
PA_NN_FC_INT8=OFF
PA_NN_DSP=ON
```

Para volver a cálculos originales en la mayor medida posible: `-DPA_NN_WORKSPACE=OFF -DPA_NN_FC_FAST=OFF -DPA_NN_FC_INT8=OFF -DPA_NN_DSP=OFF`. La instrumentación puede deshabilitarse independientemente con `-DPA_NN_PROFILE=OFF`. `PA_NN_WORKSPACE=OFF` recrea los buffers en cada inferencia, pero la implementación compartida puede usar diferente perfil de memoria que el código de v0.2.18; si hace falta rollback total, restaurar los cuatro archivos previos.

## Interpretación memoria (`Texto pegado(20261023-143629).txt`)
El log suministrado no ejecuta el árbol segmentado: `tree_capacity=1600,2112,2624` y ampliaciones de 512. El árbol segmentado arranca en capacidad 1664 y agrega bloques de 128. Por tanto los `guard_denied=1` del log NO prueban fallas del árbol v0.2.18. En búsquedas 11-14 se observaron ~185KB de `fordblks` y denegaciones preventivas sin `alloc_failed`; esto indica guardarraíl o fragmentación posible, NO prueba bloque contiguo libre.
No se altera MCTS ni su límite de memoria en este parche.

## Validación efectuada
- Compilación nativa Linux de `net.cpp` con FP32 e INT8 opcional, y `mcts.cpp`; `g++ -std=c++17`.
- 3 entradas sintéticas de 7168 elementos: salida FP32 optimizada vs referencia v0.2.16: diferencia máxima entre muestras observadas < 1e-6; INT8 experimental < 2e-7 en esas muestras. NO es evidencia de calidad general: los valores q resultan próximos a saturación.
- No disponible compilación ARM/Pico SDK ni benchmark físico. DSP no compilado en hardware Cortex-M33 en este entorno.

## Próximas pruebas
1. Comprobar la configuración en la salida CMake y que `PA_SEGMENTED_TREE=ON`.
2. Una misma FEN en FP32 original/optimizado/INT8, verificar `NN_PROFILE calls`, `total_us/calls`, `fc1_us/calls`, diferencias de P y Q, resultado UCI válido y heap al terminar.
3. Ejecutar posiciones variadas con la opción INT8 activada y mantener OFF si hay divergencias de jugadas, estabilidad o calidad.
4. Verificar que los `MEM_GROW` de v0.2.18 muestren capacidades 1664,1792,...; si aparece 1600, la configuración/binario todavía es antiguo.

**No confundir:** mejora de tiempo de inferencia no asegura mejora en fuerza ajedrecística. `INT8` altera números P/V y se considera experimental.
