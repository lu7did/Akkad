# Akkad

*“A new mind for the old buddy”*

Manual operativo, arquitectura y referencia de uso

Dr. Pedro E. Colla

(FCyT-UADER-Argentina)

**Versión 1.0000**

|                         |                                           |
|------------------------:|:------------------------------------------|
| **Estado documentado:** | v0.6.93                                   |
|              **Fecha:** | 11 de Octubre de 2026                     |
|          **Audiencia:** | Operación, pruebas, extensión y auditoría |

Manual de referencia consolidado de la arquitectura funcional del proyecto Akkad. El proyecto está formado por los siguientes paquetes:

* Sargon-NNUE. Plataforma de motores y evaluadores para juego de ajedrez.
* Challenger. Plataforma de juego de ajedrez independiente.
* micro Sargon. Port restringido de Sargon-NNUE a Raspberry Pico W1/2.


# Propósito y principio arquitectónico

## Objetivo general

En ésta documentación se expone en detalle la arquitectura de *Sargon-NNUE*, los otros aplicativos se puede referir a su documentación de base.

Se desarrolla a partir de módulos jugadores y evaluadores que implementan como base el algoritmo Sargón original y evolucionan a partir de el.

Sargon-NNUE es una plataforma experimental que integra redes neuronales
de distinta arquitectura al motor de juego, la arquitectura integra 
varios formatos de redes neuronales de otros paquetes (Cerebrum, Leela, etc) y un formato nativo de red neuronal NNUE (Efficiently Updatable Neural Network).

Desde un punto de vista de arquitectura separa dos fuentes de táctica a menudo entremezcladas en motores de ajedrez:

1.  el algoritmo que explora el árbol de juego (*player*);
2.  la función que asigna valor a una posición (*evaluator*).

El API dominante será entonces modelado alrededor de una interfaz:

``` python
Evaluator:
    evaluate(board) -> score_cp (desde el punto de vista de blancas)

Player:
    choose(board) -> MoveChoice
```

Los evaluadores devuelven centipawns desde perspectiva blanca. Los players deciden qué posiciones deben ser evaluadas y cómo convertir esas evaluaciones en una jugada.

## Qué se intenta aislar

El proyecto intenta que puedan compararse por separado mediante diferentes players:

- profundidad y política de búsqueda;
- ordenamiento de jugadas;
- quiescence;
- evaluación estática;
- redes aprendidas;
- podas selectivas;
- límites de tiempo y de nodos;
- coste del backend de evaluación.

Esta separación permite definir en forma aislada el módulo de jugada (player) y el de evaluación de jugada (evaluador). Los API de es fundamental para interpretar correctamente experimentos del tipo:

    SARGON depth=3 + CLASSIC
    SARGON depth=3 + CEREBRUM
    SARGON depth=3 + STOCKFISH evaluator

porque el algoritmo de búsqueda puede mantenerse fijo mientras cambia únicamente la función de evaluación en la medida que se trate de pares
compatibles.

# Evolución del proyecto

El proyecto se podría sumarizar como "*nunca fue en realidad ajedrez*".
El proyecto nace y evoluciona a partir de un esfuerzo de exploración 
sobre posibles estrategias y plataformas para implementarlas, con énfasis
en el uso de distintas arquitecturas de redes neurales para dar soporte
a la evaluación.

La configuración, interfaz y proceso de entrenamiento de las distintas
redes es una de las fuentes prioritarias de exploración del proyecto.

## Sargon: the old buddy


Sargón fue el primer motor de juego para ajedrez automático comercialmente
accesible, si bien existieron esfuerzos anteriores estaban normalmente
implementados en grandes plataformas de cómputos (mainframe, VAX y otras) que tenían escasas opciones de accederlas. 
**Sargon** fue desarrollado por **Dan y Kathe Spracklen** y presentado en 1978. Ese año ganó las cinco partidas del torneo de ajedrez para microcomputadoras celebrado en la **West Coast Computer Faire**, uno de los primeros hitos competitivos del ajedrez en computadoras personales.
Su importancia no radica en haber inventado la búsqueda ajedrecística, sino en demostrar que una microcomputadora de 8 bits, con memoria y potencia muy limitadas, podía ejecutar un jugador competitivo para su época. También contribuyó a popularizar el ajedrez informático entre aficionados y programadores.
Sargon fue escrito en **lenguaje ensamblador Z80**. Según la descripción de sus autores, ocupaba aproximadamente **8 KB de RAM**, distribuidos en unos 4 KB de lógica de juego, 2 KB de datos y 2 KB de interfaz gráfica.
Sus principales componentes eran:

- **Representación del tablero y generación de movimientos:** rutinas especializadas por pieza, con comprobaciones de legalidad, jaques, enroque y captura al paso.
- **Búsqueda:** exploración en profundidad de un árbol de movimientos mediante **poda alfa-beta**, para descartar ramas que no podían mejorar la decisión.
- **Evaluación:** puntuación heurística de las posiciones, basada en material y consideraciones ajedrecísticas; incluía análisis de intercambios para reducir errores tácticos con un costo computacional contenido.
- **Interfaz:** visualización del tablero e interacción con el usuario, adaptadas a las capacidades de los equipos de la época.
No utilizaba redes neuronales ni aprendizaje automático: sus decisiones procedían de reglas, búsqueda y evaluación diseñadas explícitamente.
Sargon ayudó a consolidar el ajedrez como demostración práctica de **búsqueda heurística en hardware restringido**. El libro *Sargon: A Computer Chess Program* (1978), que incluía su código fuente comentado, facilitó el estudio, la adaptación y la enseñanza de técnicas de programación de motores de ajedrez. La familia Sargon tuvo posteriores versiones y adaptaciones para diversas computadoras personales.
Su legado resulta especialmente relevante para proyectos contemporáneos que combinan motores clásicos y evaluadores neuronales: permite observar qué aporta la búsqueda y qué aporta el mecanismo de evaluación, dos componentes conceptualmente separables. Esta última comparación es una interpretación tecnológica, no una característica de la arquitectura original.

### Fuentes

- Computer History Museum, [*Sargon: A Computer Chess Program*](https://www.computerhistory.org/chess/sft-431614f63c4c4/).
- Dan y Kathe Spracklen, [*Sargon: A Computer Chess Program* (1978), texto y listado histórico](https://chessforeva.bitbucket.io/govs/Oldies/Sargon.htm).
- Computer History Museum, [Dan y Kathe Spracklen en el campeonato ACM de 1978](https://www.computerhistory.org/chess/stl-431f4cc14ba4b/).

### Algoritmo "*Sargon*"
Sargón implementó un algoritmo de ajedrez suficientemente efectivo como 
para sorprender y batir a un jugador casual, aunque no así a jugadores 
mas expertos.
Sargón usa un método de búsqueda llamado *MiniMax* optimizado para 
reducir el número de exploraciones mediante una lógica de poda (*prunning*) de opciones basada en un algoritmo denominado *alpha/beta*.
El ajedrez presenta una cantidad incomensurable de combinaciones posibles,
en el orden de $10^{130}$ lo que garantiza que ni aún utilizando cada átomo en el universo conocido como un computador cuántico sería imposible (por 40 órdenes de magnitud) calcular todas las alternativas.
Sargón utiliza un algoritmo relativamente simple de evaluación. En ajedrez 
cada turno de movida se denomina *ply*. Sargon evalúa que jugadas son
posibles en un momento dado del juego, toma cada una y simula hacerla. La nueva configuración del tablero es evaluada por una función heurística única
que combina un promedio ponderado de distintos factores tales como 
valor de las piezas involucradas, ciertas preferencias de juego (por ejemplo dominar el centro) y alternativas ganadoras tales como jaque mate (checkmate). Como resultado de la evaluación se pondera en que medida esa nueva posición favorece a uno u otro jugador. El objetivo es maximizar el valor de quien juega o negar el valor al oponente (*NegaMax*).  Si se mira solo una jugada adelante Sargón juega con *1 ply* de horizonte. Ese algoritmo se puede expandir para que cada jugada en 1 ply se explote en las jugadas posibles para luego evaluar cada una, y 
así sucesivamente. 
A medida que aumenta el número de ply utilizados el número de posiciones evaluadas aumenta geométricamente. Para limitar el tiempo de respuesta
el algoritmo se define de una profundidad (depth) objetivo, usualmente
2-ply.
La mejor jugada del análisis es la que se realiza.
El análisis se hace desde la perspectiva de las piezas blancas, por lo tanto
si quien evalúa la jugada lo hace con blancas intentará optimizar el valor
y si lo hace con negras minimizarlo.
Posteriormente se explorará el algoritmo con mas detalle.
Por su perspectiva histórica y por considerarse que Sargón permitía un
nivel de ajedrez básico se toma como referencia de éste proyecto. Si el
resultado puede batir en promedio a un programa con el algoritmo Sargón se
lo considerará aceptable. 

## Bobby: conocimiento almacenado frente a política jugable

Bobby fue el punto de partida de la línea de investigación. El mismo 
intenta un enfoque basado en la *ecuación de Bellman* para el aprendizaje
por refuerzos. Básicamente se establece un ambiente que define las reglas
de ajedrez y se expone al motor principal a una combinación de jugadas históricas recreadas desde los archivos .png que las describen o 
aleatorias. 

### Idea fundamental

Un agente aprende a elegir acciones que maximicen la **recompensa acumulada esperada**, no simplemente la recompensa inmediata. La ecuación de Bellman expresa que el valor de una posición depende de la recompensa obtenida ahora y del valor esperado de las posiciones futuras:

$\[V^\pi(s)=\mathbb{E}_{a\sim\pi,\,s'\sim P}\left[r(s,a,s')+\gamma V^\pi(s')\right]\]$

Para aprender directamente qué acción conviene, puede utilizarse una función de acción-valor:

$\[Q^*(s,a)=E\left[r(s,a,s')+\gamma\max_{a'}Q^*(s',a')\right]
\]$

Aquí, \(s\) es el estado del tablero, \(a\) una jugada legal, \(r\) la recompensa, \(\gamma\) el descuento de recompensas futuras y \(Q(s,a)\) una estimación de la conveniencia de jugar \(a\) en \(s\).

### Cómo funciona en ajedrez

1. **Jugar y explorar:** el agente disputa partidas, por ejemplo mediante autojuego, usando su política actual y cierta exploración.
2. **Registrar experiencias:** almacena transiciones \((s,a,r,s',\text{fin})\), o trayectorias completas, en un *replay buffer*.
3. **Construir un objetivo:** combina la recompensa y una estimación del valor futuro; en posiciones terminales utiliza el resultado definitivo de la partida.
4. **Actualizar la red:** ajusta sus parámetros para reducir la diferencia entre el valor predicho y el objetivo de entrenamiento.
5. **Repetir y evaluar:** genera nuevas partidas y contrasta la fuerza del agente frente a una referencia estable.

### ¿Qué aprende?

Aprende una **función de valor** \(V(s)\) o **función de acción-valor** \(Q(s,a)\), que permite comparar posiciones o jugadas según su contribución probable al resultado final. Si se incorpora una cabeza de política, también aprende qué jugadas priorizar. No aprende necesariamente reglas explícitas como «desarrollar piezas»; estas preferencias pueden emerger estadísticamente de las experiencias.

### Dificultades prácticas: experiencia en Bobby

- **Recompensa escasa y tardía:** muchas jugadas preceden al resultado final; asignar correctamente el mérito o la culpa es difícil. Una partida que dura 100 movimientos y termina de una forma proyecta una señal de recompensa muy ruidosa sobre las posiciones mas alejadas del final.
- **Arranque con una red aleatoria:** las primeras decisiones son casi arbitrarias. Terminar una partida proporciona una señal válida, pero no garantiza que sea suficiente para aprender buen ajedrez.
- **Propagación inestable:** los objetivos de Bellman dependen de predicciones que la propia red está modificando (*bootstrapping*); pueden aparecer oscilaciones y estimaciones erróneas que se refuerzan mutuamente.
- **Exploración frente a explotación:** si se explora poco, se repiten malas decisiones; si se explora demasiado, las partidas contienen poca información estratégica aprovechable.
- **Costo computacional y cobertura:** el espacio de estados del ajedrez es enorme; generar suficientes partidas y entrenar con ellas consume tiempo y recursos.
- **Perspectiva del jugador:** al alternar turnos, los valores deben manejar correctamente el cambio de signo y los resultados de victoria, derrota y tablas.
- **Validación de progreso:** una pérdida de entrenamiento menor no implica un motor más fuerte. Se necesitan partidas de evaluación contra rivales fijos y pruebas reproducibles.

**Bellman proporciona el principio de aprendizaje, pero no resuelve por sí sola el problema de entrenar un buen jugador.** En Bobby, el obstáculo central no era lograr que el motor completara partidas, sino convertir esas experiencias en señales confiables que mejorasen progresivamente la selección de jugadas.
Una estrategia práctica es empezar con un motor y evaluador de referencia, verificar el mecanismo de actualización con problemas pequeños y recién después escalar el autojuego y el entrenamiento.
Claramente el experimento encontró sus límites rápidamente, pero permitió desarrollar el criterio con que se representaría el estado del tablero en todas las evoluciones posteriores.
La evolución del tablero debe tener en cuenta cada una de las posiciones del mismo, la posición de cada pieza remanente en una jugada en particular, el registro de las condiciones sobre derechos de enroque y paso, la condición de mate, el número de jugadas redundantes (para tablas por repetición) y las reglas de 75 movidas (para tablas).

## Nyx: otra infraestructura, mismo cuello de botella estratégico

Nyx buscó superar el límite de Bobby mediante una organización diferente de los componentes donde se capturaban los elementos de política de juego y decisión de movida a partir de los datos de aprendizaje. La nueva infraestructura facilitó experimentación, pero dejó visible un problema de fondo: el mecanismo de selección de jugadas seguía siendo débil. Mejorar la fuente de datos o la red no corregía automáticamente la lógica que exploraba las respuestas del adversario.
Es decir, el final de la partida como señal de aprendizaje resulta muy ruidoso en el entrenamiento de una red NNUE que solo capture el valor de una posición.
La gran contribución de ésta etapa fue comprender que elementos de infraestructura son necesarios para operar un motor de ésta indole, nació la necesidad de tener componentes *listener* en un puerto TCP, mediante entrada/salida estándar, soportar el protocolo UCI, poder hacer bridge con los principales motores externos tales como *lichess.org* (integrando su componente *lichess-bot*) y separar las funciones de *auto-juego* y *entrenamiento*. 

## Akkad: búsqueda, aprendizaje y necesidad de auditoría

Akkad incorporó experimentación más explícita con profundidad, extensiones y mecanismos de aprendizaje de la búsqueda. Esto hizo evidente la necesidad de registrar por separado cómo se elegían candidatas, cuánto se exploraba y de dónde provenía una puntuación. 
La arquitectura, originalmente monolítica se transformó en sub-sistemas independientes que permitían aislar el origen de una regresión: evaluación, búsqueda, integración y control temporal quedaban entremezclados.
Nació de esa forma el componente sargon-NNUE descripto en mas detalle 
luego.
El esfuerzo demostró la importancia de estabilizar el proceso de evaluación con otros mecanismos que no fueran el *auto-juego* puesto que mientras la 
plataforma está evolucionando es dificil catalizar análisis sobre las
mejoras o deterioros asociados a una acción. Para solucionar eso se creo una plataforma auxiliar denominada *challenger*, el cual es básicamente un jugador automático capaz de jugar con un motor Sargon simple o permitir a un humano hacer una partida contra el motor principal. 
Esta instancia, si bien no prosperó como un programa independiente quedó
como nombre del contenedor que tiene los distintos componentes y del 
proyecto en general (la relación entre Sargon y Akkad es demasiado atractiva para perderla).

## Sargon-NNUE: modularidad como principio de arquitectura

Sargon-NNUE tiene un enfoque arquitectónico orientado al plug-in de 
componentes especializados sobre un bus común de interfaces API establecidas (o contratos). De esa manera se separa al  *player* (genera y selecciona movimientos) de *evaluator* (estima valor posicional), y ubica fuera de ambos la preparación de datos, el entrenamiento, la comparación UCI y la auditoría. Challenger puede actuar como infraestructura de ejecución externa. Dado que la evaluación sobre si la arquitectura es adecuada y si las modificaciones la mejoran o no se incorporan componentes de *match* que permiten jugar a diferentes combinaciones de player/evaluador entre si. Incluso se puede organizar verdaderos torneos o *rally* donde una dada
mezcla de combinaciones player/evaluador compiten entre si pudiendo observar con algo mas de rigor las fortalezas relativas. El diseño permite usar una misma búsqueda con varios evaluadores y un evaluador con distintas búsquedas, conservar configuraciones reproducibles y diagnosticar límites concretos sin reemplazar subsistemas completos.

# Arquitectura

## Visión por capas

    PGN (partidas externas / maestros)
            |
        (prepare) selecciona partidas y etiquetas
            |  
            v
    SQLite .pb --- audit dataset --- train --- (checkpoint) .npz
            |                               |
            +-------------> evaluators <---+
                               ^
                               |
                            players
          Sargon/Sargon-Plus/Cerebrum/Stockfish/LC0/Random
                               |
                            UCI API
                      stdin / TCP listen
                               |
                MATCH / SELFPLAY / (external player)
                               |
                             RALLY
                               |
                        JSONL / PGN / CSV
                               |
                 sargon_audit / judge / differential

Para gestionar las múltiples combinaciones de una pareja player/evaluator se almacenan los mismos bajo un nombre clave (de fantasía) en un repositorio
denominado *brains.json* los programas refieren a ese repositorio no solo
para obtener el par player/evaluator sino también la configuración de los
mismos, esa configuración recibe el nombre de *brain*.
El API de los players respetan la convensión es valorar las jugadas en
terminos de *centipawns* con signo positivo para las blancas y signo negativo para las negras.


## Perfiles de brain y prioridades de configuración

Un archivo JSON contiene `schema_version` y el objeto `brains`. Cada brain selecciona `player`, `evaluator`, sus argumentos, rutas y metadatos `rating_elo`. Las opciones generales no pertinentes a un player pueden ignorarse cuando no generan inconsistencia; una combinación semánticamente inválida debe rechazarse. El caso especial `stockfish` como player exige evaluador `null`. Los nombres de las claves de red son específicos de cada tipo de evaluador.



### Organización actual de componentes y contratos

```text
Akkad/
  Sargon-NNUE/
    src/sargon_nnue/
      players/        # estrategias de juego, UCI local y UCI/TCP
      evaluators/     # evaluadores clásico, NPZ, LC0, Grumpy, etc.
      az_core.py      # codificación de acciones y estados AlphaZero
      az_model.py     # modelo de política/valor
      az_policy.py    # políticas por posición
      az_prepare.py   # preparación de datos AlphaZero
      az_seed_train.py, az_train.py
      sargon_prepare.py, sargon_train.py
      sargon_listen.py, sargon_match.py
    scripts/          # lanzadores PowerShell
    data/pb/          # corpus de posiciones y etiquetas
    data/runs/        # entrenamientos y checkpoints
    data/brains/      # configuración de players/evaluadores
    data/test/        # CSV de auditoría y comparación
  picoSargon/         # proyecto externo con adaptador UCI en Sargon-NNUE
  picoAlpha/          # proyecto externo con adaptador UCI en Sargon-NNUE
  challenger/
```

La ubicación de los proyectos externos no constituye un enlace de código fuente obligatorio: la integración principal se produce por el protocolo **UCI**. Las unidades lógicas del motor son:

- **Estado**: `chess.Board` (posición, turno, enroques, al paso, relojes, historial disponible).
- **Evaluación escalar**: puntuación en centipeones, normalmente expresada desde la perspectiva de las blancas en la interfaz de evaluadores; el algoritmo de búsqueda convierte el signo cuando corresponde.
- **Evaluación de política/valor**: distribución de probabilidades sobre jugadas legales y valor de posición, directamente o mediante WDL (victoria/tablas/derrota).
- **Selección**: movimiento UCI legal, puntuación reportada, profundidad, nodos, latencia y tipo de player.
- **Transporte**: llamadas en proceso, subproceso UCI o socket TCP con comandos UCI.

## Flujo de búsqueda y valor

Para cada posición legal, el player elegido considera jugadas, consulta el evaluador cuando corresponde, aplica la semántica terminal (mate, tablas, jugadas ilegales) y entrega `bestmove`. Cada player utiliza la heurística que se le diseñe y solo depende de sus parámetros externos de configuración y de los valores entregados por el evaluador para una determinada posición. La profundidad principal mide plies; `qdepth` extiende de manera selectiva situaciones tácticamente no estabilizadas. No es correcto identificar `qdepth=3` con una búsqueda exhaustiva adicional de tres plies.

## Trazabilidad y reproducibilidad

Una corrida posee configuración de jugadores, perfiles de brains, manifiestos, procesos de motor, movimientos FEN y resultados. 
Las auditorías persistentes deben mantener el vínculo `run_id`, `match_id`, `game_id`, `ply` y `search_id` o equivalentes que permitan correlación sin ambigüedad. 
Los datos originales son JSONL; los CSV se derivan a posteriori y permanecen dentro del directorio de la misma corrida. Los hashes ayudan a identificar código y checkpoints, pero no sustituyen el control de versiones ni verifican por sí solos el comportamiento.

# Players: API de contratos, parámetros y algoritmos

## Resumen de motores

| Player        | Evaluadores admisibles                | Criterio de selección                                                               |
|:--------------|:--------------------------------------|:------------------------------------------------------------------------------------|
| `sargon`      | classic, npz, cerebrum-1.1, stockfish | Exploración clásica sobre árbol y valoración de hojas.                              |
| `sargon-plus` | Ídem sargon                           | SargonCore con BOOST (optimizaciones de búsqueda) y TURBO (presupuesto adaptativo). |
| `cerebrum`    | Principalmente cerebrum-1.1           | Selección a un ply mediante red y quiescence opcional, sin el conjunto BOOST.       |
| `stockfish`   | Sólo null                             | Stockfish selecciona y evalúa internamente.                                         |
| `lc0`   | Sólo null                             | Leela Chess (lc0.exe) selecciona y evalúa internamente.                                         |
| `random`      | null                                  | Jugada legal aleatoria; referencia de minima no basada en evaluación.                 |



### Players adicionales y conectores

| Player | Función | Evaluación |
|---|---|---|
| `random` | Selección aleatoria entre movimientos legales | No necesita red |
| `sargon` | Búsqueda minimax/negamax con poda alpha-beta | Escalar |
| `sargon-plus` | Búsqueda alpha-beta ampliada con mejoras selectivas, `--boost` y `--turbo` | Escalar |
| `alphazero` | MCTS con prioridades de política y valor neuronal | Política y valor |
| `doc` | Estrategia alternativa de búsqueda | Configurable |
| `cerebrum` | Estrategia asociada al ecosistema Cerebrum | Configurable |
| `stockfish`, `lc0` y motores UCI | Búsqueda ejecutada por programa externo | `null` en el proceso supervisor |
| `picoSargon`, `picoAlpha` | Adaptadores a los motores C++ de Windows mediante protocolo UCI | `null` cuando el motor ejecuta su propia evaluación |
| `external` | Motor UCI remoto identificado por `host:puerto` | `null` |

El catálogo concreto y las identidades operativas se configuran en los archivos de *brains*. Distinguir el **nombre del player** del **nombre del evaluador** impide duplicar búsquedas: si un programa UCI decide internamente, Sargon-NNUE lo trata como un jugador autónomo.

## Parámetros comunes y de selección

| Campo        | Obligación  | Función y valor si se omite                                                                                       |
|:-------------|:------------|:------------------------------------------------------------------------------------------------------------------|
| `player`     | Obligatorio | Identifica el buscador; no existe valor universal seguro.                                                         |
| `evaluator`  | Condicional | Requerido para jugadores con evaluación externa; `null` implícito en player Stockfish.                            |
| `depth`      | Opcional    | Profundidad de búsqueda principal; el valor por defecto depende de la clase/factory.                              |
| `qdepth`     | Opcional    | Máximo de extensiones tácticas; en Cerebrum el valor omitido conserva su comportamiento base: 0.                  |
| `tmax`       | Opcional    | Presupuesto por búsqueda en milisegundos; perfil explícito prevalece sobre default.                               |
| `boost`      | Opcional    | Máscara de 16 bits; 0 deshabilita todos los algoritmos BOOST.                                                     |
| `turbo`      | Opcional    | Máscara `0x00`–`0x03`; 0 deshabilita control adaptativo.                                                          |
| `network`    | Condicional | Ruta a checkpoint NPZ o modelo Cerebrum, obligatoria si la instancia necesita red y no tiene default configurado. |
| `rating_elo` | Opcional    | Metadato de ranking; no equivale al Elo operativo de Stockfish.                                                   |

Los defaults exactos dependen del entry point y del tipo de player, por lo que el perfil explícito es el contrato reproducible; no se deben inventar valores únicos para todos los lanzadores. En los perfiles de competición actualmente utilizados se fijan `depth=2`, `qdepth=2`, `tmax=15000` para Sargon-Plus.

# Algoritmos de evaluación de jugadas

## Algoritmo Sargon

El núcleo de búsqueda implementa exploración de árbol adversarial con alternancia MAX/MIN o su forma negamax, poda alpha–beta, manejo terminal, niveles iterativos y protección del resultado completo más reciente. En negamax: $$V(s,d,\alpha,\beta)=\max_{a\in A(s)}\{-V(T(s,a),d-1,-\beta,-\alpha)\}.$$ La poda es legítima cuando $\alpha\geq\beta$, siempre que la evaluación y los límites sean coherentes. El resultado elegido por la raíz puede depender del orden ante empates; una búsqueda selectiva puede depender del orden también por reducciones y podas. Los guardrails conservan el último nivel completo si el intento posterior agota el presupuesto. El núcleo conserva responsabilidades compartidas para evitar duplicar semántica terminal en Sargon-Plus.



### Detalles del coste y tratamiento terminal

El tablero define estados `s`, acciones legales `A(s)` y transiciones `T(s,a)`. En una posición terminal se aplican valores de mate o empate. En hojas no terminales se utiliza `E(s)`, evaluada mediante el módulo seleccionado. Para profundidad `d`, la formulación negamax es:

\[
N(s,d)=\begin{cases}
E(s), & d=0\text{ o condición terminal}\;,\\
\max_{a\in A(s)}[-N(T(s,a),d-1)], & d>0.
\end{cases}
\]

La forma alpha-beta mantiene límites `α` (mejor cota inferior del jugador que mueve) y `β` (cota superior impuesta por el adversario). Para cada jugada, se evalúa recursivamente `score = -search(child, d-1, -β, -α)`; después se actualiza `α = max(α,score)` y se abandona el resto de la rama si `α ≥ β`. La poda es exacta respecto del minimax a la profundidad elegida siempre que se mantengan los invariantes de la búsqueda. El orden de movimientos altera fuertemente el número de nodos, no el resultado matemático de una búsqueda completa.

**Evaluación terminal:** mate, ahogado, reglas de tablas y posiciones terminales reciben tratamiento diferenciado. En mate se incorpora la distancia en plies para preferir mates más cortos y retrasar mates inevitables. El historial de la posición es importante para repetición, regla de las cincuenta jugadas y otros efectos ajedrecísticos.

**Coste:** sin podas, una búsqueda uniforme con factor de ramificación `b` y profundidad `d` visita del orden de `O(b^d)` nodos. Alpha-beta, bajo ordenamiento muy favorable, se aproxima a `O(b^{d/2})` en el caso ideal; no elimina el peor caso exponencial.

### 4.1 Profundidad, tiempo y búsqueda táctica

La profundidad se mide en *plies* (medias jugadas). Un límite temporal detiene nuevas expansiones y utiliza el resultado de la última iteración suficientemente completada. La búsqueda de quietud (*quiescence*, `qdepth`) prolonga una hoja inestable con secuencias tácticas seleccionadas, especialmente capturas y situaciones de jaque, para reducir el efecto horizonte. La función de quietud examina primero una evaluación estática (*stand pat* cuando es admisible) y después jugadas tácticas, con sus propias podas alpha-beta.

## Algoritmo Monte Carlo Tree Search (MCTS)
# MCTS con red neuronal: política, valor y búsqueda PUCT

## Propósito

**Monte Carlo Tree Search (MCTS)** es un algoritmo de búsqueda que construye incrementalmente un árbol de posiciones mediante simulaciones. En la variante utilizada por motores de estilo **AlphaZero/Leela Chess Zero**, una red neuronal guía la exploración mediante una **política** de movimientos y estima el **valor** de las posiciones. No es necesario terminar cada simulación en un resultado de partida: la evaluación neuronal puede sustituir a un *rollout* hasta el final.

## Información de cada nodo y arista

Una posición de ajedrez define un estado \(s\), con el jugador al turno y su información relevante (incluido historial cuando la red o las reglas lo requieren). Para cada movimiento legal \(a\) que parte de \(s\), el árbol almacena típicamente:

| Dato | Símbolo | Significado |
|---|---|---|
| Prior de política | \(P(s,a)\) | Probabilidad inicial atribuida al movimiento por la red, normalizada entre movimientos legales. |
| Visitas | \(N(s,a)\) | Cantidad de simulaciones que atravesaron esa arista. |
| Valor acumulado | \(W(s,a)\) | Suma de las evaluaciones retropropagadas, con perspectiva coherente. |
| Valor medio | \(Q(s,a)\) | \(W(s,a)/N(s,a)\) si \(N>0\). |
| Hijo | \(s'\) | Estado resultante de aplicar \(a\) a \(s\). |

También se mantiene el total de visitas del nodo \(N(s)=\sum_b N(s,b)\). Una implementación puede almacenar estadísticas en nodos o aristas y aprovechar transposiciones, siempre que preserve la semántica de los valores.

## Las cuatro etapas de una simulación

### A. Selección (PUCT)

Desde la raíz, se elige repetidamente la arista que maximiza una combinación de explotación y exploración:

\[
a^*=\arg\max_{a\in\mathcal A(s)}\left[Q(s,a)+U(s,a)\right]
\]

\[
U(s,a)=c_{\mathrm{puct}}\,P(s,a)\,\frac{\sqrt{\sum_b N(s,b)}}{1+N(s,a)}.
\]

Aquí \(Q\) representa la utilidad observada y \(U\) favorece inicialmente movimientos con alta probabilidad de política y pocas visitas. A medida que crece \(N(s,a)\), su bonificación de exploración disminuye. Esta es una formulación simplificada de PUCT: implementaciones concretas, como LC0, pueden usar constantes dinámicas y otros ajustes.

### B. Expansión

Cuando se alcanza una posición no expandida, se generan sus movimientos legales y se consulta la red neuronal. La red produce dos salidas principales:

- **Política**: puntuaciones o *logits* \(z_a\), convertidos a probabilidades legales, por ejemplo mediante *softmax*:

  \[
  P(s,a)=\frac{e^{z_a}}{\sum_{b\in\mathcal A(s)}e^{z_b}}.
  \]

- **Valor**: una estimación \(v(s)\in[-1,1]\), donde \(+1\) indica victoria esperada para el jugador que debe mover, \(0\) empate y \(-1\) derrota. Si la red devuelve probabilidades WDL, puede formarse una utilidad escalar \(v=p_{\mathrm{win}}-p_{\mathrm{loss}}\), conservando WDL por separado cuando interesa.

Las probabilidades \(P(s,a)\) se asignan como *priors* a las aristas nuevas. El valor \(v(s)\) se utiliza para actualizar las estadísticas del trayecto. **La política no es un valor de posición ni garantiza que el movimiento más probable sea el mejor**; dirige el presupuesto de búsqueda.

### C. Evaluación terminal

Si la posición alcanzada es terminal, no hace falta consultar la red: se utiliza el resultado real de la partida desde la perspectiva apropiada (victoria \(+1\), empate \(0\), derrota \(-1\)).

### D. Retropropagación (*backup*)

Al volver de la hoja hacia la raíz se actualizan las aristas recorridas:

\[
N(s,a)\leftarrow N(s,a)+1,\qquad
W(s,a)\leftarrow W(s,a)+v,\qquad
Q(s,a)\leftarrow\frac{W(s,a)}{N(s,a)}.
\]

En un juego de suma cero, **al cambiar de jugador se invierte el signo del valor**: \(v\leftarrow-v\). La convención debe fijarse claramente; en las fórmulas de selección, \(Q(s,a)\) debe expresar la expectativa desde la perspectiva del jugador que elige en \(s\).

## Elección del movimiento efectivo

Se realizan simulaciones hasta agotar un presupuesto, generalmente de nodos o tiempo. **Durante la búsqueda se maximiza \(Q+U\); al decidir el movimiento real normalmente se utilizan las visitas**, no el máximo \(Q+U\):

\[
a_{\mathrm{juego}}=\arg\max_a N(s_0,a).
\]

En autojuego o entrenamiento puede aplicarse muestreo con temperatura \(\tau\):

\[
\pi(a\mid s_0)=\frac{N(s_0,a)^{1/\tau}}{\sum_b N(s_0,b)^{1/\tau}}.
\]

La distribución de visitas \(\pi\) puede constituir la señal de entrenamiento para mejorar la política neuronal.

## Estructura de datos orientativa

```python
class Edge:
    move: str       # jugada, por ejemplo UCI
    prior: float    # P(s,a)
    visits: int     # N(s,a)
    value_sum: float  # W(s,a), desde el punto de vista del jugador en s
    child: "Node | None"

    @property
    def q(self):
        return self.value_sum / self.visits if self.visits else 0.0

class Node:
    position: object
    expanded: bool
    edges: list[Edge]
    # Opcional: estado terminal, transposiciones, historial y metadatos
```

## Pseudocódigo resumido

```text
repetir mientras quede presupuesto:
    nodo = raíz
    recorrido = []
    mientras nodo esté expandido y no sea terminal:
        arista = argmax(Q + U)
        recorrido.agregar(arista)
        nodo = hijo(arista)
    si nodo es terminal:
        v = resultado_terminal(nodo)
    si no:
        P, v = red_neuronal(nodo.posición)
        crear_aristas_legales(nodo, normalizar(P))
    para cada arista del recorrido, en orden inverso:
        v = -v   # invertir perspectiva entre jugadores
        actualizar N, W y Q de la arista con v
jugar la acción con mayor cantidad de visitas en la raíz
```

## Rol efectivo de la red neuronal

La red cumple **dos funciones distintas y complementarias**. La política \(P\) decide dónde conviene concentrar la exploración; el valor \(v\) aproxima la calidad de las posiciones descubiertas. MCTS acumula evidencia mediante visitas y promedios \(Q\), por lo que sus decisiones no son una simple lectura directa de la red. Una red sin entrenamiento puede guiar mal la búsqueda, y aumentar simulaciones no garantiza por sí solo buena calidad ajedrecística.

## Diferencia respecto de Sargon Plus

Sargon Plus, con alfa-beta y *quiescence*, explora variantes hasta cierta profundidad y solicita valoraciones de posiciones al evaluador. MCTS/PUCT selecciona dinámicamente qué ramas visitar usando \(P\), \(N\) y \(Q\), incorpora el valor neuronal en hojas y elige normalmente la jugada por visitas. Si se usa una red LC0 como evaluador de Sargon Plus, se puede aprovechar su **valor** sin que el player se transforme automáticamente en MCTS: la estrategia de exploración sigue siendo alfa-beta.

**Nota de alcance:** exposición conceptual de AlphaZero/PUCT; las estructuras, convenciones y constantes exactas pueden variar entre implementaciones.

## Uso combinado

La arquitectura permite intercambiar, con cierta libertad, players y 
evaluadores. En tal sentido puedo utilizar un evaluador stockfish con un
algoritmo de jugada Sargon o éste con un evaluador basado en la red
Cerebrus. Es decir el jugador no necesariamente tiene que usar la
representación de evaluación que le es nativa (Classic para Sargon, 
NPZ para SargonPlus, Cerebrum para Cerebrum, etc). En todos los casos 
el evaluador retorna un valor de posición normalizado y consistente
entre todos los posibles evaluadores. Algunas combinaciones son, por supuesto, mas efectivas que otras.
En el caso de evaluación lc0, que es la requerida por el jugador 
AlphaZero, hay una diferencia. El algoritmo MCTS requiere dos valores
provenientes del evaluador, el valor de la posición y un vector con la
política para las jugadas permitidas. Eso es provisto por el evaluador
lc0 a partir de la evaluación de la red del mismo origen (fija y pre-entrenada). También es posible usar el evaluador lc0 con jugadores como SargonPlus, simplemente se ignora el resultado de política y el resultado es aún así suficientemente bueno.
Sin embargo la evaluación del algoritmo MCTS con una red NNUE nativa no da buen resultado, al faltar el dato de la política a priori la misma no puede ser sintetizada facilmente solo con los datos de valor. El resultado, si bien técnicamente posible, es una muy mala estrategia donde jugadas o encuadres posicionales muy triviales no son reconocidos. Debido a eso tal combinación no es utilizada.

# Arquitectura de Jugadores

## Player Sargon-Plus

La variante Sargon-Plus reutiliza SargonCore y agrega un conjunto de optimizaciones independientes controladas por bits. BOOST cambia la estructura u orden del árbol; TURBO decide si continuar a profundidad mayor, reducir candidatos o abortar el siguiente nivel. Ningún bit BOOST debe interpretarse como aumento garantizado de fuerza competitiva; puede mejorar velocidad y perjudicar selección bajo determinadas condiciones.

## Player Cerebrum

Implementa un player simple capaz de operar con la red neural *Cerebrum V1.1*
CerebrumPlayer considera las jugadas legales, aplica cada candidata y obtiene su valor de la red neural Cerebrum 1.1. Con `qdepth=0` conserva selección a un ply; con `qdepth>0` agrega negamax alpha–beta táctico, evaluando stand-pat en posiciones estables, capturas/promociones relevantes y todas las evasiones legales cuando está en jaque. La profundidad quiescence no representa una segunda búsqueda principal full-width. La red incremental reutiliza información del tablero padre cuando el API del evaluador lo permite. La evaluación terminal prevalece sobre el valor estimado de red.

## Player AlphaZero

Se trata de implementar un algoritmo MCTS con red neuronal de manera de poder establecer la  política, valor y búsqueda PUCT.
**Monte Carlo Tree Search (MCTS)** es un algoritmo de búsqueda que construye incrementalmente un árbol de posiciones mediante simulaciones. En la variante utilizada por motores de estilo **AlphaZero/Leela Chess Zero**, una red neuronal guía la exploración mediante una **política** de movimientos y estima el **valor** de las posiciones. No es necesario terminar cada simulación en un resultado de partida: la evaluación neuronal puede sustituir a un *rollout* hasta el final.

### Información de cada nodo y arista

Una posición de ajedrez define un estado \(s\), con el jugador al turno y su información relevante (incluido historial cuando la red o las reglas lo requieren). Para cada movimiento legal \(a\) que parte de \(s\), el árbol almacena típicamente:

| Dato | Símbolo | Significado |
|---|---|---|
| Prior de política | \(P(s,a)\) | Probabilidad inicial atribuida al movimiento por la red, normalizada entre movimientos legales. |
| Visitas | \(N(s,a)\) | Cantidad de simulaciones que atravesaron esa arista. |
| Valor acumulado | \(W(s,a)\) | Suma de las evaluaciones retropropagadas, con perspectiva coherente. |
| Valor medio | \(Q(s,a)\) | \(W(s,a)/N(s,a)\) si \(N>0\). |
| Hijo | \(s'\) | Estado resultante de aplicar \(a\) a \(s\). |

También se mantiene el total de visitas del nodo \(N(s)=\sum_b N(s,b)\). Una implementación puede almacenar estadísticas en nodos o aristas y aprovechar transposiciones, siempre que preserve la semántica de los valores.

### Las cuatro etapas de una simulación

#### A. Selección (PUCT)

Desde la raíz, se elige repetidamente la arista que maximiza una combinación de explotación y exploración:

\[
a^*=\arg\max_{a\in\mathcal A(s)}\left[Q(s,a)+U(s,a)\right]
\]

\[
U(s,a)=c_{\mathrm{puct}}\,P(s,a)\,\frac{\sqrt{\sum_b N(s,b)}}{1+N(s,a)}.
\]

Aquí \(Q\) representa la utilidad observada y \(U\) favorece inicialmente movimientos con alta probabilidad de política y pocas visitas. A medida que crece \(N(s,a)\), su bonificación de exploración disminuye. Esta es una formulación simplificada de PUCT: implementaciones concretas, como LC0, pueden usar constantes dinámicas y otros ajustes.

#### Expansión

Cuando se alcanza una posición no expandida, se generan sus movimientos legales y se consulta la red neuronal. La red produce dos salidas principales:

- **Política**: puntuaciones o *logits* \(z_a\), convertidos a probabilidades legales, por ejemplo mediante *softmax*:

  \[
  P(s,a)=\frac{e^{z_a}}{\sum_{b\in\mathcal A(s)}e^{z_b}}.
  \]

- **Valor**: una estimación \(v(s)\in[-1,1]\), donde \(+1\) indica victoria esperada para el jugador que debe mover, \(0\) empate y \(-1\) derrota. Si la red devuelve probabilidades WDL, puede formarse una utilidad escalar \(v=p_{\mathrm{win}}-p_{\mathrm{loss}}\), conservando WDL por separado cuando interesa.

Las probabilidades \(P(s,a)\) se asignan como *priors* a las aristas nuevas. El valor \(v(s)\) se utiliza para actualizar las estadísticas del trayecto. **La política no es un valor de posición ni garantiza que el movimiento más probable sea el mejor**; dirige el presupuesto de búsqueda.

#### Evaluación terminal

Si la posición alcanzada es terminal, no hace falta consultar la red: se utiliza el resultado real de la partida desde la perspectiva apropiada (victoria \(+1\), empate \(0\), derrota \(-1\)).

#### Retropropagación (*backup*)

Al volver de la hoja hacia la raíz se actualizan las aristas recorridas:

\[
N(s,a)\leftarrow N(s,a)+1,\qquad
W(s,a)\leftarrow W(s,a)+v,\qquad
Q(s,a)\leftarrow\frac{W(s,a)}{N(s,a)}.
\]

En un juego de suma cero, **al cambiar de jugador se invierte el signo del valor**: \(v\leftarrow-v\). La convención debe fijarse claramente; en las fórmulas de selección, \(Q(s,a)\) debe expresar la expectativa desde la perspectiva del jugador que elige en \(s\).

### Elección del movimiento efectivo

Se realizan simulaciones hasta agotar un presupuesto, generalmente de nodos o tiempo. **Durante la búsqueda se maximiza \(Q+U\); al decidir el movimiento real normalmente se utilizan las visitas**, no el máximo \(Q+U\):

\[
a_{\mathrm{juego}}=\arg\max_a N(s_0,a).
\]

En autojuego o entrenamiento puede aplicarse muestreo con temperatura \(\tau\):

\[
\pi(a\mid s_0)=\frac{N(s_0,a)^{1/\tau}}{\sum_b N(s_0,b)^{1/\tau}}.
\]

La distribución de visitas \(\pi\) puede constituir la señal de entrenamiento para mejorar la política neuronal.

### Estructura de datos orientativa

```python
class Edge:
    move: str       # jugada, por ejemplo UCI
    prior: float    # P(s,a)
    visits: int     # N(s,a)
    value_sum: float  # W(s,a), desde el punto de vista del jugador en s
    child: "Node | None"

    @property
    def q(self):
        return self.value_sum / self.visits if self.visits else 0.0

class Node:
    position: object
    expanded: bool
    edges: list[Edge]
    # Opcional: estado terminal, transposiciones, historial y metadatos
```

### Pseudocódigo resumido

```text
repetir mientras quede presupuesto:
    nodo = raíz
    recorrido = []
    mientras nodo esté expandido y no sea terminal:
        arista = argmax(Q + U)
        recorrido.agregar(arista)
        nodo = hijo(arista)
    si nodo es terminal:
        v = resultado_terminal(nodo)
    si no:
        P, v = red_neuronal(nodo.posición)
        crear_aristas_legales(nodo, normalizar(P))
    para cada arista del recorrido, en orden inverso:
        v = -v   # invertir perspectiva entre jugadores
        actualizar N, W y Q de la arista con v
jugar la acción con mayor cantidad de visitas en la raíz
```

### Rol efectivo de la red neuronal

La red cumple **dos funciones distintas y complementarias**. La política \(P\) decide dónde conviene concentrar la exploración; el valor \(v\) aproxima la calidad de las posiciones descubiertas. MCTS acumula evidencia mediante visitas y promedios \(Q\), por lo que sus decisiones no son una simple lectura directa de la red. Una red sin entrenamiento puede guiar mal la búsqueda, y aumentar simulaciones no garantiza por sí solo buena calidad ajedrecística.

### Diferencia respecto de Sargon Classic/Sargon Plus

Sargon Plus, con alfa-beta y *quiescence*, explora variantes hasta cierta profundidad y solicita valoraciones de posiciones al evaluador. MCTS/PUCT selecciona dinámicamente qué ramas visitar usando \(P\), \(N\) y \(Q\), incorpora el valor neuronal en hojas y elige normalmente la jugada por visitas. Si se usa una red LC0 como evaluador de Sargon Plus, se puede aprovechar su **valor** sin que el player se transforme automáticamente en MCTS: la estrategia de exploración sigue siendo alfa-beta.



### Codificación AlphaZero de acciones legales

El catálogo de acciones implementado por `az_core.py` tiene **64 × 73 = 4672** índices. Se toma la casilla inicial (64 opciones) y uno de 73 planos: 56 desplazamientos direccionales (8 direcciones × distancias 1..7), 8 saltos de caballo y 9 promociones menores (3 piezas × 3 desplazamientos). Las promociones a dama se cubren mediante el movimiento direccional correspondiente. Antes de normalizar probabilidades, se enmascaran todas las acciones ilegales. `action_id(board,move)` es una operación de codificación, no de valoración.

### Historial, caché y límites del árbol

El estado de una posición contiene las piezas y datos de legalidad, pero algunas propiedades (repetición, contexto de jugadas, planes de red dependientes del historial) requieren secuencia de posiciones. Las etiquetas LC0 distinguen historial disponible e incompleto. La **caché de inferencias** puede compartirse durante una partida y se libera al concluirla; no se persisten entre partidas las estadísticas de árbol `N/W/Q` ni se mezclan evaluaciones obtenidas mediante redes de distintas identidades.

## Players Stockfish, Leela y Random

Estos players en realidad no operan con el supuesto arquitectónico de 
obtener la evaluación de las jugadas desde un módulo evaluador.
*StockfishPlayer* delega selección y evaluación al ejecutable *Stockfish* externo y aplica límites `depth`, `nodes`, `movetime`, `elo`, `stockfish-threads`, `stockfish-hash`, `timeout` y `engine-path`, según perfil. Su único evaluador admisible es `null`. 
*lc0* (leela chess zero)  delega selección y evaluación al ejecutable *lc0.exe* externo y aplica límites `depth`, `nodes`, `movetime`, `elo`, `stockfish-threads`, `stockfish-hash`, `timeout` y `engine-path`, según perfil. Su único evaluador admisible es `null`. 
Random obtiene una jugada legal sin optimización y la juega; puede utilizar `null` como evaluador y no interpreta `depth/qdepth` como búsqueda estratégica. Su objetivo es confrontar la efectividad última de una estrategia respecto a como se comporta comparada con un jugador al azar.

# Evaluadores

## API (contrato)

El evaluador responde un escalar en centipawns desde la perspectiva blanca, salvo contratos de entrenamiento que expresamente definan objetivos normalizados. $e(s)>0$ favorece blancas; $e(s)<0$ favorece negras. Jaque mate, ahogado, repetición y cincuenta movimientos pertenecen a la lógica de juego y pueden requerir historial no contenido en el vector de características; no se deben interpretar como una simple inferencia estática.

## Evaluador *Classic*

El evaluador clásico es la implementación interna, con la mejor fidelidad
histórica posible, del algoritmo *Sargón* original. Utiliza una función determinista basada en características ajedrecísticas definidas por el código del proyecto y que no evoluciona mediante entrenamiento. 
Permite construir un baseline reproducible y etiquetar posiciones sin búsqueda principal. No debe confundirse la evaluación estática con las jugadas elegidas por Sargon usando esa evaluación.

## Evaluador SargonPlus

Este evaluador utiliza una red *NNUE* nativa del proyecto (formato npz) que captura las  características posicionales mediante una longitud lógica 781. En la arquitectura inicial se emplea una red densa $781\to64\to1$ con ReLU intermedia y un término de corrección de halfmove. Para un vector $x$, una formulación representativa es: $$h=\operatorname{ReLU}(W_1x+b_1),\qquad z=W_2h+b_2,\qquad e_{\mathrm{cp}}=400z+g_{\mathrm{hm}}(s).$$ 
La función concreta de halfmove y los nombres de tensores deben verificarse en el checkpoint/código; la fórmula describe el API funcional y no presupone una clave interna de archivo no verificada. El formato guardado `.npz`  conserva dimensiones, pesos, sesgos y metadatos suficientes para comprobar compatibilidad para agregar integridad al uso de la misma.

## Evaluador Cerebrum 1.1

Dado que el alcance del proyecto intenta evaluar tanto implementaciones de redes neurales diferentes así como diferentes estrategias para usarlas uno
de los objetivos ha sido poder integrar redes neuranales creadas y
entrenadas bajo otras arquitecturas. Esto es importante porque en ocasiones
ciertas arquitecturas de redes representan un costo de entrenamiento 
vastamente superior al disponible en éste proyecto, aún así se intenta
capturar la generalización estratégica del juego que proponen mediante 
algoritmos y enfoques que si son parte del proyecto.
Cerebrum 1.1 consume una representación posicional propia y expone evaluación ordinaria y, cuando existe estado anterior compatible, evaluación incremental. La interfaz especializada admite `evaluate_with_hint(incremental=True, previous_state=...)` o su equivalente interno; la factory decide el evaluador. La inferencia incremental actualiza acumuladores de características a partir de la transición padre–hijo en lugar de reconstruir todo el estado; *no* cambia intencionalmente la semántica del puntaje. No se debe suponer compatibilidad binaria entre redes Cerebrum y NPZ.

## Evaluador Stockfish

*Stockfish* es claramente la referencia en materia de motores de ajedrez,
su impresionante plataforma de tratamiento y la enorme cantidad de 
heurísticas que aplica lo hacen, para un dado nivel de competencia ser muy
cercano a imbatible. No se experimentó, como en el caso de Cerebrum 1.1, con intentar integrar la red que utiliza Stockfish. Por un lado porque la red probablemente sea poco valiosa sin las heurísticas aplicadas para determinar movidas y por el otro porque desarrollar un player se escapa de la escala y el propósito del proyecto.
Pero Stockfish tiene modalidades que permiten utilizarlo como evaluador de jugadas, y en tal sentido es posible alimentarlo con una determinada configuración de tablero y mediante un protocolo UCI utilizarlo como
como evaluador externo para entregar la evaluación posicional de su NNUE sin entregar las candidatas de su algoritmo de búsqueda. Ese uso se distingue estrictamente implementar un player, pues el valor posicional obtenido se puede armonizar con las necesidades de los otros players disponibles (por ejemplo Sargon) o utilizar como una "*opinión*"de entrenamiento. Los valores terminales, la salida textual del motor y la perspectiva blanca requieren normalización, parsing apropiado y tratamiento separado de estados en jaque; pero su resultado se compatibiliza mediante un *wrapper* para que pueda ser
consumido mediante un API compatible por el resto de los players de la plataforma, excepto restricciones de API específicamente documentadas.

## Evaluador Leela Chess Zero (lc0)

Al igual que en el caso de Stockfish el motor implementado por el proyecto *Leela Chess (lc)" aporta una plataforma muy robusta basada en el uso de redes neuronales convolucionales de alta capacidad junto con la implementación de algoritmos tipo *Monte Carlo Search Tree (MCST)* , sin embargo y a diferencia del caso de Stockfish se implementa un player propio utilizando el algoritmo MCST puesto que representa un potencial de juego muy grande que es importante explorar. Aun así el entrenamiento de las redes que utiliza lc0 implica ejercitar millones de partidas (cientos de millones de movimientos) lo que escapa en términos de capacidad de cómputo a los disponibles por el proyecto. Sin embargo al ser las redes públicas en su 
estructura y siendo disponible su matriz de coeficientes es natural el interés para poder reusarlas, cosa que logra éste evaluador. El mismo puede proveer del valor posicional no solo al player Sargon/SargonPlus sino también a un jugador con algoritmo MCST llamado *AlphaZero* en honor al legendario programa que lo implementó por primera vez.
Desde el punto de vista de la arquitectura el evaluador provee la doble salida $f(V_i,\{P_i\})$ para poder evaluar el valor posicional y las preferencias de política a-priori que utiliza el algoritmo, este evaluador lo pueden utilizar tanto el player *AlphaZero* como *Sargon/Sargon+*. 



### Bindings Python y motor UCI de LCZero

La integración contempla dos rutas principales:

**Bindings Python (`lczero_bindings`).** Sargon-NNUE llama una biblioteca nativa desde Python. Permite obtener política y valor directamente, con configuración de backend (por ejemplo Eigen/CPU u ONNX Runtime + DirectML/GPU) según el entorno construido. Evita utilizar el texto UCI como formato de intercambio de cada inferencia y facilita construir lotes de posiciones.

**`lc0.exe` por UCI.** El ejecutable opera como motor independiente y puede seleccionarse como player, o emplearse para etiquetar posiciones con parámetros específicos de inferencia/análisis. Las opciones del backend, hilos, pesos, nodos y política de historial se transmiten al adaptador correspondiente; en el modo player completo LC0 selecciona directamente sus jugadas.

### 7.1 Redes LC0 utilizadas

| Modelo | Caracterización | Uso |
|---|---|---|
| `t1-256x10-distilled-swa-2432500.pb.gz` | Familia T1 con **256 filtros y 10 bloques residuales** | Evaluación y etiquetado con LC0 |
| `tinyGyal` | Red LC0 compacta, **2 bloques × 16 filtros** | Política/valor en experimentos compactos |
| `picoGyal` | Red destilada, **1 bloque × 8 filtros** | Experimentación y compatibilidad de inferencia LC0 |

Los archivos `.pb.gz` almacenan redes LC0 serializadas/comprimidas. El identificador de arquitectura, planos de entrada y cabezales de salida deben coincidir con el runtime. **No debe inferirse que dos redes con diferente arquitectura tienen parámetros intercambiables**: incluso si ambas usan el mismo protocolo UCI, sus matrices, convoluciones y normalizaciones no son las mismas.

### 7.2 Arquitectura residual: operación matemática

Para entrada con planos espaciales `X ∈ R^{C×8×8}`, un tronco convolucional aplica transformaciones tipo `H = φ(BN(Conv(X)))`. Un bloque residual usa de forma esquemática `H_{k+1}=φ(H_k + F_k(H_k))`, con `F_k` formado por convoluciones y operaciones de activación/normalización. Un cabezal de política produce logits `z_a`, transformados en probabilidades legales por `P(a|s)=exp(z_a)/Σ_{b∈A(s)}exp(z_b)`; un cabezal de valor puede emitir escalar o WDL. En este último caso, `p_i=exp(z_i)/Σ_j exp(z_j)` para `i∈{W,D,L}`. Las dimensiones exactas de cabezales y el número de planos activos se toman del archivo de pesos y del backend de LC0 correspondiente.

### 7.3 CPU y GPU

En Windows se contemplan inferencias mediante **CPU/Eigen** y **GPU vía ONNX Runtime/DirectML** cuando las bindings se construyen con el backend apropiado. Los parámetros de ejecución incluyen selección de backend y opciones de dispositivo, tamaño de lote, hilos y pesos. La GPU acelera convoluciones y lotes densos; para cargas de una sola posición, el coste de transferencia y preparación puede dominar. El entrenamiento de redes NPZ/PyTorch utiliza el dispositivo disponible del framework, incluido `xpu` donde está habilitado.

### Redes LC0 utilizadas

| Modelo | Caracterización | Uso |
|---|---|---|
| `t1-256x10-distilled-swa-2432500.pb.gz` | Familia T1 con **256 filtros y 10 bloques residuales** | Evaluación y etiquetado con LC0 |
| `tinyGyal` | Red LC0 compacta, **2 bloques × 16 filtros** | Política/valor en experimentos compactos |
| `picoGyal` | Red destilada, **1 bloque × 8 filtros** | Experimentación y compatibilidad de inferencia LC0 |

Los archivos `.pb.gz` almacenan redes LC0 serializadas/comprimidas. El identificador de arquitectura, planos de entrada y cabezales de salida deben coincidir con el runtime. **No debe inferirse que dos redes con diferente arquitectura tienen parámetros intercambiables**: incluso si ambas usan el mismo protocolo UCI, sus matrices, convoluciones y normalizaciones no son las mismas.

### Arquitectura matemática de redes LC0

Para entrada con planos espaciales `X ∈ R^{C×8×8}`, un tronco convolucional aplica transformaciones tipo `H = φ(BN(Conv(X)))`. Un bloque residual usa de forma esquemática `H_{k+1}=φ(H_k + F_k(H_k))`, con `F_k` formado por convoluciones y operaciones de activación/normalización. Un cabezal de política produce logits `z_a`, transformados en probabilidades legales por `P(a|s)=exp(z_a)/Σ_{b∈A(s)}exp(z_b)`; un cabezal de valor puede emitir escalar o WDL. En este último caso, `p_i=exp(z_i)/Σ_j exp(z_j)` para `i∈{W,D,L}`. Las dimensiones exactas de cabezales y el número de planos activos se toman del archivo de pesos y del backend de LC0 correspondiente.

### CPU, GPU y backends de inferencia

En Windows se contemplan inferencias mediante **CPU/Eigen** y **GPU vía ONNX Runtime/DirectML** cuando las bindings se construyen con el backend apropiado. Los parámetros de ejecución incluyen selección de backend y opciones de dispositivo, tamaño de lote, hilos y pesos. La GPU acelera convoluciones y lotes densos; para cargas de una sola posición, el coste de transferencia y preparación puede dominar. El entrenamiento de redes NPZ/PyTorch utiliza el dispositivo disponible del framework, incluido `xpu` donde está habilitado.

## Evaluador Null

Indica que el player no requiere evaluador externo. Es mandatorio semánticamente para los players Stockfish, lc0 y  Random.



### Catálogo ampliado de evaluadores

- `classic`: evaluación heurística de Sargón, sin red neuronal.
- `npz`: red local con parámetros serializados por NumPy.
- `stockfish`: análisis escalar obtenido de Stockfish cuando se utiliza como evaluador de otro player.
- `lc0`: inferencia neuronal LCZero con probabilidades de política y valor/WDL, según el adaptador y la arquitectura de la red.
- `tinygyal`: acceso especializado a redes compactas LC0 compatibles con el backend configurado.
- `grumpy`: evaluación mediante pesos de red Grumpy, cuando se usa como evaluador independiente.
- `cerebrum-1.1`, `cerebrum-2`/`cerebrum`: importadores de redes Cerebrum.
- `null`: evaluador nulo para programas externos con motor de búsqueda y evaluación autónomos.

**Perspectiva de los valores.** Una utilidad de preparación puede almacenar valores en `[0,1]`, un evaluador de búsqueda puede producir centipeones y LC0 puede informar WDL. No son magnitudes intercambiables sin una transformación explícita. Una conversión habitual es `v = P(win) - P(loss)` desde la perspectiva del jugador al turno; la esperanza de puntuación es `P(win) + 0.5 P(draw)`.

# Optimizaciones Sargón Plus

El player *Sargon Plus* se diferencia del *Sargon* clásico por la
disponibilidad de varias heurísticas adicionales de evaluación (*boost*) y gestión de performance (*turbo*), implementa además el algoritmo de *quiescence* en la exploración de jugadas.

## Quiescence

Esta opción de performance se activa con el argumento (*--qdepth*) y en
evaluaciones preliminares aporta un margen de mejora apreciable al 
algoritmo Sargon nativo.
Se trata de una extensión selectiva del algoritmo de búsqueda alfa-beta que, al alcanzar la profundidad nominal (--depth), continúa explorando jugadas tácticamente relevantes hasta alcanzar una posición relativamente estable.
Su objetivo es evitar el *efecto horizonte*, por el cual el motor evalúa una posición justo antes de una captura, recaptura u otro acontecimiento táctico importante, produciendo una valoración engañosa.
En Sargon Plus:
- --qdepth 0: desactiva la búsqueda de quiescence.
- --qdepth N: permite explorar hasta N niveles adicionales de movimientos tácticos.
- Se priorizan capturas, recapturas y, según la implementación, otras jugadas forzadas.
- Las posiciones alcanzadas se valoran mediante el evaluador configurado (NNUE, LC0, Stockfish, etc.).
Por ejemplo con --depth 3 --qdepth 2, Sargon Plus realiza una búsqueda principal de 3 plies y puede extender determinadas variantes tácticas hasta 5 plies.
Como beneficio se encontró experimentalmente que mejora la estabilidad de la evaluación táctica sin explorar exhaustivamente todas las jugadas de los niveles adicionales.
El costo es incrementar el número de nodos evaluados y el tiempo de búsqueda; el incremento depende de la cantidad de movimientos tácticos disponibles.
En resumen, el modo Quiescence evita que Sargon Plus detenga el análisis en medio de una secuencia táctica que todavía no se ha resuelto. En la práctica el algoritmo ha probado mejorar el nivel promedio del player cuando está activado (qdepth>0).

## Máscara BOOST y activación

BOOST se interpreta como una máscara $B\in[0,2^{16}-1]$ de bits independientes, no como nivel ordinal. La optimización $i$ se activa cuando $(B\ \&\ 2^i)\neq 0$. La composición usa OR bit a bit; por ejemplo History más PVS equivale a `0x0001 | 0x0004 = 0x0005`. No se garantiza aditividad de sus efectos competitivos.

|   Bit | Hexadecimal | Algoritmo                                             |
|------:|:------------|:------------------------------------------------------|
|     0 | `0x0001`    | History Heuristic                                     |
|     1 | `0x0002`    | Killer Moves                                          |
|     2 | `0x0004`    | Principal Variation Search / NegaScout                |
|     3 | `0x0008`    | Transposition Table con bounds                        |
|     4 | `0x0010`    | Hash Move First                                       |
|     5 | `0x0020`    | SEE Pruning                                           |
|     6 | `0x0040`    | Aspiration Windows                                    |
|     7 | `0x0080`    | Late Move Reductions                                  |
|     8 | `0x0100`    | Futility / Reverse Futility                           |
|     9 | `0x0200`    | Delta Pruning en quiescence                           |
|    10 | `0x0400`    | Razoring                                              |
|    11 | `0x0800`    | Null Move Pruning                                     |
|    12 | `0x1000`    | ProbCut / MultiCut                                    |
|    13 | `0x2000`    | Evaluación incremental cuando el evaluador lo soporta |
| 14–15 | `0xC000`    | Reservados                                            |

No todas las optimizaciones tienen un efecto neto positivo, y en determinadas partidas distintos mecanismos pueden actuar como detractor de otros. La variedad de algoritmos de optimización tienen un efecto mayormente de experimentación.

### History Heuristic y Killer Moves

History asigna a una jugada tranquila $m$ una prioridad acumulada $H[m]$, incrementada cuando produce cortes beta. Un incremento típico es $\Delta H\propto d^2$; su papel es ordenar candidatas, no eliminar alternativas. Killer conserva jugadas tranquilas que anteriormente produjeron cortes a la misma profundidad o ply y las promueve en el ordenamiento. Una búsqueda alfa–beta exacta debería preservar el valor minimax aunque cambie el orden; las jugadas elegidas pueden diferir si existe empate o búsqueda selectiva.

### PVS y búsqueda de ventanas

Después de examinar la primera candidata con ventana completa $[\alpha,\beta]$, PVS prueba otras jugadas con una ventana de ancho mínimo $[\alpha,\alpha+\epsilon]$, donde $\epsilon$ es la granularidad de puntuación. Si el resultado supera $\alpha$ sin alcanzar el corte beta, reanaliza con ventana completa. La re-búsqueda no es opcional si el resultado de ventana estrecha es un límite insuficiente.

### TT Bounds y Hash Move First

La tabla indexa una clave Zobrist o equivalente, conserva profundidad, jugada y tipo de bound. Una entrada EXACT puede devolver el valor bajo condiciones de profundidad compatibles; LOWER y UPPER actualizan respectivamente los límites inferior y superior. El uso incorrecto de bounds puede cambiar la decisión. Hash Move First prioriza la jugada almacenada por TT, tras comprobar legalidad, para elevar la probabilidad de cortes tempranos.

### SEE y poda por intercambios

SEE estima el balance de un intercambio sobre una casilla mediante capturas y recapturas. Conceptualmente, para ganancias alternadas $g_k$, la secuencia satisface una recurrencia minimax local; podar una candidata por SEE negativo puede ahorrar nodos, pero no equivale a demostrar que la jugada sea globalmente mala (amenazas, jaques o tácticas intermedias pueden prevalecer).

### Aspiration Windows

Cuando existe una evaluación anterior $v_{d-1}$, la nueva búsqueda puede usar $[v_{d-1}-\delta,\,v_{d-1}+\delta]$. Si se obtiene *fail-low* o *fail-high*, se ensancha la ventana y se vuelve a buscar hasta disponer de un resultado utilizable. La elección de $\delta$ afecta costo y frecuencia de re-búsqueda.

### Late Move Reductions

LMR reduce profundidad para jugadas tardías consideradas menos críticas: $d'=d-1-r(d,i)$, con $r\geq 1$, aplicado solo si se cumplen guardrails tácticos, de profundidad y orden $i$. Si la búsqueda reducida contradice la ventana se puede requerir re-búsqueda a profundidad completa. La relación exacta $r(d,i)$ y umbrales se define en código, no en el contrato externo.

### Futility y Reverse Futility

Futility contrasta evaluación estática $e(s)$ y margen $M(d)$ con el límite alfa: $e(s)+M(d)\leq\alpha$ puede indicar que ciertas jugadas tranquilas no alcanzarán el límite. Reverse Futility compara $e(s)-M(d)\geq\beta$ para posibles cortes por límite inferior. Son heurísticas selectivas, no demostraciones exactas.

### Delta pruning en quiescence

Con evaluación $e(s)$, máxima ganancia material esperada $G(m)$ y margen $\Delta$, se puede omitir una captura si $e(s)+G(m)+\Delta <\alpha$, salvo excepciones tácticas necesarias. En posiciones de jaque deben contemplarse evasiones legales; stand-pat no es una alternativa legal a responder al jaque.

### Razoring

Prueba si un nodo de profundidad reducida, con $e(s)+R(d)$ claramente bajo alfa, puede resolverse por quiescence en lugar de búsqueda completa. La prueba debe respetar posiciones tácticamente peligrosas y las condiciones del motor.

### Null Move Pruning

Realiza una búsqueda de prueba pasando turno bajo condiciones restringidas. Si $-V(s_{null},d-R-1,-\beta,-\beta+\epsilon)\geq\beta$, considera un corte beta. Se debe proteger frente a posiciones de zugzwang, jaque y materiales reducidos; el hecho de que la máscara esté disponible no demuestra que el corte sea ajedrecísticamente seguro.

### ProbCut y MultiCut

ProbCut usa una búsqueda reducida y un umbral probabilístico sobre el bound beta para intentar un corte temprano, por ejemplo $V_{reducida}\geq\beta+\sigma$. MultiCut examina un subconjunto de jugadas a profundidad reducida y corta si suficientes producen fail-high. Son aproximaciones de selectividad con parámetros empíricos.

### Inferencia incremental

El bit `0x2000` solicita al evaluador aprovechar el estado anterior. Si éste implementa el contrato incremental (Cerebrum 1.1), puede evitar recomputación; NPZ y CLASSIC permanecen en evaluación convencional. Debe conservarse equivalencia de resultados dentro de tolerancias numéricas apropiadas.

### Alcance matemático y verificación

Estas ecuaciones describen la familia de algoritmos y sus desigualdades esenciales. No constituyen una especificación exacta de constantes ni umbrales locales: para un diagnóstico reproducible deben cotejarse con `players/sargon_plus.py` instalado. Activar un bit no prueba que el mecanismo haya encontrado oportunidades; los contadores de auditoría distinguen cobertura, intervención y efecto observado.

## Gestión adaptativa de performance (TURBO)

Esto expresa un conjunto de heurísticas tomando el proceso para la 
decisión de la movida como restringido por un conjunto de supuestos de
tiempo máximo y profundidad máxima de análisis.
En tal sentido se utilizan excedentes de tiempo para profundizar el análisis o deficit de tiempo para restringirlos.
TURBO es independiente de BOOST. Se habilita mediante `0x01` (Adaptive Full Width), `0x02` (Adaptive Candidate Selection) y `0x03` (ambos). Los modos gestionan la decisión de iniciar el siguiente nivel, no reemplazan el evaluador ni el resultado terminal.

### Modelo de crecimiento

Sea $t_d$ el tiempo observado para completar profundidad $d$. Se estima un factor $\hat g_d=t_d/t_{d-1}$ y el costo del próximo nivel $\hat t_{d+1}=t_d\hat g_d$, ajustable por el controlador. La decisión de iniciar un nivel considera el tiempo restante $T_{rem}$ y un margen de seguridad $\eta$: $$\hat t_{d+1}\leq\eta T_{rem}.$$ El factor observado no debe tratarse como constante teórica: ramificación, ordenamiento y quiescence producen alta variabilidad. Datos censurados (nivel incompleto por timeout) no equivalen a una medición de nivel terminado.

### Adaptive Full Width

Evalúa si una búsqueda completa de todas las candidatas raíz es admisible bajo el presupuesto. Si no lo es, no inicia un nivel que previsiblemente no podrá completar y conserva la última búsqueda terminada. La respuesta final nunca debería proceder de un nivel parcial cuya comparación de candidatas no sea válida.

### Adaptive Candidate Selection

Puede estimar un subconjunto $K$ de las $N$ jugadas raíz. La fracción $f=K/N$ controla trabajo y riesgo de exclusión. Los guardrails evitan casos degenerados como $K=1$ cuando no habría comparación útil o no existe presupuesto para un solo candidato. Para posiciones similares, la decisión de reducir candidatos debe preservar la trazabilidad del conjunto seleccionado y la cobertura del nivel anterior.

### Reglas de fallback y criterios de seguridad

Si un nivel es interrumpido, se devuelve el mejor resultado del último nivel *completo*. Si la proyección excede tiempo restante se registra el descarte de nivel; si ninguna candidatura puede completarse se detiene. El costo de ordenar y auditar no debe ocultarse bajo el tiempo de búsqueda. Los límites deben tener prioridad sobre heurísticas de avance.

### Interacciones con BOOST

BOOST modifica el costo efectivo $t_d$ y la ramificación observada, lo que cambia la estimación de TURBO. Una aceleración de BOOST no implica mejor juego si el nivel completado o conjunto de candidatas cambia. La fuerza se evalúa con partidas; el costo con medidas de latencia/nodos; y las decisiones de TURBO con eventos de presupuesto, intentos y fallback.

# Integración de Stockfish

## Stockfish como evaluador

En esta modalidad los player Sargon, Sargon-Plus o Cerebrum, según compatibilidad de implementación, gobiernan la selección de jugadas y piden a Stockfish un valor posicional de una posición. No debe asumirse que el motor Stockfish entrega su árbol de candidatos como parte de ese API. La salida se normaliza a centipawns con perspectiva blanca, se distingue evaluación NNUE de búsqueda principal y se controlan terminales. El wrapper puede gestionar proceso persistente y cache LRU cuando está configurado.

## Stockfish como player

Stockfish decide internamente la mejor jugada con sus métodos propios; por el API utilizado, en éste caso el evaluador externo es `null` puesto que no es posible controlar el funcionamiento de stockfish en forma externa para que provea solo la función de player. Los controles del perfil incluyen `engine-path`, `depth`, `nodes`, `movetime`, `elo`, `stockfish-threads`, `stockfish-hash` y `timeout`. La omisión de evaluator se interpreta como null; la indicación explícita de otro evaluador es incompatible.

### Performance, diagnóstico y límites de comparación

La velocidad y fuerza de Stockfish como player no son comparables directamente con un player propio al que Stockfish sólo ofrece evaluación: el primero controla orden, poda y red interna; el segundo retiene la política de Sargon. Existen riesgos específicos en cargar redes NNUE, extraer *Final evaluation*, interpretar `readyok`, distinguir errores de `bestmove`, y terminar procesos. Los parámetros restrictivos, como `nodes=1`, pueden reducir drásticamente la fuerza y deben registrarse antes de interpretar cualquier resultado. La auditoría conserva respuesta UCI y tiempo interno por separado.

# Integración de Leela Chess Zero 

## Leela Chess Zero como Player
Similar al caso de Stockfish, en éste caso se entrega el cuadro posicional a lc0.exe (mediante su interfaz UCI) y se obtiee la jugada que recomienda. Puesto que el proceso de inferencia es completamente realizado dentro de la llamada el evaluador en éste caso es *null*.


# Entrenamiento y preparación de redes

Se puede entrenar y producir redes propias de tipo NNUE (formato npz) para lo cual se dispone de una cadena de construcción para almacenar jugadas históricas, realizar muestras, etiquetar valores objetivos y realizar el entrenamiento.
El entrenamiento se realiza con movidas aisladas seleccionadas al azar.
Al comenzar el entrenamiento,  un porcentaje de las movidas es separada 
y reservada para validación, no usandola en el entrenamiento mismo.

## Cadena de entrenamiento

    PGN --> sargon_prepare --> SQLite .pb
                 |             |       |
           etiquetado           |    sargon_audit
           CLASSIC/Stockfish    |
                               v
                          sargon_train
                           NumPy/PyTorch
                               |
                         checkpoint .npz
                               |
                    sargon_brainmaker / UCI
                               |
                      MATCH / RALLY / JUDGE

## SARGON PREPARE y las etiquetas

El proceso lee PGN, extrae posiciones, controla errores de partida y construye una base SQLite `.pb`. Puede remuestrear partidas completas, calcular etiquetas CLASSIC estáticas, solicitar WDL de Stockfish o conservar resultados PGN. La unidad de partición para prevenir fuga entre train/validation es la partida, no la posición individual.

| Argumento    | Función                                                           |
|:-------------|:------------------------------------------------------------------|
| `--dir GLOB`  | Archivos PGN de entrada; requerido en modo de adquisición.        |
| `--input`     | Base existente para operaciones de remuestreo, cuando aplica.     |
| `--out`       | Destino `.pb`; obligatorio para crear una base persistente.       |
| `--resample`  | Remuestreo desde base existente, conservando unidades de partida. |
| `--classic`   | Etiquetado estático mediante CLASSIC.                             |
| `--stockfish` | Etiquetado externo Stockfish, sujeto a proceso y parámetros.      |



### Preparación, etiquetado y fuentes de valor

El flujo de datos separa **importar**, **muestrear**, **etiquetar** y **analizar**:

```text
PGN → posiciones PB → selección/muestreo → etiquetas
     → validación del corpus → entrenamiento → checkpoints
```

`data/pb/<nombre>.pb` es la base preparada; una muestra suele nombrarse `data/pb/<nombre>_sample.pb`. Se utilizan etiquetas provenientes de resultado de partida, evaluador Sargón clásico, Stockfish, LC0 bindings, LC0 UCI y exploración MCTS. Cada fuente debe preservar su identidad: actualizar una etiqueta no equivale a sobrescribir indiscriminadamente las anteriores.

La codificación de posiciones clásica usa **781 características**: `64×12=768` indicadores de pieza/casilla, 4 derechos de enroque, 8 posibilidades de columna de al paso y 1 indicador de turno. Para AlphaZero se representa además la política sobre las 4672 acciones posibles y se registra la suficiencia del historial.

**Resultado y valor.** El resultado de una partida aporta una etiqueta final, pero la evaluación durante una partida no es necesariamente idéntica a ese resultado. La mezcla de fuentes se formula, para etiquetas normalizadas a una misma perspectiva, como:

\[
y=\frac{w_s y_{stockfish}+w_c y_{classic}+w_r y_{result}}{w_s+w_c+w_r},
\qquad w_i\ge0.
\]

Las etiquetas faltantes requieren política explícita de exclusión o renormalización; no se reemplazan implícitamente por cero. Para construir políticas iniciales, pueden utilizarse frecuencias empíricas de acciones observadas sobre posiciones comparables, normalizadas sobre movimientos legales.

### 8.1 Scripts operativos

Los scripts de `scripts/` envuelven comandos Python y parámetros de los pipelines. Entre los lanzadores disponibles están `sargon_prepare.ps1`, `run_pipeline_prepare.ps1`, `run_pipeline_train.ps1`, `sargon_train.ps1`, `run_prepare_lc0_secondary.ps1` y `run_lc0_prepare.ps1`. El modo repetible separa explícitamente preparación y entrenamiento; no exige repetir importación y etiquetado cada vez que se entrena de nuevo.

Ejemplos de puntos de entrada Python (la configuración detallada se obtiene mediante `--help` del módulo correspondiente):

```powershell
python -m sargon_nnue.sargon_prepare --help
python -m sargon_nnue.sargon_train --help
python -m sargon_nnue.sargon_listen --help
python -m sargon_nnue.sargon_match --help
```

Las opciones especializadas para etiquetado LC0-UCI incluyen `--lc0-uci-path`, `--lc0-uci-nodes`, `--lc0-uci-threads`, `--lc0-backend`, `--lc0-backend-options`, `--lc0-weights` y `--lc0-history` según el subcomando utilizado.

### Lanzadores y puntos de entrada de preparación

Los scripts de `scripts/` envuelven comandos Python y parámetros de los pipelines. Entre los lanzadores disponibles están `sargon_prepare.ps1`, `run_pipeline_prepare.ps1`, `run_pipeline_train.ps1`, `sargon_train.ps1`, `run_prepare_lc0_secondary.ps1` y `run_lc0_prepare.ps1`. El modo repetible separa explícitamente preparación y entrenamiento; no exige repetir importación y etiquetado cada vez que se entrena de nuevo.

Ejemplos de puntos de entrada Python (la configuración detallada se obtiene mediante `--help` del módulo correspondiente):

```powershell
python -m sargon_nnue.sargon_prepare --help
python -m sargon_nnue.sargon_train --help
python -m sargon_nnue.sargon_listen --help
python -m sargon_nnue.sargon_match --help
```

Las opciones especializadas para etiquetado LC0-UCI incluyen `--lc0-uci-path`, `--lc0-uci-nodes`, `--lc0-uci-threads`, `--lc0-backend`, `--lc0-backend-options`, `--lc0-weights` y `--lc0-history` según el subcomando utilizado.

## Heurísticas de generación de señales

Los objetivos de aprendizaje no son intercambiables: (i) resultado de partida $R\in\{0,\frac12,1\}$, (ii) WDL del maestro $(W,D,L)$, (iii) centipawns estáticos CLASSIC, (iv) otras etiquetas cuando estén disponibles. Para WDL con unidades milésimas se obtiene una expectativa blanca $S=(W+D/2)/1000$. Para CLASSIC se usa el valor normalizado $C/400$ en la arquitectura documentada. Una mezcla supervisada genérica es: $$L(\theta)=\lambda_C\frac1N\sum_i(f_\theta(x_i)-C_i/400)^2+\lambda_S\frac1N\sum_i(f_\theta(x_i)-S_i)^2+\lambda_R L_R,$$ donde $\lambda$ sólo corresponde a objetivos habilitados. En la práctica no se deben mezclar magnitudes incompatibles sin normalizarlas explícitamente. La preparación permite filtrar etiquetas terminales de mate de la regresión estática y guardar procedencia. El remuestreo, la selección dispersa de movimientos, la ponderación por fase y la verificación de integridad deben interpretarse respecto de los argumentos reales del programa utilizado; no todos los filtros experimentales están garantizados en cada modo.

## Rol de PyTorch y backend NumPy

NumPy resuelve entrenamiento matricial CPU; PyTorch ofrece autograd, optimizadores, batch tensors y elección de dispositivo `cpu`, `cuda` o `xpu` si el entorno soporta la GPU. PyTorch no reemplaza el contrato de características ni resuelve por sí mismo una mala etiqueta. Entrenar en XPU obliga a validar tipos, operadores soportados y consistencia con checkpoints anteriores.

## SARGON TRAIN: argumentos y defaults

| Argumento               | Descripción                                                                                |
|:------------------------|:-------------------------------------------------------------------------------------------|
| `--input`                | Base .pb de entrenamiento                                                                  |
| `--nnuedir`              | Directorio de checkpoints .npz                                                             |
| `--epoch`                | Cantidad de épocas, predeterminado 10                                                      |
| `--validation`           | Porcentaje de partidas de validación, predeterminado 1                                     |
| `--stockfish`            | Habilitar supervisión de Stockfish                                                         |
| `--classic`              | Habilitar supervisión CLASSIC                                                              |
| `--weight-classic`       | Proporción de objetivo CLASSIC (0 a 1)                                                     |
| `--weight-stockfish`     | Proporción de objetivo Stockfish (0 a 1)                                                   |
| `--seed`                 | Semilla de partición y muestreo (42)                                                       |
| `--shuffle`              | Porcentaje de movimientos de TRAIN elegidos una vez; 100 por defecto, no altera validación |
| `--lr`                   | Tasa de aprendizaje                                                                        |
| `--optimizer`            | adam, sgd, adamw, rmsprop, adagrad, adadelta, adamax, nadam, radam, asgd, rprop            |
| `--batch-size`           | Tamaño de lote (64)                                                                        |
| `--network`              | Checkpoint inicial .npz opcional                                                           |
| `--quick`                | Prueba de humo reducida; solamente backend PyTorch                                         |
| `--pytorch`              | Usar PyTorch; sin esta bandera se selecciona NumPy                                         |
| `--device`               | auto, cpu, cuda, xpu                                                                       |
| `--torch-dtype`          | float32 o float64                                                                          |
| `--weight-decay`         | Regularización del optimizador                                                             |
| `--torch-foreach`        | auto, on, off; off evita ciertas rutas foreach de XPU                                      |
| `--momentum`             | Parámetro SGD/RMSprop                                                                      |
| `--dampening`            | Amortiguación SGD                                                                          |
| `--nesterov`             | Nesterov SGD                                                                               |
| `--beta1`                | Primer beta de optimizadores tipo Adam                                                     |
| `--beta2`                | Segundo beta de optimizadores tipo Adam                                                    |
| `--eps`                  | Constante numérica                                                                         |
| `--alpha`                | Suavizado RMSprop                                                                          |
| `--centered`             | RMSprop centrado                                                                           |
| `--rho`                  | Adadelta rho                                                                               |
| `--lr-decay`             | Adagrad learning-rate decay                                                                |
| `--grad-clip`            | Límite norma del gradiente; 0 desactiva                                                    |
| `--scheduler`            | none, step, cosine, plateau                                                                |
| `--step-size`            | Intervalo de scheduler step                                                                |
| `--gamma`                | Factor de scheduler                                                                        |
| `--min-lr`               | Learning rate mínimo                                                                       |
| `--patience`             | Paciencia del scheduler o selección                                                        |
| `--early-stopping`       | Épocas para detención temprana; 0 desactiva                                                |
| `--min-delta`            | Mejora mínima considerada                                                                  |
| `--save-best`            | Guardar checkpoint mejor                                                                   |
| `--save-optimizer-state` | Guardar estado adicional del optimizador PyTorch                                           |
| `--version`              | Informar versión                                                                           |



### Entrenamiento de política y valor AlphaZero

Para una red dual, el objetivo puede reunir error de valor, entropía cruzada de política y regularización:

\[
L(\theta)=(v_\theta-z)^2-\pi^T\log p_\theta+\lambda\|\theta\|_2^2.
\]

`z` es el resultado o valor objetivo, `π` es la distribución objetivo sobre acciones (histórica o derivada de visitas MCTS) y `p_θ` es la predicción de política. Las acciones ilegales se enmascaran tanto al entrenar como al utilizar la red. Para evitar contaminación de validación entre posiciones de una misma partida, la partición se realiza por **partidas completas**, y el muestreo de posiciones se aplica posteriormente dentro del conjunto de entrenamiento.

Los programas `az_prepare.py`, `az_policy.py`, `az_seed_train.py`, `az_train.py`, `az_model.py` y `az_mcts_label.py` separan preparación, construcción de políticas, aprendizaje de semilla, entrenamiento de política/valor y generación de objetivos MCTS. En el aprendizaje por autojuego, la distribución de visitas proporciona la política objetivo, y el resultado de la partida proporciona crédito de valor a estados anteriores, con signo según el jugador.

## Partición, convergencia y métricas

El conjunto de validación se define por partida, para que posiciones vecinas del mismo juego no aparezcan en ambos subconjuntos. Una selección de entrenamiento por `--shuffle` se fija mediante semilla y se conserva en sucesivas épocas. Una época completa calcula MSE/RMSE, muestras válidas, pérdida de validación y, cuando procede, métricas de acierto de decisión o de aproximación WDL. La reducción de MSE mide fidelidad a un objetivo; no demuestra aumento de fuerza competitiva. La normalización de CLASSIC induce $MSE_{cp}=400^2 MSE_{norm}$ si las únicas diferencias son el factor lineal de escala. Para progreso estable deben controlarse fuga de partidas, mezcla de maestros, identidad del dataset y continuidad de checkpoint.

## Continuación e integridad del checkpoint

Un checkpoint existente debe cargarse y verificarse; un fallo de carga no autoriza reinicializar aleatoriamente los parámetros. Un checkpoint inexistente puede iniciar una red nueva si la operación lo pide explícitamente. El estado CPU/dispositivo de halfmove debe sincronizarse para evitar pérdida de aprendizaje entre sesiones. El entrenamiento conserva validación y exporta pesos con metadatos suficientes para reproducir arquitectura, escala y función objetivo.

# Herramientas adicionales

## Brainmaker

`sargon_brainmaker.py` organiza la creación/evolución de brains, su experimentación y metadatos de rating; `sargon_selfplay.py` produce partidas de entrenamiento o evaluación consigo mismo, según perfil. Los scripts de pipeline PowerShell coordinan prepare, train, evaluación y rutas. El uso actual de redes Cerebrum 1.1 se refiere a inferencia a partir de un modelo ya entrenado; su entrenamiento externo no se identifica con el `sargon_train` que produce checkpoints NPZ.

El programa tiene ademas dos modos auxiliares:

*   ELO, permite calcular el ELO de los jugadores en base a la performance en una competencia (rally) respecto a un player/evaluador de referencia
(en esta plataforma ese es normalmente sargon/classic). El mismo puede salvarse en brains.json para uso futuro.
*   Level, permite nivelar el ELO de distintos players/evaluadores en función de los resultados relativos en un rally determinado.

## Benchmark

Es una herramienta para evaluar la performance relativa de distintas combinaciones de player/evaluador, esto se logra jugando un set de movidas
normalizadas y midiendo los tiempos de ejecución. Este análisis no tiene nada que ver con la calidad de juego del motor, solo su performance absoluta.

## Pgn_Splitter

Programa utilitario para manipular archivos en formato .pgn, contar
partidas y jugadas y segmentar archivos.

# Infraestructura operativa

Es el conjunto de programas cuyo propósito es sostener las comunicaciones
con otros jugadores y evaluaciones de entrenamiento.

## LISTEN y STDIN (UCI)

`sargon_listen` ofrece UCI sobre TCP; `sargon_stdin` o la capa UCI correspondiente permite conexión por entrada y salida estándares. Los comandos habituales son `uci`, `isready`, `ucinewgame`, `position`, `go`, `quit`; `bestmove` debe contener jugada legal o un marcador terminal válido, no un valor arbitrario `(none)` ante un fallo interno. La selección del brain y el tipo de evaluador se resuelven en el bootstrap del motor.



### Integración con ejecutables C++ x86 mediante UCI

Sargon-NNUE incluye adaptadores en `players/picosargon_uci.py`, `players/picoalpha_uci.py`, `players/tinyalpha_uci.py` y el motor genérico `players/uci_external.py`. Un adaptador inicia el ejecutable configurado, sincroniza la sesión UCI, transmite la posición y solicita una jugada. El programa remoto o local mantiene sus propios modelos y algoritmos. El contrato fundamental es:

```text
uci                  → uciok
isready              → readyok
ucinewgame
position startpos moves e2e4 e7e5
go ...
                     ← info depth ... nodes ... score cp ...
                     ← bestmove g1f3
quit
```

La configuración del *brain* determina player, ruta del ejecutable, argumentos permitidos, parámetros de tiempo/búsqueda y, donde corresponda, evaluador `null`. La detección de movimientos ilegales se efectúa contra el tablero mantenido por Sargon-NNUE; los `info` UCI se pueden registrar como profundidad, nodos y puntuación.

### Motor remoto external mediante UCI sobre TCP

El adaptador `players/tcp_external.py` acepta un endpoint **`host:puerto`**, sin prefijo `tcp://` ni `http://`. Ejemplos válidos: `127.0.0.1:6100`, `motor.ejemplo.local:6110` o `[::1]:6100`. El puerto debe estar en `1..65535`; el timeout del adaptador es positivo y su valor inicial en la clase es `30000 ms`.

Una sesión se establece con la secuencia `uci`/`uciok`, `isready`/`readyok`, `ucinewgame` y una nueva comprobación `isready`. Para jugar se transmite el **historial completo** de la partida cuando existe, preferentemente `position startpos moves ...`, o `position fen <fen> moves ...` si parte de una posición inicial personalizada. Se envía después `go` **sin límites impuestos por el cliente**, porque el servidor externo gobierna sus propios recursos. Se consume telemetría `info` cuando esté disponible y se espera `bestmove`. La jugada se valida antes de incorporarse a la partida. En cierre se envía `quit`.

Este contrato hace que un motor C++ ubicado en otro equipo o un UCI accesible mediante puente TCP pueda participar sin copiar sus pesos ni sus fuentes a Sargon-NNUE.

### CLI y configuración de brains

La configuración operacional se concentra en un catálogo JSON de brains, utilizado por `sargon_listen`, `sargon_match`, `sargon_rally` y `sargon_benchmark`. Cada entrada establece identificador, player, evaluator, pesos o ruta de motor cuando corresponde, así como límites de búsqueda. Los identificadores se gestionan separadamente del rating Elo.

### 13.1 Servicio UCI

```powershell
python -m sargon_nnue.sargon_listen --help
```

En `sargon_listen` están definidos argumentos `--mode`, `--host`, `--port`, `--once`, `--version`, `--brain`, `--id`. En modo TCP atiende conexiones por IP/puerto; en modo STDIN la comunicación UCI va por entrada y salida estándar. La identidad UCI se informa en el intercambio inicial con el cliente.

### 13.2 Partidas y competiciones

```powershell
.\scripts\sargon_match.ps1 --help
.\scripts\sargon_rally.ps1 --help
python -m sargon_nnue.sargon_match --help
```

`match` enfrenta dos brains con condiciones homogéneas, produce resultados y admite mecanismos de auditoría de posiciones y evaluadores; `rally` organiza competiciones de múltiples participantes y ranking. Las partidas pueden exportarse a PGN y los resultados a CSV. Los límites de reloj y tiempos consumidos pertenecen a la ejecución real de cada player; para UCI remotos se diferencia la latencia del cliente del tiempo interno de búsqueda reportado.

### 13.3 Defaults significativos

| Componente | Valor inicial o criterio |
|---|---|
| NPZ | Entrada 781, capa oculta 64, salida 1 |
| Factor de calibración NPZ | `400` |
| AlphaZero | Espacio de acciones 4672 |
| SargonPlus `boost` | `0`, máscara independiente de 16 bits en el constructor |
| SargonPlus `turbo` | `0`, máscara independiente de 8 bits en el constructor |
| TCP `external` | `host:puerto`, timeout inicial `30000 ms` en la clase |
| Evaluador de motor externo autónomo | `null` |
| Checkpoint NPZ | `nnue_best.npz` o `nnue_epoch_XXX.npz`, según el flujo |

Los valores operativos por *brain* prevalecen sobre los valores iniciales de las clases y sobre ejemplos de scripts. Para observar los parámetros efectivos, inspeccionar el JSON de brains utilizado y la ayuda CLI del ejecutable real.

### Auditoría y reproducibilidad complementarias

`Sargon-NNUE` incluye herramientas de comparación de jugadores y de evaluadores. Las métricas incluyen victorias/tablas/derrotas, puntuaciones, Elo, duración, profundidad, nodos y, en pares de evaluaciones para las mismas posiciones, desviación media absoluta y máximo error. `sargon_arbiter` lee posiciones FEN y escribe tablas comparables como `data/test/arbiter.csv` y `data/test/arbiter_pairs.csv`.

En entrenamiento se diferencian pérdidas de *train* y *validation*, las fuentes de etiquetas y la identidad de cada red. Para motores MCTS, el número de simulaciones y de nodos explorados no debe confundirse con la profundidad alpha-beta. En las pruebas de `--boost`/`--turbo`, el criterio comparativo es medir fuerza, latencia y nodos en las mismas posiciones y presupuestos, además del resultado de las partidas.

### Secuencias operativas complementarias

**Preparar y entrenar red local**

```powershell
cd .\Sargon-NNUE\scripts
.\run_pipeline_prepare.ps1
.\run_pipeline_train.ps1
```

**Ejecutar una competición desde scripts**

```powershell
cd .\Sargon-NNUE\scripts
.\sargon_match.ps1 --help
.\sargon_rally.ps1 --help
```

**Verificar el servidor UCI y el catálogo de brains**

```powershell
cd .\Sargon-NNUE
python -m sargon_nnue.sargon_listen --help
python -m sargon_nnue.sargon_match --help
```

**Conectar un motor externo por TCP**: definir en el catálogo de brains un player `external` con su endpoint `host:puerto`; iniciar el servidor UCI remoto y seleccionar su brain en los ejecutores de partidas. El adaptador mantiene la sesión UCI y valida `bestmove`.

---

## MATCH

`sargon_match.py` enfrenta dos instancias UCI, asigna colores, aplica límites y conserva resultados CSV/PGN. Sus argumentos incluyen selección de perfil mediante `--brain`, `--idA`, `--idB`, `--pairs`, `--max-plies`, `--csv`, `--pgn`; cuando están disponibles, override de máscaras `--a-boost`, `--b-boost`, `--a-turbo`, `--b-turbo`, y `--boost-audit-dir`. El archivo de movimientos contiene FEN previo, jugada, proceso y tiempos.

## RALLY

`sargon_rally.py` interpreta la definición JSON de torneos `tournaments`, expande una lista de participantes a todos contra todos y lanza MATCH por pareja. Los campos de torneo incluyen `name`, `brains`, `plays_per_pair`, `max_simultaneous_games`, `max_game_seconds` y `pgn`. La CLI soporta `--id`, `--brain`, `--rally`, `--preflight-only`, `--scores`, `--boost-audit-dir`. *Preflight* valida inicialización UCI y respuesta `bestmove`. Una falla deja el torneo incompleto, no debe contabilizarse como derrota deportiva.

## SELFPLAY

`sargon_selfplay.py` ejecuta autocompetencia con perfiles y límites configurables; permite producir partidas para análisis o alimentar procesos de aprendizaje. Su captura de auditoría reutiliza el mecanismo estructurado, cuando está activado.

## AUDIT y JUDGE

`sargon_audit.py` puede analizar datasets de entrenamiento o el directorio completo de auditoría BOOST/TURBO. `sargon_judge.py` examina resultados y, cuando hay evaluación por posición, fidelidad numérica y discrepancias de decisiones. Las funciones no son intercambiables: AUDIT comprueba integridad/cobertura de capturas; JUDGE interpreta resultados competitivos.

## Reproducción y almacenamiento

Cada ejecución crea un directorio único. Es incorrecto reutilizar uno que ya contiene ; ello mezclaría evidencia de corridas distintas. Los CSV analíticos deben generarse por defecto al lado de los JSONL que los originaron, no en un directorio compartido global. La velocidad percibida se mide tanto en `response_ms` (UCI) como `elapsed_ms` (búsqueda interna); la diferencia corresponde a comunicación y overhead del entorno.

# APPENDIX - Referencia de uso y ejemplos

## Definir un brain

    { "schema_version": 1, "brains": {
      "classic": {"player":"sargon-plus", "evaluator":"classic",
         "depth":2,"qdepth":2,"tmax":15000,"boost":0,"turbo":0},
      "s0001": {"player":"sargon-plus", "evaluator":"classic",
         "depth":2,"qdepth":2,"tmax":15000,"boost":"0x0001","turbo":0},
      "cerebrum3": {"player":"cerebrum", "evaluator":"cerebrum-1.1",
         "network":"../data/nnue/cerebrum/epoch-11-q.txt","qdepth":3},
      "stockfish": {"player":"stockfish", "evaluator":"null",
         "engine-path":"C:/ruta/stockfish.exe","movetime":1000}
    }}

## Definir un RALLY

    {"schema_version":1,"tournaments":{"boost":{
      "name":"Boost individual y turbo",
      "brains":["buddy","classic","smart","s0001","sT01"],
      "plays_per_pair":10,
      "max_simultaneous_games":2,
      "max_game_seconds":1200,
      "pgn":"../data/rally/boost.pgn"
    }}}

## Ejecutar y auditar

    .\sargon_rally.ps1 --id boost --brain ..\data\brains\brains.json `
        --rally ..\data\rally\boost.json `
        --boost-audit-dir ..\data\runs\RUN\audit
    .\sargon_audit.ps1 --input ..\data\runs\RUN\audit --validate
    .\sargon_audit.ps1 --input ..\data\runs\RUN\audit --boost-audit

## Interpretación de resultados

La puntuación competitiva es $P=W+\frac12D$, con rendimiento $p=P/N$. Para optimizaciones se comparan por separado puntos, errores UCI, latencias $\overline t$, percentil 95 y nodos. A igualdad de tiempo, una variante rápida puede profundizar más; a profundidad fija, puede producir otra jugada sin mejorar su calidad. Una coincidencia de puntaje raíz no demuestra igualdad de valor individual de cada jugada candidata. Partidas deterministas repetidas no equivalen a muestras independientes de aperturas diversas.

# Appendix - Arquitectura de módulos

| Componente                   | Responsabilidad funcional                                              |
|:-----------------------------|:-----------------------------------------------------------------------|
| `players/sargon_core.py`     | Núcleo compartido de búsqueda y resolución temporal.                   |
| `players/sargon_plus.py`     | Aplicación de BOOST/TURBO e instrumentación de búsqueda.               |
| `players/cerebrum_player.py` | Elección Cerebrum a un ply, qsearch opcional e inferencia incremental. |
| `players/__init__.py`        | Factory y registro de players.                                         |
| `evaluators/base.py`         | Contrato de evaluación escalar y extensión incremental.                |
| `evaluators/cerebrum_v11.py` | Adaptador y modelo Cerebrum 1.1.                                       |
| `sargon_prepare.py`          | PGN, bases de posiciones y etiquetas.                                  |
| `sargon_train.py`            | Entrenamiento, validación y checkpoint NPZ.                            |
| `sargon_brainmaker.py`       | Gestión de brains, ranking y procesos asociados.                       |
| `sargon_match.py`            | Orquestación de dos procesos UCI; PGN y registros.                     |
| `sargon_rally.py`            | Torneos múltiples, preflight y clasificación.                          |
| `sargon_selfplay.py`         | Partidas automáticas.                                                  |
| `sargon_audit.py`            | Auditoría de dataset y auditoría persistente de búsquedas.             |
| `boost_audit_coverage.py`    | Cobertura de modalidades BOOST/TURBO.                                  |
| `boost_differential.py`      | Comparación externa, mismo FEN, dos configuraciones.                   |
| `boost_audit_validate.py`    | Consistencia de búsquedas, jugadas y partidas.                         |
| `sargon_judge.py`            | Comparación competitiva y fidelidad numérica.                          |

El nombre físico exacto de alguna clase o archivo auxiliar puede variar entre despliegues incrementales. La lista es un mapa funcional comprobable con los scripts y parches disponibles; debe contrastarse con el repositorio instalado antes de una intervención de mantenimiento.



### Mapa ampliado de módulos y responsabilidades

| Módulo | Responsabilidad |
|---|---|
| `players/sargon.py` | Núcleo minimax/alpha-beta |
| `players/sargon_plus.py` | Máscaras boost/turbo, heurísticas, TT y búsqueda adaptativa |
| `players/alphazero.py` | Player de búsqueda MCTS |
| `az_core.py` | Codificación de acciones y reconstrucción de estados |
| `az_model.py`, `az_policy.py` | Modelo y políticas de entrenamiento |
| `az_seed_train.py`, `az_train.py` | Entrenamiento de redes AlphaZero |
| `az_mcts_label.py` | Etiquetado mediante búsqueda MCTS |
| `evaluators/npz.py` | Carga, evaluación y persistencia NPZ |
| `evaluators/lc0.py` | Inferencia/adapter LCZero |
| `players/lc0_uci.py` | LC0 autónomo por UCI |
| `players/picosargon_uci.py`, `players/picoalpha_uci.py` | Conexión a programas C++ x86 |
| `players/tcp_external.py` | Adaptador UCI sobre TCP |
| `sargon_prepare.py`, `sargon_train.py` | Preparación, etiquetado y entrenamiento |
| `sargon_listen.py` | Servidor UCI |
| `sargon_match.py` | Partidas y confrontaciones |

**Convención:** la documentación de arquitectura de los motores externos se mantiene separada de este manual. La interfaz que Sargon-NNUE necesita conocer es su contrato UCI, su configuración y el identificador de player/evaluador asignado.

# Red NNUE Nativa (NPZ) arquitectura

## Representación de estado

La codificación inicial empaqueta 781 características posicionales: una parte esencial es la ocupación por pieza/color/casilla y el resto contiene estado auxiliar (turno, enroques, posibilidad de captura al paso y/o halfmove según el contrato). Cada atributo debe preservar un orden canónico; una permutación de bits puede producir valores aparentemente válidos pero ajedrecísticamente incorrectos. No asumir que la estructura de características codifica todo el historial de repetición.

## Modelo y parámetros

La arquitectura densa $781\times64$ más un vector de sesgo de 64 dimensiones y $64\times1$ más sesgo escalar posee $781\cdot64+64+64+1=50113$ parámetros principales, excluyendo términos externos como halfmove. En $x\in\mathbb R^{781}$, el forward es $z=w_2^\top\operatorname{ReLU}(W_1x+b_1)+b_2$. Para objetivo CLASSIC la escala documentada produce $e_{cp}\approx400z$ más correcciones pertinentes. El contenido exacto de un checkpoint se inspecciona por forma y metadatos; la extensión NPZ no identifica por sí sola el objetivo o dimensiones.

## Generación de señal y optimización

Una muestra supervisada asocia posición y objetivo $y$, con $L=\frac{1}{N}\sum(f_\theta(x_i)-y_i)^2$. Un lote de tamaño $B$ aproxima el gradiente $\nabla_\theta L$. Adam/AdamW y otras opciones del programa actualizan parámetros mediante su historia de momentos; la tasa $\eta$, regularización y programación de aprendizaje influyen en estabilidad. Entrenar con resultados PGN da objetivos débiles para posiciones intermedias; maestro CLASSIC o WDL de Stockfish ofrece señales más densas, pero puede transferir sesgos del maestro.

## Diagnóstico de convergencia

Separar MSE de train/validation, proporción de etiquetas válidas y rendimiento competitivo. Una red que imita bien CLASSIC no necesariamente supera a CLASSIC ni a Sargon con el mismo evaluador. Observar tendencia de loss, gap de generalización, saturación de salidas, gradientes y consistencia al reanudar checkpoint. El objetivo de aprendizaje con etiquetas $y$ distintas no tiene MSE comparable sin transformación previa. La métrica de acierto *top-1* requiere valorar explícitamente alternativas y no puede inferirse directamente del error escalar de posición.

## Compatibilidad de checkpoint

Validar peso y sesgo, escala, codificación, estado CPU/dispositivo y semántica de objetivo. Rechazar archivo existente corrupto; registrar hash y entrenamiento de origen. La inferencia en NumPy debe preservar evaluación blanca y reproducibilidad, incluyendo corrección de medio movimiento cuando se implemente.



### Arquitectura y serialización NPZ

La red **Sargon-NPZ** es un perceptrón 781–64–1 con activación ReLU:

\[
h=\max(0,xW_{ih}+b_h), \quad
\hat y=hW_{ho}+b_o+hm_w\frac{halfmove}{50}.
\]

Con `x∈{0,1}^{781}`, `W_ih∈R^{781×64}`, `b_h∈R^{64}`, `W_ho∈R^{64×1}`, `b_o∈R` y `hm_w∈R`. Se aplica una calibración de puntuación en la interfaz de evaluación (factor de referencia `400` centipeones). El archivo `.npz` es un contenedor de arrays NumPy con las claves **`w_ih`, `b_h`, `w_ho`, `b_o`, `hm_w`**. Los modelos antiguos de 32 neuronas ocultas no cumplen la estructura actual.

El objetivo básico de entrenamiento supervisado puede expresarse mediante error cuadrático medio:

\[
L_{value}(\theta)=\frac1m\sum_{i=1}^{m}(f_\theta(x_i)-y_i)^2.
\]

El proceso reserva observaciones para validación, calcula pérdidas y emite checkpoints como `nnue_epoch_001.npz` y `nnue_best.npz` en `data/runs/<nombre>/checkpoints/`. Una carga de checkpoint existente exige estructuras compatibles; el entrenamiento nuevo y la continuación de un entrenamiento anterior son operaciones diferenciadas.

### Formatos NPZ, NPX, PB.GZ y PT

| Extensión | Identidad | Contenido / interoperabilidad |
|---|---|---|
| `.npz` | Red de evaluación de Sargon-NNUE | Archivo de arrays NumPy, con arquitectura 781–64–1 y claves descritas arriba |
| `.npx` | Formato NNUE de **picoSargon** | Representación propia de pesos NNUE asociada al motor picoSargon; distinta del contenedor NumPy NPZ |
| `.pb.gz` | Redes **LC0** | Pesos y metadatos de arquitectura serializados y comprimidos, interpretados por el backend LC0 |
| `.pt` | Checkpoint PyTorch | Estado de tensores de entrenamiento; para utilización por LC0 se requiere conversión compatible a `.pb.gz` |
| `.bin` | Pesos binarios externos | Por ejemplo, pesos Grumpy usados por adaptadores específicos; no es automáticamente equivalente a NPX |

La capa de integración de Sargon-NNUE no presupone que `.npz`, `.npx` y `.pb.gz` sean formatos intercambiables. Sus lectores interpretan arquitecturas distintas. La existencia de `grumpy.bin` dentro de un proyecto no cambia la definición de `.npx`: son artefactos diferentes y deben identificarse por su lector/serializador concreto.

# Appendix - Cerebrum 1.1: modelo, incrementalidad y evaluación

## Alcance de la documentación

Cerebrum 1.1 es una red preentrenada usada desde el proyecto mediante un adaptador en ; los modelos operativos aparecen en archivos de texto como . El manual previo y los parches disponibles no contienen una especificación tensorial completa y verificable de cada capa del modelo externo. En consecuencia se documenta con detalle el contrato matemático de evaluación y la integración, pero *no se inventa* una topología exacta no sustentada por el código fuente del entrenador externo.

## Cómputo de valor

La red evalúa una posición a partir de características ajedrecísticas y devuelve un escalar que el adaptador convierte a centipawns de perspectiva blanca. En una arquitectura incremental NNUE genérica, un acumulador puede expresarse como $a(s)=b+\sum_{f\in F(s)}w_f$, seguido de activación y capas de salida $e(s)=g(a(s))$. Esto es una descripción de la familia de métodos, no una afirmación sobre dimensiones internas de Cerebrum 1.1. El adaptador asegura signos, normalización y tipos al pasar el valor al player.

## Inferencia incremental

Para pasar de un padre $s$ a su hijo $s'$, se actualiza el acumulador mediante $a(s')=a(s)-\sum_{f\in F_{removed}}w_f+\sum_{f\in F_{added}}w_f$. Así el costo depende de características modificadas por la jugada. La optimización es válida si los cambios de tablero, turno, enroque, promoción y en passant actualizan consistentemente el estado. La interfaz permite entregar `previous_state` como pista; si no es válido se requiere ruta de evaluación completa. El bit `0x2000` permite que Sargon-Plus solicite incrementalidad al evaluador compatible.

## Entrenamiento y convergencia

El proceso de entrenamiento externo de Cerebrum no es el de NPZ y no es compatible. De hecho, la red utilizada por Cerebrum si bien es también de arquitectura NNUE no tiene la misma configuración ni resultados. La misma puede ser entrenada con herramientas provistas por la plataforma Cerebrum o utilizarse una versión ya entrenada. Durante su entrenamiento las métricas son las usuales en entrenamiento de redes neurales loss de aprendizaje, error de validación, calidad frente a maestro, saturaciones, estabilidad de pesos y rendimiento competitivo por checkpoint; los parches examinados sólo verifican la integración de inferencia y no aportan una serie auditable de esas métricas. Los modelos de época deben conservar su identificación y hash para comparar competencias sin introducir variaciones inadvertidas.

## CerebrumPlayer y alcance táctico

Con `qdepth=0` evalúa candidatas a un ply; con `qdepth>0` utiliza una continuación quiescence sobre capturas, promociones y jaques. En un RALLY reducido, `qdepth=3` presentó competitividad superior a otras variantes, pero esa evidencia no constituye una demostración universal de optimalidad. La mejora se atribuye al sistema completo de selección y evaluación, no únicamente a un checkpoint.

# Appendix - Redes MCTS: fundamentos e integración

## Introducción

Monte Carlo Tree Search (MCTS) es un algoritmo de búsqueda por simulaciones; no constituye por sí mismo una red neuronal. Una integración moderna suele entrenar una red de *política* $p_\theta(a\mid s)$ y una red de *valor* $v_\theta(s)$, que alimentan la selección de nodos. Este apéndice describe una alternativa todavía no incorporada como evaluador/plataforma operativa de Sargon-NNUE; no presenta comandos ficticios.

## Selección y expansión

Una regla PUCT típica selecciona $a^*=\arg\max_a [Q(s,a)+c_{puct}P(s,a)\frac{\sqrt{\sum_b N(s,b)}}{1+N(s,a)}]$. Los términos $Q$, $N$ y $P$ representan valor medio acumulado, visitas y prior de política. El nodo nuevo se expande con sus jugadas legales y un valor inicial calculado por la red o por un mecanismo de rollouts. Durante backup, valores de bandos opuestos cambian signo.

## Entrenamiento autosupervisado

En un ciclo de autojuego, la política objetivo se obtiene de frecuencias de visitas $\pi(a\mid s)\propto N(s,a)^{1/\tau}$, y el valor objetivo $z\in\{-1,0,1\}$ proviene del desenlace desde el punto de vista correspondiente. Una pérdida frecuente es $$L=(z-v_\theta(s))^2-\pi^\top\log p_\theta(\cdot\mid s)+\lambda\lVert\theta\rVert^2.$$ Se alternan autojuego, almacenamiento de ejemplos, optimización y evaluación del nuevo checkpoint.

## Integración potencial con Sargon

Un player Sargon requiere un valor para las posiciones resultantes de jugadas candidatas, mientras que un sistema MCTS entrenado entrega tanto distribución de política como valor. Hay tres posibilidades: usar $v_\theta(T(s,a))$ como evaluador de cada jugada de Sargon; usar $p_\theta(a\mid s)$ sólo como ordenamiento; o utilizar MCTS como player completo. La primera mantiene la separación player–evaluator, pero desperdicia información de política; la segunda necesita cuidado para no confundir prior con valor; la tercera requiere un nuevo player. La semántica terminal, normalización de signos, gestión de tiempo y adquisición de entrenamiento deben definirse antes de adoptar cualquiera.

# Appendix - Evaluación de entrenamiento

El entrenamiento de las redes neuronales tiene dos etapas bien diferenciadas:

*   Convergencia durante el entrenamiento.
*   Evaluación de performance.

## Convergencia durante el entrenamiento

Durante el entrenamiento el principal problema es que la red memorice el set de entrenamiento en vez de aprenderlo por generalización. No hay una heurística única para analizarlo pero es util evaluar dos factores durante el entrenamiento:
*   El MSE del lote de entrenamiento se reduce entre epoch sucesivos.
*   El MSE del lote de validación se reduce entre epoch sucesivos.
*   El MSE entre ambos grupos tiene valores similares.

Lo que se observa con mas frecuencia es que el MSE de entrenamiento disminuye pero no asi el de validación, eso significa que la red está memorizando el set de entrenamiento pero no está pudiendo generalizar el resultado al conjunto de validación, el cual metodológicamente desconoce.
Otro aspecto notable es que el MSE de validación se reduzca pero permanezca alto comparado con el MSE de entrenamiento, eso suele significar ruido en la señal de refuerzo.
La solución a éstos problemas es mayormente empírica, y el conjunto de entrenamiento está preparado para correr muchas sesiones de entrenamiento con la misma base de ejemplos. Usualmente es una combinación de un learning rate mas pequeño y una disminución periódica del learning rate a medida que progresan los epochs. No necesariamente el último epoch es el mejor, es mejor aquel que es el punto de inflexión en el MSE de validación, los scripts configuran PyTorch para que guarde el mejor.

## Evaluación de performance

La evaluación de performance es también mayormente carente de una heurística clara, básicamente consiste en que el motor juegue y se pueda observar las bondades (o pobrezas) de su juego.
Esto se puede lograr habilitando el motor para competir en plataformas
como liches.org, el programa lichess-bot.py puede ser configurado exitorsamente para conectar con el programa sargon_listen.py mediante el programa sargon_bridge.py.
No obstante las partidas en ésta plataforma son usualmente lentas de acuerdo al modo y el número de ellas que se puede hacer por día es limitado. Adicionalmente la gestión de la plataforma detecta rápidamente un jugador que se comporte en forma errática, por ejemplo que pierda muy rápido o pierda mucho. Situaciones que no son raras al experimentar una nueva configuración, una red nueva o simplemente un algoritmo fallido.
Mucho mas útil es trabajar mediante juegos internos, de esa manera se pueden hacer cientos de partidas por hora y establecer un ranking entre configuraciones. Los mecanismos son básicamente tres:
* Uso del programa *challenger* el cual es un jugador estable que puede jugar con algoritmo Sargon (clásico) o con Stockfish como motor de jugadas. Se pueden jugar automáticamente un número de partidas contra una instancia de listener teniendo una determinada combinación de player/evaluador con su respectiva configuración. El criterio de evaluación es que una combinación player/evaluador supere en promedio al algoritmo sargón y que sea capaz de ganar una proporción minoritaria de las partidas con el algoritmo stockfish.
* El uso del programa *sargon_match* permite establecer rondas de juegos de a pares entre dos combinaciones cualquiera de player/evaluador, normalmente se lo emplea contra una configuración de referencia para medir mejora.
* El uso del programa *sargon_match* permite establecer *rallies* (torneos) con un número arbitrario de combinaciones player/evaluador de manera que todos compitan contra todos un número de partidas por enfrentamiento.
El resultado de las evaluaciones anteriores permite ir, incrementalmente, identificando las fortalezas relativas entre players, evaluadores y distintas estrategias de configuración (por ejemplo redes NNUE entrenadas a distinto nivel o de distinto tamaño). El poder asignar una variante de puntuación basada en el algoritmo ELO (sargon.brainmaker.py) permite estudiar la capacidad relativa entre distintas combinaciones player/evaluador (brain) aunque esa medida no es en realidad comparable con el puntaje ELO asignado por plataformas como lichess.org. 
Sin embargo, cuando un brain está suficientemente estable y su performance es aceptable respecto a otras combinaciones es importante abrirlo a juegos online donde será desafiado por otros bots de distintas capacidades y será entonces posible evaluar su performance con mas realismo. Al presente la combinación AlphaZero/lc0 con red pequeña converge a un ELO asignado por lichess.org en el entorno de 2500-2600. 

# Appendix - Cronología de versiones

Este apéndice es el único lugar donde se documenta la secuencia de versiones. Los títulos de los paquetes señalan el ámbito de cada entrega, pero no equivalen a una especificación completa de su contenido. Las versiones sin paquete local verificable se identifican como hitos registrados en la documentación precedente.

| Versión   | Entrega o hito identificado                                                                                                             |
|:----------|:----------------------------------------------------------------------------------------------------------------------------------------|
| `v0.6.0`  | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.1`  | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.2`  | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.3`  | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.4`  | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.5`  | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.6`  | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.7`  | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.8`  | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.9`  | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.10` | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.11` | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.12` | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.13` | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.14` | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.15` | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.16` | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.17` | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.18` | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.19` | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.20` | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.21` | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.22` | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.23` | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.24` | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.25` | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.26` | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.27` | Evolución inicial del núcleo, redes, evaluadores y arquitectura, documentada en manuales previos; sin paquete individual examinado aquí |
| `v0.6.28` | Paquete: parche                                                                                                                         |
| `v0.6.29` | Paquete: parche                                                                                                                         |
| `v0.6.30` | Paquete: parche                                                                                                                         |
| `v0.6.31` | Paquete: parche                                                                                                                         |
| `v0.6.32` | Paquete: parche                                                                                                                         |
| `v0.6.33` | Paquete: parche                                                                                                                         |
| `v0.6.34` | Paquete: parche                                                                                                                         |
| `v0.6.35` | Paquete: parche                                                                                                                         |
| `v0.6.36` | Paquete: parche                                                                                                                         |
| `v0.6.37` | Paquete: parche                                                                                                                         |
| `v0.6.38` | Paquete: parche                                                                                                                         |
| `v0.6.39` | Paquete: parche                                                                                                                         |
| `v0.6.40` | Paquete: parche                                                                                                                         |
| `v0.6.41` | Paquete: validation parche                                                                                                              |
| `v0.6.42` | Paquete: match parche                                                                                                                   |
| `v0.6.43` | Paquete: judge parche                                                                                                                   |
| `v0.6.44` | Paquete: match parche                                                                                                                   |
| `v0.6.45` | Paquete: match parche                                                                                                                   |
| `v0.6.46` | Paquete: auditoria posicional parche                                                                                                    |
| `v0.6.47` | Paquete: match parche                                                                                                                   |
| `v0.6.48` | Paquete: classic teacher parche                                                                                                         |
| `v0.6.49` | Paquete: prepare parche                                                                                                                 |
| `v0.6.50` | Paquete: finetune parche                                                                                                                |
| `v0.6.51` | Paquete: refine pgn audit parche                                                                                                        |
| `v0.6.52` | Paquete: match telemetria parche                                                                                                        |
| `v0.6.53` | Paquete: brains parche                                                                                                                  |
| `v0.6.54` | Paquete: brains cleanup parche                                                                                                          |
| `v0.6.55` | Paquete: pipeline parche                                                                                                                |
| `v0.6.56` | Paquete: pipeline paths parche                                                                                                          |
| `v0.6.57` | Paquete: pipeline ps51 parche                                                                                                           |
| `v0.6.58` | Paquete: rally parche                                                                                                                   |
| `v0.6.59` | Paquete: brainiac match script                                                                                                          |
| `v0.6.60` | Paquete: match startup parche                                                                                                           |
| `v0.6.61` | Paquete: brainiac override parche                                                                                                       |
| `v0.6.62` | Paquete: brainiac override fix                                                                                                          |
| `v0.6.63` | Paquete: match game start parche                                                                                                        |
| `v0.6.64` | Paquete: match judge telemetry parche                                                                                                   |
| `v0.6.65` | Paquete: brainiac script completo                                                                                                       |
| `v0.6.66` | Paquete: brainmaker telemetria                                                                                                          |
| `v0.6.67` | Paquete: brainmaker alineado                                                                                                            |
| `v0.6.68` | Paquete: rally preflight parche                                                                                                         |
| `v0.6.69` | Paquete: rally utf8 match parche                                                                                                        |
| `v0.6.70` | Paquete: match rally pulso                                                                                                              |
| `v0.6.71` | Paquete: rally preflight random null                                                                                                    |
| `v0.6.72` | Paquete: rally preflight startup fix                                                                                                    |
| `v0.6.73` | Paquete: cerebrum11 profiles fix                                                                                                        |
| `v0.6.74` | Paquete: match rally sin parpadeo                                                                                                       |
| `v0.6.75` | Paquete: match rally verbose score                                                                                                      |
| `v0.6.76` | Paquete: match progress cleanup                                                                                                         |
| `v0.6.77` | Paquete: rally clasificacion                                                                                                            |
| `v0.6.78` | Paquete: rally scores                                                                                                                   |
| `v0.6.79` | Paquete: brainmaker elo                                                                                                                 |
| `v0.6.80` | Paquete: brainmaker elo alineado                                                                                                        |
| `v0.6.81` | Paquete: brains random null regression fix                                                                                              |
| `v0.6.82` | Paquete: brainmaker utf8                                                                                                                |
| `v0.6.83` | Paquete: rating elo match fix                                                                                                           |
| `v0.6.84` | Paquete: match rating metadata fix                                                                                                      |
| `v0.6.85` | Paquete: boost incremental eval                                                                                                         |
| `v0.6.86` | Paquete: boost incremental contract                                                                                                     |
| `v0.6.87` | Paquete: cerebrum qdepth rally                                                                                                          |
| `v0.6.88` | Paquete: boost turbo persistent audit                                                                                                   |
| `v0.6.89` | Paquete: audit turbo0 fix                                                                                                               |
| `v0.6.90` | Paquete: audit validation parche                                                                                                        |
| `v0.6.91` | Paquete: boost turbo coverage parche                                                                                                    |
| `v0.6.92` | Paquete: audit same run directory                                                                                                       |
| `v0.6.93` | Paquete: boost differential audit                                                                                                       |
