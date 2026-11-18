# picoBit v0.1.12 — Optimización del evaluador NumPy de Nurse

Este parche **sólo** modifica `picoBit/src/bnn.py`, agrega una prueba y actualiza
`picoBit/etc/VERSION`. Se aplica encima de v0.1.11, en la raíz de Akkad.

## Cambio de implementación (sin cambio de algoritmo)

- Antes: nueve iteraciones Python en la primera convolución y otras nueve en la
  segunda, con llamadas pequeñas a NumPy; y 256 multiplicaciones/acumulaciones
  en un generador Python para la salida.
- Ahora: *gather* vectorizado de los nueve vecinos, máscara SAME de padding
  explícita, XNOR y popcount `uint64` vectorizados en toda la segunda
  convolución, y producto escalar `np.dot` vectorizado para la salida.
- Se conservan los pesos Q20, la disposición de bits little-endian, el formato
  `.bnni`, el mismo codificador de piezas, las estadísticas de BN precalculadas,
  el convenio sign(0)=+1 y la salida en centipeones.
- No hay DLL, TensorFlow, compilación ni nuevas dependencias en inferencia.
- No se modifica `train.py`, la arquitectura, Nurse ni los checkpoints.

## Verificaciones

- Prueba de v0.1.11: 24 posiciones sintéticas vs fórmula flotante original,
  diferencia máxima 0 cp en este entorno.
- Comparación diferencial v0.1.11/v0.1.12 sobre 750 posiciones sintéticas con
  tres juegos de pesos, diferencia máxima 0 cp.
- Prueba de referencia adicional con implementación literal de convoluciones
  empaquetadas: `python picoBit/tests/test_numpy_xnor_v012.py`.

Microbenchmark aislado en este entorno: aproximadamente 0.414 ms/evaluación
(v0.1.11) y 0.199 ms/evaluación (v0.1.12) en 250 posiciones sintéticas;
aceleración 2.08×. Es **tiempo de evaluación**, no tiempo por nodo del minimax.
La comparación definitiva es el benchmark en tu hardware, con tu `best.bnn`.

## Prueba

Desde raíz Akkad:

```
python picoBit/tests/test_numpy_equivalence.py
python picoBit/tests/test_numpy_xnor_v012.py
python picoBit/src/bnn.py --network picoBit/assets/best.bnn
```

Mantener la configuración `bitty` existente; la única condición es disponer
previamente de v0.1.11 y de sus dependencias NumPy/h5py.
