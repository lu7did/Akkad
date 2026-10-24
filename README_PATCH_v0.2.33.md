# picoAlpha v0.2.33 — parche incremental sobre v0.2.32

Cambios: `src/net.cpp`, `src/mcts.cpp`, `src/pico_main.cpp`, `CMakeLists.txt`.

1. Producto punto INT8 de convoluciones: acumulación en cuatro carriles enteros; reutiliza el parche cuantizado por casilla para todos los filtros (ya presente, preservado). No se altera el redondeo de la cuantización ni los pesos.
2. FC1 INT8: procesa cuatro neuronas de salida por bloque reutilizando los bytes cuantizados de entrada. No se habilita el núcleo 1.
3. `Node`: 28 -> 20 bytes (`visits`/`first` uint16_t, `count` uint8_t, banderas uint8_t), capacidad fija 6144 -> 8576, SRAM de nodos pasa de 172032 a 171520 bytes. Límite: 128 simulaciones por búsqueda, índices < 65536, hijos <= 255.
4. Terminales conocidos: las visitas posteriores de un nodo terminal usan el resultado almacenado, evitando nuevas comprobaciones de jaque. No cambia PUCT.
5. Draw: la detección se realiza al expandir el nodo, no de nuevo en cada revisita; backup de nodos terminales sigue aumentando visitas con valor -1 o 0 y sin inferencia adicional.
6. Identidad UCI conservada `id author Dr. Pedro E. Colla`; versionado v0.2.33 uniforme. Un núcleo por defecto.

Pruebas: sintaxis C++17 para net/mcts/board; prueba nativa de 3 búsquedas y 100 movimientos sin llamadas adicionales a new; comparación de la evaluación neuronal posición inicial con implementación anterior idéntica: Q=0.113683470, sum=-92.330073602, first=-0.348489583. No se compiló firmware ARM ni se ejecutó en RP2350. Los cambios de rendimiento ARM son hipótesis medibles, no velocidad garantizada. La transformación de terminales necesita regresión prolongada en posiciones de tablas y mate.

Aplicación: descomprimir sobre v0.2.32, reconstruir desde CMake, asegurándose que `PA_STATIC_TREE_NODES=8576` (forzado) y `PA_DUAL_CORE_NN=OFF`. Contenido de ZIP: solo cuatro archivos fuente/configuración y este README; no altera datos/redes.
