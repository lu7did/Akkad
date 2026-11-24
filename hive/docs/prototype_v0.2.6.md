# Hive v0.2.6 — Probabilidades de asignación `kmin`

Cada entrada de `engines:` admite una propiedad **opcional** `kmin` (número de 0 a 1).

- Se comprueba durante la carga que la suma de todos los `kmin` **configurados** sea <= 1; un valor no numérico, no finito o fuera de rango aborta Hive.
- Para los motores conectados y elegibles en la asignación: el motor con `kmin` recibe ese peso fijo; el resto de la probabilidad hasta 1 se distribuye **solo entre motores sin `kmin`**, ponderado por el inverso del tiempo de pared de la prueba UCI.
- El cálculo se repite al conectarse o desconectarse motores y se recalcula para el conjunto de motores libre en cada búsqueda. Un motor ocupado no recibe trabajo.
- Las instancias locales adicionales se crean sin duplicar el `kmin` de la plantilla, porque de otra manera la suma de mínimos podría exceder 1.
- Si todos los motores elegibles tienen `kmin` explícito y su suma es menor que 1, el remanente queda sin asignar (la suma efectiva es menor que 1). Para repartir **una cantidad finita de movimientos**, la agenda compara proporcionalmente los pesos positivos existentes, por lo que distribuye igualmente todas las jugadas.
- Si todos los pesos explícitos son cero, se utiliza asignación uniforme como salvaguarda para no perder ninguna jugada.
- Los `kmin` no actúan como garantía de que un motor reciba al menos una jugada cuando hay muy pocas posiciones, ni como garantía de capacidad física. Se interpretan como pesos de reparto a largo plazo.

Ejemplo:

```yaml
engines:
  - {name: alphazero, type: uci, path: 'C:/engines/AlphaZero.exe', kmin: 0.3}
  - {name: stockfish, type: uci, path: 'C:/engines/stockfish.exe', kmin: 0.3}
  - {name: picoSargon, type: uci, path: 'C:/engines/picoSargon.exe'}
```

Los pesos son 0.3, 0.3 y 0.4. Si hay dos picoSargon sin `kmin`, se reparten 0.4 proporcionalmente a su velocidad de prueba.

La telemetría muestra `latency_k`, `kmin`, `priority` y `total_priority` por separado.

Pruebas: `python -m unittest discover -s hive/tests -p 'test_v026.py'`.
