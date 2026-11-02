# picoSargon ARM v0.2.20 — TWINS: memoria y búsqueda cooperativa

Incremental respecto a TWINS v0.2.19; aplicar desde la raíz `akkad/`.

## Compilación

TWINS=ON activa `PICOSARGON_TWINS`, TWINS=OFF usa las rutas originales protegidas por condicionales. No se toca el motor x86 ni la ruta ARM sin TWINS. Para Pico 2 W usar `PICO_BOARD=pico2_w`.

## Cambios

- Antes de **cada** nivel, la mejor jugada del nivel anterior se coloca en la primera posición de la lista raíz; luego se vuelven a repartir las jugadas con el esquema fijo alternado entre núcleos.
- Los scouts de ventana nula rechazan candidatos que no superan la cota global; solo los que pueden superarla requieren re-búsqueda. La ventana de verificación comienza en el umbral conocido (en lugar de `[-INF,+INF]`). Las cotas globales se publican únicamente después de verificar el resultado. No hay cambios en la profundidad de búsqueda.
- Buffers persistentes por nivel de invocación y por motor para movimientos legales, pseudo-legales y ordenación; el SEE también usa buffers reutilizados. En TWINS la ordenación estable usa inserción en el lugar, sin `stable_sort`/reservas temporales.
- Cada copia de Board reserva un historial de 128 plies para su búsqueda (evita crecimiento del vector en cada push/pop mientras no exceda ese tamaño).
- Las dos instancias Engine siguen separadas, al igual que sus buffers, TT, historial, killers y red Grumpy. Se mantiene el reparto raíz fijo y la barrera por profundidad.
- Telemetría añadida: `scout_nodes`, `verify_nodes`, `buffer_allocations`, `research_avoided`. `buffer_allocations` contabiliza las reservas/crecimientos instrumentados de los buffers de Engine, **no todas las operaciones malloc del firmware**. `research_avoided` cuenta candidatos descartados por scout, NO nodos ahorrados frente a un baseline.

## Estado de validación

Se verificó la sintaxis del núcleo C++ con TWINS encendido y apagado, incluyendo `PICOSARGON_STEROIDS`. No se probó el firmware en RP2350 ni se comprobó consumo máximo SRAM, stack ni equivalencia de jugadas en torneo. Estas pruebas son obligatorias antes de desplegar sobre el dispositivo de competición.

## Riesgos

Las ventanas alfa-beta y la TT incluyen cotas: los scouts no deben confundirse con scores exactos. La activación de buffers persistentes suma consumo de SRAM por Engine; verificar mapa y stack máximo en el hardware. Además, cambiar ordenación puede cambiar líneas PV, nodos y selección ante empates aunque la puntuación sea equivalente.
