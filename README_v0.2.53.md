# picoAlpha v0.2.53 — FC1 picoGyal

Parche incremental sobre v0.2.52. Modifica exclusivamente `src/net_1x8.cpp`.

Auditoría: TinyGyal y picoGyal comparten el FC1 cuantizado de 2048 entradas, 128 salidas. El código previo llamaba cuatro veces a `dot_int8` en cada tesela de 32 entradas. Ahora acumula las cuatro salidas en una misma pasada de la tesela, reusando los valores de entrada. En RP2350/M33, usa SMLAD para cuatro acumuladores, preservando sumas INT32 exactas. No altera pesos, escalas, cuantización ni dimensiones. TinyGyal (`net.cpp`) no se modifica.

Validación: equivalencia exacta de acumuladores INT32 mediante prueba aleatoria de escritorio. El rendimiento y la compilación en Pico 2 W deben medirse físicamente; la mejora no se puede garantizar sin benchmarking ARM. Comparar `NN_PROFILE fc1` y `sims` en las mismas posiciones y presupuesto temporal antes/después.

Aplicar conservando `include/config.h`, `include/picoGyal.hpp`, `include/picoGyal_fc_int8.hpp`.
