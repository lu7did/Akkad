# Hive — Arquitectura conceptual y asuntos pendientes

**Estado:** síntesis de discusión; no es una especificación cerrada ni autorización para implementar.  
**Fecha:** 23 de noviembre de 2026 (hora de Argentina).  
**Versión:** 0.1.

## 1. Propósito y alcance

**Hive** (antes denominado «picoHive») es un **concentrador/orquestador UCI** que se presenta al mundo exterior como un solo motor, aunque no necesita poseer ni ejecutar un algoritmo de ajedrez propio. Mantiene el frontend de la partida, conoce la posición, genera los movimientos legales, reparte subconjuntos entre endpoints UCI, reúne resultados y elige una jugada final.

Los endpoints pueden ser motores heterogéneos: picoSargon (minimax/alpha-beta/STEROIDS), AlphaZero (MCTS), Sargon clásico, motores de redes neuronales, Stockfish, Leela Chess Zero, players de Nurse y **otros Hives**. Pueden ejecutarse en placas embebidas o equipos Windows, macOS o Linux. Cada uno conserva su algoritmo, sus opciones y su paralelismo.

## 2. Estructura lógica

```text
GUI / FICS / Nurse / Challenger / cliente UCI
                       |
                 stdin / stdout
                       |
                +-------------+
                |   Hive A    |  (raíz, frontend UCI)
                +-------------+
                  /    |     \
            TCP/UCI TCP/UCI TCP/UCI
               /       |       \
           Stockfish  Sargon   Hive B
                               /  |  \
                            Motor Motor Hive C
                                        |
                                      Motor ...
```

- **Interfaz exterior primaria:** UCI estándar por `stdin`/`stdout`. Si se requiere TCP para recibir partidas, se dispone un listener como **capa de transporte**, separada de la lógica de Hive.
- **Interfaz hacia endpoints:** conexiones **TCP/UCI persistentes**, con un listener/adaptador cuando un motor solo ofrece UCI por proceso local.
- **Recursividad:** un Hive puede aparecer como endpoint de otro Hive y distribuir internamente el trabajo recibido, sin que el padre conozca su topología.
- **Cálculo local opcional:** un Hive puede ser solo concentrador o tener motor propio en implementaciones pequeñas. El cálculo local se modela como otro endpoint, no como obligación del master.

### Responsabilidad del Hive que controla la partida

1. Interpretar `uci`, `isready`, `ucinewgame`, `position`, `go`, `stop`, `quit` y demás operaciones UCI necesarias.
2. Mantener/reconstruir la posición y enumerar movimientos legales.
3. Aplicar también restricciones de `searchmoves` recibidas cuando actúa subordinado.
4. Mantener conexiones y estados de endpoints y distribuir subconjuntos de movimientos.
5. Recibir resultados, comprobar legalidad/coherencia y seleccionar `bestmove`.
6. Respetar los límites de tiempo y evitar bloqueos ante pérdidas de endpoints.

### Responsabilidad de cada endpoint

Recibe la misma posición raíz con **una o varias jugadas permitidas** y las analiza con su propio algoritmo. Informa su mejor movimiento dentro del subconjunto, evaluación en cp y, cuando corresponda, tiempo, profundidad alcanzada y nodos. No conduce la partida; solo analiza el conjunto asignado.

## 3. Operación UCI: distribución y resultados

La primitiva que permite restringir alternativas en la raíz es **`searchmoves`**:

```text
position startpos moves ...
go movetime 3000 searchmoves e2e4 d2d4
```

Las restricciones se aplican **a la raíz**; las continuaciones son responsabilidad del algoritmo interno. Hive necesita verificar que el endpoint implementa `searchmoves` *de verdad*; ser compatible con UCI no garantiza esa capacidad.

La respuesta UCI consiste en mensajes `info` (puntuación y estadísticas cuando estén disponibles) y `bestmove` (movimiento elegido). El texto `bestmove` **no contiene por sí mismo cp, tiempo, profundidad ni nodos**: Hive deberá asociar esa información con la búsqueda y los mensajes de salida correspondientes. La evaluación puede ser una cota `lowerbound`/`upperbound`, no necesariamente exacta.

**Sin acuerdo aún:** política precisa de límites de búsqueda transmitidos en `go`; la profundidad y los nodos no son unidades universales de trabajo entre minimax y MCTS.

## 4. Endpoints estáticos y dinámicos

| Aspecto | Estáticos | Dinámicos |
|---|---|---|
| Alta | Definidos en configuración | Descubiertos por anuncios/respuestas a **broadcast UDP periódico** |
| Conexión inicial | Hive la intenta al arrancar | Hive la intenta tras el descubrimiento |
| Desconexión | Se marca caída y **reintenta periódicamente** | Se marca caída y se retira del conjunto disponible |
| Vuelta al servicio | Intentos activos periódicos | **No hay intentos activos**; solo se vuelve a contactar cuando aparece un **nuevo anuncio** |

El descubrimiento identifica dirección `IP:puerto` y eventualmente que el endpoint es otro Hive. Los motores UCI convencionales sin descubrimiento requieren una capa que los anuncie.

**Decisión explícita:** el diseño actual **NO tiene protocolo de contratación**. Las ofertas/reservas UDP del diseño anterior de picoHive quedan descartadas; hay descubrimiento y conexiones UCI, no contratos.

### Hive subordinado y topología

Se acordó que un Hive con una conexión activa como subordinado de otro Hive **no puede usar simultáneamente su interfaz UCI para recibir una partida independiente**. Puede seguir repartiendo el trabajo de su padre entre sus propios endpoints. Quedan por diseñar la exclusión de sesiones, conflictos de conexiones concurrentes y la prevención de ciclos (`A → B → A`). No existe aún un protocolo de admisión aprobado.

## 5. Flujo de una búsqueda

1. El Hive raíz recibe `position` y `go`.
2. Calcula el conjunto de movimientos legales, o el subconjunto autorizado por su padre.
3. Asigna subconjuntos de movimientos entre endpoints disponibles.
4. Envía a cada endpoint la posición completa y solo sus `searchmoves`.
5. Los endpoints analizan independientemente y devuelven su mejor jugada con la telemetría disponible.
6. Si un endpoint es otro Hive, este redistribuye recursivamente y devuelve un resultado consolidado.
7. El Hive raíz consolida y responde `bestmove` por su frontend UCI.

La distribución exacta y la selección final no están cerradas.

## 6. Balanceo de carga: dirección acordada

La intención es un **balanceador adaptativo, puramente empírico y agnóstico del algoritmo**, sin conocimientos de profundidad, NPS, núcleos ni arquitectura interna.

**Acuerdos:**

- **Todos los endpoints comienzan con capacidad relativa 1**.
- **No se harán benchmarks ni acertijos Bratko–Kopec** al conectar ni recalibraciones en cascada.
- El reparto evoluciona **lentamente**, a partir de búsquedas reales y con una media móvil para amortiguar el ruido de jugadas particularmente caras o baratas.
- Un endpoint que recibe más carga de la que puede manejar debería tardar relativamente más y recibir gradualmente menos trabajo.
- El aprendizaje funciona **localmente en cada Hive**: un Hive padre observa a otro Hive como una caja negra.
- Un Hive con diez motores detrás **no debería tratarse necesariamente como un único motor** frente a nueve endpoints directos; la potencia relativa, no el número de conexiones, debe determinar la asignación.
- **No se utilizará el flujo continuo de mensajes `info` para balancear**; generaría demasiado tráfico de red.

### Métrica propuesta

Si el endpoint `i` recibe `m_i` movimientos de raíz y tarda `T_i` de tiempo de pared en entregar el resultado:

```text
costo_observado_i = T_i / m_i           # segundos por movimiento raíz asignado
capacidad_estimada_i ∝ 1 / promedio_móvil(costo_observado_i)
```

Una media móvil exponencial sería posible, pero **su coeficiente, límites y reglas de actualización NO están acordados**.

### Problema fundamental aún sin resolver

**Si los motores agotan el mismo `movetime`, el tiempo de pared no mide capacidad.** Por ejemplo, dos motores de velocidad muy distinta pueden usar exactamente 3 segundos y devolver resultados de calidades distintas; entonces `T_i/m_i` puede recompensar indebidamente a quien recibió más jugadas. La convergencia por realimentación negativa **no está demostrada** bajo esas condiciones.

Esto no se resuelve con NPS ni profundidad: son específicas de algoritmos y se descartaron como criterio universal. Tampoco se aprobó utilizar eventos `info` intermedios. Por ello, **la métrica y el scheduler siguen siendo hipótesis de diseño**, aunque la orientación general de aprendizaje lento está acordada.

### Capacidad de un Hive con muchos descendientes

Un Hive subordinado puede representar una capacidad de procesamiento mucho mayor (o menor) que un endpoint individual. Se discutió transmitir capacidad agregada y sumar capacidades, pero después se priorizó el **aprendizaje puramente observado**, sin propagar pesos internos. **El arranque en frío de un Hive grande permanece abierto**; asignarle 1 no refleja necesariamente su potencia y contar descendientes tampoco permite estimarla correctamente.

### Alternativa mencionada, no aprobada

Dividir los movimientos en lotes pequeños y entregar trabajo adicional al endpoint que termina antes. Puede aproximarse a un reparto por demanda, pero aumenta las transacciones UCI y puede perder ventajas de búsquedas conjuntas. No se eligió como arquitectura definitiva.

## 7. Consolidación de puntuaciones heterogéneas

Cada endpoint devuelve una mejor jugada entre las asignadas y una puntuación cp cuando sea posible. **No está acordado** cómo escoger globalmente entre puntuaciones de algoritmos y evaluadores diferentes.

Un `+80 cp` de AlphaZero, un `+60 cp` de Sargon y un `+40 cp` de Stockfish no garantizan una escala uniforme. Además, con conjuntos raíz disjuntos, cambiar qué motor evalúa cada movimiento puede cambiar la jugada final.

Se discutieron **máximo cp literal**, **normalización**, **verificación de finalistas** y otros criterios, sin aprobar ninguno. La política de consolidación debe ser independiente del transporte.

El intercambio de **alpha global** se descartó del contrato básico: cotas de motores/evaluadores incompatibles no son intercambiables. Queda como posible extensión futura para motores realmente compatibles.

## 8. Robustez: requisitos identificados, diseño pendiente

- **Tiempo de partida y límites:** `stop`, deadlines y propagación de cancelación en cascada, sin multiplicar tiempos por nivel.
- **Fallas de conexión:** remover temporalmente clientes caídos, tratar resultados tardíos, decidir si se redistribuyen trabajos pendientes; no se presupone motor local.
- **Consistencia:** asociar mensajes `info` y `bestmove` a la solicitud correcta y verificar que cada resultado respete el conjunto `searchmoves` asignado.
- **Topología:** impedir ciclos y doble participación independiente de un Hive subordinado.
- **Distribución discreta:** algunos tableros tienen menos movimientos legales que endpoints; gestionar redondeo y nodos ociosos.
- **Conformidad UCI:** determinar el comportamiento ante motores que no implementan `searchmoves`, no informan cp, no responden a `stop` o usan convenciones diferentes.
- **Tráfico de red:** favorecer una solicitud por lote y respuestas consolidadas, evitando telemetría continua entre Hives.

## 9. Estado observado de los motores de Akkad

La revisión de código discutida se concentró en el repositorio <https://github.com/lu7did/Akkad>:

| Motor/componente | Hallazgo preliminar |
|---|---|
| **picoSargon ARM** | Usa `DEPTH`, `QDEPTH` y `TIMEOUT_MS` definidos en firmware. Su frontend UCI examinado **no filtra `searchmoves`** ni interpreta `go depth` dinámico; su motor registra tiempos, nodos y profundidad. |
| **picoSargon x86** | **Sí** interpreta `go depth`, `go movetime`, `setoption name QDepth` y `Cores` bajo MULTICORE; **no** implementa `searchmoves` en el frontend examinado. |
| **AlphaZero C++** | Se observaron opciones UCI de límites de búsqueda, pero no se encontró filtrado `searchmoves` en el frontend revisado. |
| **picoAlpha / picoKeras** | Sus rutas UCI observadas requieren examinar/adaptar el tratamiento de `searchmoves`. |
| **Nurse** | La capa UCI analizada preserva `searchmoves` para determinados backends; eso no prueba que todos los players lo respeten. |

**Criterio de implementación futura:** si se añade `searchmoves` a picoSargon, debe filtrar las jugadas **antes de ejecutar la búsqueda**, en mono/multinúcleo y en todas las plataformas relevantes, no solo ARM. Esto debe mantenerse separado del diseño general de Hive.

Referencias consultadas:

- <https://github.com/lu7did/Akkad/blob/main/picoSargon/ARM/src/pico_main.cpp>
- <https://github.com/lu7did/Akkad/blob/main/picoSargon/ARM/src/engine.cpp>
- <https://github.com/lu7did/Akkad/blob/main/picoSargon/x86/src/host_main.cpp>
- <https://github.com/lu7did/Akkad/blob/main/AlphaZero/src/akkad_alphazero_main.cc>
- <https://github.com/lu7did/Akkad/blob/main/picoAlpha/src/main.cpp>
- <https://github.com/lu7did/Akkad/blob/main/nurse/src/nurse/uci.py>

## 10. Registro ejecutivo de acuerdos y pendientes

### Acordado

1. Nombre del proyecto: **Hive**, no picoHive.
2. Hive es un **concentrador UCI**, con motor de cálculo propio solo opcionalmente.
3. Frontend UCI estándar por `stdin/stdout`; TCP externo mediante listener independiente.
4. Endpoints por TCP/UCI, heterogéneos y eventualmente recursivos (Hive dentro de Hive).
5. Distribución de subconjuntos de movimientos raíz, idealmente mediante `searchmoves`.
6. Descubrimiento mixto: endpoints estáticos con reintento periódico; dinámicos anunciados por UDP y **sin reintento activo** tras caer.
7. **Sin contratación.**
8. Un Hive subordinado no recibe al mismo tiempo otra partida independiente.
9. Sin benchmark artificial ni calibración Bratko–Kopec.
10. Pesos iniciales iguales y aprendizaje lento a partir de experiencias reales, sin exigir conocimiento del algoritmo.
11. No emplear telemetría UCI continua entre Hives para balancear.
12. Considerar a **todas las plataformas picoSargon**, no solamente ARM, al evaluar compatibilidad con Hive.

### Aún por resolver

1. **Cómo estimar capacidad desde tiempos de pared cuando se agota `movetime`**: problema prioritario.
2. Política precisa de `go`, plazos, trabajo incompleto y cancelaciones en motores distintos.
3. Reparto discreto, convergencia del promedio móvil, exploración y posible asignación por lotes.
4. Arranque en frío y adaptación de un Hive subordinado con numerosos clientes, sin benchmarks.
5. Comparabilidad y selección final entre puntuaciones cp heterogéneas.
6. Topología sin ciclos y exclusividad de sesiones UCI subordinadas.
7. Esquema exacto de anuncios UDP, deduplicación e identidad.
8. Recuperación ante fallos y manejo de resultados desfasados.
9. Compatibilidad efectiva de los endpoints con `searchmoves` y su información de puntuación.
10. Experimentos para valorar eficiencia, escalabilidad y calidad de jugada frente a motores aislados.

## 11. Próximo paso recomendado

**Continuar la discusión sin implementar todavía.** Prioridad: identificar una señal de rendimiento robusta y agnóstica del algoritmo bajo búsquedas con plazo fijo, o reconocer formalmente que el balanceador no puede inferir capacidad con la información disponible. En paralelo, definir la política de agregación de puntuaciones heterogéneas. Ambos afectan a la corrección conceptual del sistema más que cualquier detalle de conexiones o estructura de directorios.
