# picoBit 0.1.13 — perfil y optimización verificable

Solo modifica `picoBit/src/bnn.py`. Python/NumPy, sin DLL, TensorFlow, nuevo modelo ni cambios al entrenamiento.

## Optimizaciones

1. Se precalculan **ambas variantes del turno**, los 12 códigos de piezas, el estado vacío y un código separado para el padding de la primera convolución. Se elimina el recálculo del canal de turno en cada posición, así como la aplicación de máscaras temporales en esta capa. La fila de padding aporta cero.
2. `np.bitwise_xor` y `np.bitwise_count` usan buffers persistentes para la convolución 2 y la densa. El producto exacto de signos se obtiene mediante `N - 2*popcount(XOR)`, equivalente a `2*popcount(XNOR)-N`.
3. Se precalcula la cantidad de entradas válidas para convolución `SAME`. Se excluye la contribución de posiciones fuera del tablero.
4. El plegado Q20 existente de BatchNormalization y salida se preserva sin cambios.

Los buffers son **por instancia** y asumen uso secuencial del evaluador, como el proceso Nurse actual; llamadas simultáneas sobre la misma instancia requieren sincronización externa.

## Validación

Prueba de referencia sin TensorFlow: `python picoBit/tests/test_numpy_xnor_v013.py`.
Prueba adicional frente a cálculos flotantes sintéticos: `python picoBit/tests/test_numpy_equivalence.py`.
No se dispone en este entorno de los pesos reales `best.bnn` ni de un benchmark completo de Nurse.

Perfil sobre los mismos tableros para ambos evaluadores (desde la raíz del repositorio):

```powershell
python .\picoBit\tools\ps\profile_inference.py --network .\picoBit\assets\best.bnn
```

**No es una comparación controlada** comparar `buddy` (player `sargon`, Depth=2, QDepth=0) contra `bitty` (player `sargon-plus`, Depth=4, QDepth=2). Para comparar tiempos/nodo del evaluador hace falta fijar idéntico buscador y configuración.
