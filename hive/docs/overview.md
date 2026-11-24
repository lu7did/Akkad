Revisé la implementación actual de **picoSargon ARM con&#x20;**`TWINS=ON` directamente en el repositorio Akkad, particularmente estos tres archivos:

- [pico_main.cpp](https://github.com/lu7did/Akkad/blob/main/picoSargon/ARM/src/pico_main.cpp?utm_source=chatgpt.com) — coordinación entre núcleos.
- [engine.cpp](https://github.com/lu7did/Akkad/blob/main/picoSargon/ARM/src/engine.cpp?utm_source=chatgpt.com) — búsqueda, alpha-beta y publicación de resultados.
- [engine.hpp](https://github.com/lu7did/Akkad/blob/main/picoSargon/ARM/include/engine.hpp?utm_source=chatgpt.com) — estructuras de datos y estado del motor.

La conclusión principal es que **TWINS implementa paralelismo a nivel de movimientos raíz, con un alpha global compartido y sincronización al finalizar cada profundidad**. No reparte dinámicamente los nodos interiores del árbol.

## **1. Arquitectura de ejecución**

**Core 0 — Coordinador**

UCI, WiFi, reloj, iterative deepening, selección final

Estado compartido en RAM

shared_alpha

Atómico

twin_job / twin_stop

Control

**Core 0**

Movimientos pares

Board propio

Engine propio

TT y heurísticas propias

NNUE Bashful A

Negamax/PVS

**Core 1**

Movimientos impares

Board propio

Engine propio

TT y heurísticas propias

NNUE Bashful B

Negamax/PVS

**Barrera de sincronización**

Core 0 espera la finalización de Core 1

Compara resultados y decide si progresa a depth + 1

## **2. ¿Qué información recibe el segundo núcleo?**

El núcleo 0 prepara un trabajo completo antes de despertar al núcleo 1.

Las variables compartidas principales son:

| Variable        | Contenido                                |
| --------------- | ---------------------------------------- |
| `twin_board`    | Copia completa de la posición raíz       |
| `twin_roots`    | Lista de movimientos asignados al core 1 |
| `twin_depth`    | Profundidad de la iteración actual       |
| `twin_deadline` | Instante límite para terminar            |
| `twin_alpha`    | Mejor puntuación global publicada        |
| `twin_stop`     | Señal de interrupción                    |
| `twin_job`      | Estado del trabajo: 0, 1 o 2             |

El código asigna movimientos alternados:

```
for(size_t i=0; i<all.size(); ++i)
    (i & 1 ? right : left).push_back(all[i]);
```

Así, si hay 30 movimientos legales:

- Core 0 recibe 15 movimientos: índices 0, 2, 4, ..., 28.
- Core 1 recibe 15 movimientos: índices 1, 3, 5, ..., 29.

El reparto es estático por cantidad de movimientos, **no por carga computacional**. Que ambos reciban 15 movimientos no garantiza que trabajen el mismo tiempo.

Cada núcleo dispone de su propia instancia `Engine`, con su tabla de transposiciones de 256 entradas, heurísticas *killer*, historial, contadores y buffers de búsqueda. Las dos copias de los pesos Bashful son inmutables y están embebidas en FLASH.

## **3. ¿Cómo comparten alpha?**

Esta es la parte central de la implementación.

El código define:

```
std::atomic<int> twin_alpha{-1000000};
```

Al comenzar cada nueva profundidad, el core 0 reinicia el valor:

```
twin_alpha.store(-1000000, std::memory_order_release);
```

Ambos núcleos reciben una referencia a ese mismo objeto atómico:

```
search_partition(
    board,
    roots,
    depth,
    deadline,
    twin_alpha
);
```

Cada núcleo consulta el alpha global antes de explorar un movimiento raíz:

```
const int threshold =
    shared_alpha.load(std::memory_order_acquire);
```

El valor representa la mejor puntuación raíz publicada hasta ese momento, en centipeones y desde el punto de vista del jugador que tiene el turno.

### **Ejemplo**

Supongamos que ambos núcleos están buscando a profundidad 5.

1. **Core 0 encuentra +35 cp.**

   Publica `shared_alpha = 35`.
2. **Core 1 lee alpha = 35.**

   Usa ese umbral para buscar si su próximo movimiento podría superar +35.
3. **Core 1 encuentra +70 cp.**

   Después de verificar la puntuación, publica `shared_alpha = 70`.
4. **Core 0 lee alpha = 70.**

   Sus movimientos posteriores pueden descartarse con mayor rapidez si no consiguen superar ese umbral.

La publicación utiliza `compare_exchange_weak`, por lo que un núcleo solo puede aumentar el mejor alpha compartido, nunca reducirlo.

**Un detalle fundamental:** no se comparte beta. El límite beta se calcula localmente para cada llamada de búsqueda. La información cooperativa global se limita a alpha en la raíz.

## **4. ¿Qué calcula el núcleo antes de publicar su resultado?**

La implementación utiliza una búsqueda de reconocimiento (*scout*) seguida, cuando corresponde, de una verificación.

Para un umbral finito `threshold`, primero ejecuta:

```
value = -negamax(
    b,
    depth-1,
    qdepth_,
    -threshold-1,
    -threshold,
    1,
    false
);
```

Es una búsqueda con ventana estrecha, de un centipeón.

Si el resultado no supera el umbral:

```
candidate = value > threshold;
```

el movimiento se descarta como candidato a mejorar la mejor puntuación conocida.

Si supera el umbral, se realiza una segunda búsqueda:

```
value = -negamax(
    b,
    depth-1,
    qdepth_,
    -INF,
    -lo,
    1,
    true
);
```

Donde `lo` es el umbral observado.

Esta segunda búsqueda verifica el candidato y permite publicar una puntuación de raíz.

El propósito es evitar búsquedas completas de movimientos que no pueden mejorar el resultado global.

## **5. ¿Cómo avanza al siguiente nivel?**

El mecanismo es **iterative deepening sincronizado**.

Para cada profundidad \\(d\\):

1. Core 0 ordena la lista raíz, colocando primero el mejor movimiento de la iteración completa anterior.
2. Divide nuevamente los movimientos entre ambos núcleos.
3. Reinicia `twin_alpha` y la señal de parada.
4. Copia tablero, movimientos, profundidad y plazo al trabajo del core 1.
5. Publica `twin_job = 1`, indicando que hay un trabajo pendiente.
6. Core 0 ejecuta su propia partición mientras core 1 ejecuta la suya.
7. Core 0 espera que `twin_job` pase a 2.
8. Si ambas particiones finalizaron correctamente, compara sus mejores resultados y actualiza el movimiento principal.
9. Solo entonces comienza \\(d+1\\).

El core 1 no decide cuándo aumentar la profundidad. Tampoco ejecuta por su cuenta un ciclo de iterative deepening: procesa la profundidad que recibió y vuelve a esperar.

## **6. ¿Qué devuelve el segundo núcleo?**

La función:

```
SearchResult Engine::search_partition(...)
```

devuelve una estructura `SearchResult` que incluye, entre otros datos:

| Campo                  | Significado                                     |
| ---------------------- | ----------------------------------------------- |
| `best`                 | Mejor movimiento encontrado en su partición     |
| `score`                | Puntuación del mejor candidato de su partición  |
| `depth`                | Profundidad completada, o 0 si se interrumpió   |
| `nodes`                | Nodos visitados                                 |
| `qnodes`               | Nodos contabilizados en búsqueda de quiescencia |
| `tt_hits`              | Aciertos de su TT local                         |
| `tt_stores`            | Almacenamientos en la TT                        |
| `cutoffs`              | Cortes de búsqueda                              |
| `elapsed_ms`           | Duración de su trabajo                          |
| `twin_scouts`          | Búsquedas scout realizadas                      |
| `twin_prunes`          | Candidatos descartados                          |
| `twin_alpha_publishes` | Actualizaciones del alpha compartido            |
| `twin_verify_nodes`    | Nodos usados en verificaciones                  |

El core 1 escribe esta estructura en `twin_result` y publica:

```
twin_job.store(2, std::memory_order_release);
```

El core 0 espera con:

```
while (twin_job.load(std::memory_order_acquire) != 2) {
    service();
    // Comprobación de stop y deadline
    tight_loop_contents();
}
```

Durante esa espera continúa atendiendo WiFi, watchdog y las condiciones de cancelación.

La combinación `release/acquire` permite que el core 0 vea el resultado completo después de observar `twin_job == 2`.

## **7. Una limitación importante del diseño actual**

Hay una debilidad que merece atención: **el alpha global se comparte, pero la información de búsqueda interna no**.

Esto implica:

- No se comparten las tablas de transposiciones.
- No se comparte la variación principal completa.
- No se intercambian heurísticas killer ni history.
- No hay distribución dinámica de los movimientos cuando un núcleo termina antes.
- Cada profundidad tiene una barrera obligatoria.

Por ejemplo, si un núcleo necesita 80 ms y el otro 400 ms, el primero queda ocioso durante buena parte del tiempo restante.

Además, el resultado de los movimientos que no superan el alpha compartido se registra como `-INF`. Eso simplifica la selección del ganador global, pero tiene una consecuencia delicada: el `score` devuelto por una partición puede no ser una evaluación exacta de su mejor movimiento cuando todos sus candidatos fueron descartados.

La comparación final actual es:

```
const bool choose_b =
    b.has_move && b.score > a.score;
```

Por eso convendría verificar formalmente los invariantes de puntuación y selección, especialmente ante cambios concurrentes de alpha, interrupciones y empates. No afirmo que exista un fallo reproducible, pero es un punto que requiere pruebas específicas de equivalencia con búsqueda mononúcleo.

## **8. Evaluación de la estrategia de paralelismo**

La principal ventaja del diseño es su sencillez: cada núcleo trabaja con un tablero independiente, evitando bloqueos en la mayor parte del árbol. La cooperación mediante alpha permite descartar trabajo innecesario.

Su desventaja es que el reparto estático puede desequilibrarse considerablemente. Además, cada nueva profundidad vuelve a dividir las raíces, pero conserva el mismo conjunto de movimientos hasta que la iteración termine.

**Mi recomendación:** antes de modificar el algoritmo, medir cuánto tiempo permanece ocioso cada núcleo en la barrera y qué proporción de nodos se dedica a scouts frente a verificaciones. Si el desequilibrio es significativo, el siguiente cambio de mayor impacto sería una cola dinámica de movimientos raíz, conservando `shared_alpha` y la sincronización por profundidad.

Eso permitiría que un núcleo que termina su movimiento tome otro pendiente, en lugar de esperar al otro. No modificaría todavía la búsqueda interna ni compartiría las tablas de transposiciones: introducir ambas cosas simultáneamente aumentaría demasiado la complejidad de validación.
