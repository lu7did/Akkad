# Sargon-NNUE v0.6.177 — optimización experimental de convoluciones C++

Parche incremental sobre v0.6.176. Reemplaza únicamente `native/tinyAlpha/src/net.cpp`.

Optimización: convolución de TinyGyal con matriz im2col y productos escalares contiguos; elimina condiciones de contorno y cálculos de índices del bucle interno. Sin llamadas LC0 ni PyTorch.

Pruebas realizadas en Linux/GCC Release, con la red TinyGyal original:
- 8/8 posiciones de referencia válidas, con diferencia máxima de política < 0.00051 y Q < 0.000002. La novena entrada se omite por ser un FEN ilegal, como en el test nativo anterior.
- 200 simulaciones UCI desde startpos: antes 0.581 s, después 0.489 s (~16 % menor tiempo en este entorno). No implica el mismo porcentaje en MSVC/Windows.
- En ambas versiones: `bestmove e2e4` en esta prueba.

Para probar en Windows:
1. Extraer el ZIP en la raíz de Sargon-NNUE, sobrescribiendo solo `net.cpp`.
2. `cd native\\tinyAlpha`
3. `cmake --build build_windows --config Release`
4. Repetir BENCHMARK con los mismos parámetros y reloj, y comparar tiempos.

El benchmark del usuario indica 3.5 ms/nodo en tinyAlpha vs 1.7 ms/nodo en LC0/Eigen. Este parche NO certifica paridad de rendimiento con Eigen. La diferencia más profunda es que LC0/Eigen utiliza kernels muy optimizados; se necesita seguir perfilando la inferencia y MCTS para cerrarla.
