# picoAlpha v0.2.25 — Memoria, fases de inferencia y MCTS

Parche incremental **sobre v0.2.24**. Sustituir solo archivos incluidos. Se mantiene PA_DUAL_CORE_NN=ON.

- `NoMemoryExpansion`: rechazo de ampliación aborta exclusivamente esa simulación sin backup ficticio ni contabilizarla. Se bloquea el nodo afectado para evitar reintentos idénticos; la selección continúa por otras ramas. Solo al agotarse el árbol completo se informa `memory_saturated`.
- Se mantienen los contadores de rechazo del guardarraíl y se agregan contadores específicos de simulaciones abortadas, ramas bloqueadas y terminales.
- Terminales: cuentan como visitas y propagan su valor en vez de repetir una hoja terminal sin actualizar N/Q.
- Comprueba que q y logits legales sean finitos antes del softmax; no cambia el signo PUCT (`score=-q+u` para Q guardado desde la perspectiva del hijo).
- Se distinguen fase 9 (inferencia), 16 (entrada al workspace), 17 (workspace listo y entrada a convolución) y 18 (primera convolución terminada) en el marcador persistente.
- `MCTS_INTEGRITY` registra estadísticas y anomalías. No cambia `AZ_SIMULATIONS` (128), tiempo ni parámetros PUCT.

## Verificación
Compilar los archivos modificados con el toolchain del Pico antes de desplegar. Prueba nativa de sintaxis y semántica del árbol registrada por el generador. No hay ejecución ni benchmark físico.

## Alcances
Si todas las ramas están bloqueadas, `memory_saturated` concluye sin introducir valores nuevos. El resultado de inferencia no se valida contra LC0: la comprobación de signo se limita a la convención de `Tree::traverse` y `score=-q+u` y a controles de finitud. El watchdog puede activarse por causas no detectables en estos puntos.
