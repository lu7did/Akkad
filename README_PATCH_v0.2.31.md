# picoAlpha v0.2.31 — Primera convolución: validaciones y diagnóstico granular

**Aplicar únicamente sobre v0.2.30.** Es un parche incremental. Mantiene PA_DUAL_CORE_NN=OFF, la arena estática de 6144 nodos, los buffers fijos y las 128 simulaciones.

Se analiza el reinicio observado en v0.2.28 con `WD_LAST search=9 phase=17 step=0`. En esa versión el marcador 17 se emitía justo antes de entrar en la primera convolución, pero no identifica la instrucción que falló. v0.2.30 ya había eliminado asignaciones de la primera convolución.

Cambios:
- Validación en la entrada de `conv_sparse_first()` de geometría de TinyGyal (112 canales, 16 filtros, kernel 3x3), 7168 activaciones, límites de los buffers y presencia de pesos/escalas/sesgos. Un defecto devuelve una excepción controlada.
- Comprobación de valores finitos de entrada, capacidad del buffer disperso y desplazamientos al calcular las activaciones de la primera convolución.
- Marcadores persistentes adicionales: 21 preflight; 22 cuantización (step hasta 7168); 23 cuantización terminada; 24 casillas procesadas (step 8..64); 25 primera convolución terminada. Los marcadores 17 y 18 anteriores permanecen.
- No se introduce asignación dinámica, incremento de stack, cambio de topología neuronal o modificación de MCTS.

Validación: compilación y ejecución C++17 nativa con 3 búsquedas y 100 jugadas sin nuevas llamadas a `new` en las rutas medidas; comparación de salida (valor y política) de `Network::evaluate_legal` entre v0.2.30 y v0.2.31 sobre posición inicial: idéntica con la precisión mostrada. ZIP verificado.

**No se ha compilado con SDK ARM ni probado físicamente.** Los datos de v0.2.28 no permiten demostrar que la primera convolución fuera la causa raíz: solo era el último marcador registrado. Este parche agrega límites explícitos y un lugar de diagnóstico exacto, y conserva las correcciones de memoria de v0.2.30.
