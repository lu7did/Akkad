# picoAlpha v0.2.21 – optimización de evaluación TinyGyal

Parche incremental sobre v0.2.20. Sólo sobrescribir archivos incluidos; conservar todo lo demás.

## Implementación
- Primera convolución: construir lista de entradas INT8 no nulas por casilla y acumular sólo productos no cero, sin modificar pesos ni escalas.
- Política legal: se computan únicamente los logits de las jugadas legales; no se generan 4672 logits intermedios en MCTS.
- FC1: variante INT8 de 262144 pesos, cuantización simétrica por fila, activación INT8 e acumulación INT32 con DSP donde está disponible. ON por defecto.
- Sin INT4, sin segundo núcleo, sin inferencia incremental.

## Alcance numérico
- Las convoluciones continúan usando activaciones intermedias FP32, escalas FP32 y capas SE FP32: NO es inferencia íntegramente INT8. El producto de convolución y la FC1 son INT8/INT32. Convertir SE a INT8 demandaría otro formato y otro algoritmo no cubiertos aquí.
- La cuantización de FC1 cambia los valores resultantes; requiere medir diferencias de política y valor en posiciones reales.

## Archivos
- src/net.cpp, include/net.hpp, src/mcts.cpp, src/pico_main.cpp, CMakeLists.txt y include/generated_tinygyal_fc_int8.hpp.

## Compilación
Se conservan `PA_SEGMENTED_TREE` y `PA_LEGACY_MCTS_TREE` v0.2.20; la configuración segmentada sigue siendo obligatoria por defecto. La identificación de versión es v0.2.21.

## Limitaciones de validación
Compilación nativa y pruebas de comparación efectuadas aquí. Sin compilación RP2350/UF2 ni prueba física. No asumir velocidad mayor sin mediciones.
