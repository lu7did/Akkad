Planteo outline de "Nunca fue ajedrez"
Libro de experiencias de investigación de Dr. Pedro E. Colla

[Portada]

# Prefacio

Es un manual anotado,un journal de actividades

# Introducción

## Motivaciones

## Antecedentes históricos


### Los inicios teóricos y mecánicos (1912 - 1950)

#### El Ajedrecista (1912):

 Construído por el ingeniero español Leonardo Torres y Quevedo, fue un autómata electromecánico capaz de jugar de forma totalmente automática un final de torre
 y rey contra el rey de un oponente humano. Se considera el primer juego de ajedrez automatizado de la historia.

#### Turochamp (1948):

Desarrollado en papel por Alan Turing junto a David Champernowne. Era un algoritmo con un sistema de puntuación heurístico que calculaba
dos jugadas en el futuro. Al no existir computadoras capaces de ejecutarlo, Turing tuvo que simular el código a mano (tardando unos 30 minutos por movimiento)
en una partida jugada en 1952.

#### El artículo de Claude Shannon (1950):

El matemático Claude Shannon publicó "Programming a Computer for Playing Chess" [LINK], el texto fundacional que definió las dos estrategias básicas
 de búsqueda para las computadoras de ajedrez:

* la Tipo A (fuerza bruta, evaluar todas las jugadas posibles)
* la Tipo B (búsqueda selectiva, evaluar solo las mejores jugadas).


### Las primeras ejecuciones en computadoras (1951 - 1959)

#### El programa de Dietrich Prinz (1951):
El primer programa de ajedrez real ejecutado por una computadora digital. Fue escrito para la Ferranti Mark 1 en la Universidad de Mánchester.
No jugaba partidas completas, pero era capaz de resolver problemas de **"jaque mate en dos jugadas"**.

#### El Ajedrez de Los Alamos (1956):
Desarrollado en la computadora MANIAC I por un equipo del Laboratorio Científico de Los Álamos (incluido Stanislaw Ulam).
Debido a las limitaciones de memoria, redujeron el tablero a 6x6 (sin alfiles ni peones dobles).
Fue el primer programa en jugar una partida completa y derrotar a un contrincante humano (un principiante que recibió ventaja).

#### El programa de Alex Bernstein (1957):
Creado en una IBM 704, fue el primer programa capaz de jugar una partida completa en un tablero estándar de 8x8.
Utilizaba una estrategia Tipo B (selectiva), analizando las 7 mejores jugadas posibles en cada posición.

### La era académica y los primeros torneos (1960 - 1977)

#### El programa Kotok-McCarthy (1962):
Desarrollado en el MIT bajo la tutela de John McCarthy. En 1966 protagonizó el primer match de ajedrez entre computadoras de la historia, enfrentándose vía telégrafo
al programa del Instituto de Física Teórica y Experimental (ITEP) de la Unión Soviética. El programa soviético ganó el encuentro 3-1.

#### Mac Hack Six (1966-1967):
Escrito por Richard Greenblatt en el MIT para la computadora PDP-6. Fue un punto de inflexión absoluto: incorporó amplios conocimientos de aperturas y heurísticas de ajedrez.
Se convirtió en el primer programa en competir contra humanos en torneos oficiales, logrando la primera victoria computacional contra un jugador federado y obteniendo un
rating ELO de unos 1200 o 1400 puntos.

#### La serie "Chess" de Northwestern University (1970 - 1977):
Creado por Larry Atkin, David Slate y Keith Gorlen. Sus versiones (Chess 3.0, Chess 4.0, etc.) dominaron por completo los primeros Campeonatos de Ajedrez de Computadoras de la ACM.
En 1977, Chess 4.6 ganó el segundo Campeonato Mundial de Ajedrez por Computadora y logró vencer por primera vez a un Gran Maestro (Michael Stean) en una partida de ajedrez rápido.

## El Fenómeno Histórico de Microchess (1976)

Microchess es el primer programa de ajedrez comercialmente exitoso para microcomputadoras en la historia de la informática.
Diseñado originalmente en 1976 por Peter R. Jennings para el microcomputador hobbista KIM-1 de MOS Technology, demostró al mundo que una máquina extremadamente
limitada podía ejecutar una simulación interactiva inteligente, ayudando a cimentar el mercado del software comercial independiente.

Fuentes
[1] (https://chessprogramming.org/Peter_Jennings),
[2] (https://en.wikipedia.org/wiki/Microchess),
[3] (https://es.wikipedia.org/wiki/Microchess),
[4] (https://wiki.texto-plano.xyz/microchess),
[5] (https://www.microsiervos.com/archivo/ordenadores/historia-microchess-juego-ajedrez-1k-primer-software-comercial-historia.html),
[6] (https://www.schach-computer.info/wiki/index.php?title=Jennings,_Peter_En)

### Orígenes e Historia

[FOTOGRAFIA DE KIM-1 con MicroChess]

En el año 1976, las computadoras domésticas daban sus primeros pasos. El KIM-1 de MOS Technology no era una computadora convencional, 
se trataba de una placa de circuito impreso sin caja, provista de un microprocesador MOS 6502 a 1 MHz, un teclado hexadecimal de 24 teclas, un display de 7 segmentos
de 6 dígitos y la asombrosa cantidad de 1 Kilobyte (1024 bytes) de memoria RAM.

[1] (https://benlo.com/microchess/), 
[2] (https://es.wikipedia.org/wiki/Microchess)

Peter Jennings, un recién graduado universitario, se propuso el desafío de meter un juego de ajedrez completo en ese espacio.
El 18 de diciembre de 1976 nació Microchess.

[1] (https://www.computerhistory.org/chess/early-microcomputer-chess/), 
[2] (https://www.schach-computer.info/wiki/index.php?title=Jennings,_Peter_En), 
[3] (https://es.wikipedia.org/wiki/Microchess), 
[4] (https://benlo.com/microchess/)

#### El primer hito comercial

[FOTOGRAFIA DE MICROCHESS]

Inicialmente, Jennings vendía el programa por $10 dólares enviando un manual físico que contenía el código fuente completo en lenguaje ensamblador.
Los compradores debían teclear línea por línea los códigos hexadecimales en sus computadoras.
Más adelante, cofundó Personal Software y comenzó a distribuirlo en casete, vendiendo decenas de miles de copias (y eventualmente millones con sus posteriores
versiones gráficas para Apple II, TRS-80 y Commodore PET).
Curiosamente, las regalías generadas por Microchess sirvieron para financiar el desarrollo y lanzamiento de VisiCalc, la primera hoja de cálculo de la historia.

[1] (https://www.schach-computer.info/wiki/index.php?title=Jennings,_Peter_En),
[2] (https://es.wikipedia.org/wiki/Microchess), 
[3] (https://www.microsiervos.com/archivo/ordenadores/historia-microchess-juego-ajedrez-1k-primer-software-comercial-historia.html),
[4] (https://www.computerhistory.org/chess/early-microcomputer-chess/), 
[5] (https://translate.google.com/translate?u=https://en.wikipedia.org/wiki/Microchess&hl=es&sl=en&tl=es&client=sge)

#### Filosofía de Diseño

La filosofía detrás de Microchess no era vencer a Grandes Maestros, sino lograr lo aparentemente imposible, la compresión absoluta y la optimización radical de un desarrollo de 
software dentro de recursos inimaginablemente reducidos.
En lugar de un árbol de búsqueda masivo, Jennings se enfocó en:

[1] (https://www.schach-computer.info/wiki/index.php?title=Jennings,_Peter_En)
[1] (https://translate.google.com/translate?u=https://en.wikipedia.org/wiki/Microchess&hl=es&sl=en&tl=es&client=sge)
[1] (https://www.schach-computer.info/wiki/index.php?title=Jennings,_Peter_En), [2] (https://translate.google.com/translate?u=https://en.wikipedia.org/wiki/Microchess&hl=es&sl=en&tl=es&client=sge)

* Accesibilidad y entretenimiento: El creador afirmaba que parte de su éxito comercial radicaba en que el programa cometía errores humanos,
lo que hacía divertido jugar contra él y ganarle.
* Demostración técnica: Servir como una "analogía del mundo real" para mostrar a familiares y amigos de qué era capaz un microordenador, rompiendo la percepción
de que estas máquinas eran meros juguetes de luces parpadeantes.
* Heurística simplificada: Basarse en conceptos estratégicos del famoso libro *My System* de Aron Nimzowitsch para tomar decisiones sin sobrecargar la memoria.
[1] (https://benlo.com/microchess/)

#### Implementación Técnica

El programa original de Microchess ocupaba exactamente 924 bytes de memoria. En ese espacio diminuto se incluyó el generador de movimientos, la lógica de validación,
la función de evaluación, la interfaz de entrada/salida y las variables del juego. [1] (https://www.schach-computer.info/wiki/index.php?title=Jennings,_Peter_En)

* Lenguaje: Código máquina / Ensamblador puro del MOS 6502. [1] (https://es.wikipedia.org/wiki/Microchess)
* Interfaz de Usuario Básica: Sin gráficos. El jugador introducía su movimiento en formato numérico (por ejemplo, anotando las coordenadas de origen y destino por número
 de casilla) usando las teclas de la placa KIM-1, y el display de 7 segmentos respondía mostrando la jugada de la máquina. [1] (https://www.computerhistory.org/chess/early-microcomputer-chess/), [2] (https://translate.google.com/translate?u=https://en.wikipedia.org/wiki/Microchess&hl=es&sl=en&tl=es&client=sge)
* Estructura de Datos Ultra-Comprimida: En lugar de mapear un tablero clásico de 64 casillas completas (que consumiría demasiada memoria para la época),
 utilizaba una matriz compacta orientada al conteo y posición de piezas activas de cada bando. [1] (https://chessprogramming.org/MicroChess)

#### Características Principales

* Modo de Juego Humano vs. CPU: Permitía jugar partidas completas contra el computador.
* Velocidades de ejecución configurables: Las versiones iniciales podían responder al instante, tomar de 5 a 10 segundos o calcular de forma más profunda para una
partida de aproximadamente una hora en total.
* Niveles de dificultad: Dependiendo de la versión, ofrecía desde 3 niveles (Microchess 1.5) hasta 8 niveles de juego en versiones posteriores.
* Herramienta de práctica: Era ideal para aprender aperturas estándar y practicar mates sencillos. [1] (https://www.ecured.cu/Microchess), [2] (https://translate.google.com/translate?u=https://en.wikipedia.org/wiki/Microchess&hl=es&sl=en&tl=es&client=sge)

#### Algoritmo Detallado

Para operar en menos de 1 KB de RAM sin desbordar la pila de llamadas (stack) del procesador 6502, Jennings ideó un algoritmo simplificado basado en variaciones
de Minimax con poda Alpha-Beta rudimentaria: [1] (https://fvcalderan.github.io/myworks/articles/minimax_chess_engine.pdf), [2] (https://chessprogramming.org/MicroChess)

En un Árbol de Búsqueda (Búsqueda por Plies), Microchess calculaba usualmente hasta 3 plies de profundidad (3 medios movimientos: Jugada CPU \(\rightarrow \) Respuesta Humana \(\rightarrow \) Réplica CPU).
[1] (https://en.wikipedia.org/wiki/Microchess), [2] (https://translate.google.com/translate?u=https://en.wikipedia.org/wiki/Microchess&hl=es&sl=en&tl=es&client=sge)

* Generación de movimientos: El motor barría las piezas secuencialmente para encontrar movimientos legales.
* Inversión de Tablero (Board Reversing): Para ahorrar código de evaluación duplicado para blancas y negras, el programa "espejaba" o invertía internamente el tablero para
que el bando que estuviera calculando siempre fuera evaluado desde la misma perspectiva algorítmica. [1] (https://chessprogramming.org/MicroChess)

Se utilizaba una función de *Evaluación Estática* de manera que cuando el motor alcanzaba el límite de profundidad, ejecutaba una asignación de puntos
preinicializada de 16 bytes que tasaba el valor de las piezas en unidades de medio peón:


|Pieza|	Valor en Microchess (Medios Peones)|
|-----|------------------------------------|
|Rey	|11|
|Reina	|10|
|Torre	|6|
|Alfil	|4|
|Caballo|	4|
|Peón	|2|

A este valor material estático se le sumaban sutiles bonificaciones posicionales basadas en la movilidad (cuántas casillas libres tenía una pieza para moverse)
y la ocupación del centro del tablero. El movimiento con la puntuación final ponderada más alta (Minimax) era el seleccionado. [1] (https://benlo.com/microchess/)

#### Evaluación Comparativa de Potencia Ajedrecística

Microchess debe ser juzgado bajo el prisma de su contexto técnico:

|Criterio                    |	Microchess (1976)            |	Sargon (1978) / Sargon II (1979) |	Motores Modernos (Ej. Stockfish) |
|----------------------------|-------------------------------|-----------------------------------|---------------------------------------|
|Fuerza Estimada (Elo)	     |~1100 Elo (Nivel Principiante) |~1500 - 1800 Elo (Nivel Club)      |	>3500 Elo (Superhumano)          |
|Profundidad de Búsqueda     |Hasta 3 plies                  |	4 - 6 plies habitualmente        |	>30 plies con facilidad          |
|Consumo de Memoria	     |< 1 KB RAM                     |~8 KB - 16 KB RAM	                 |  Gigabytes de Tablas de Transposición |
|Reglas Soportadas	     |Básicas (algunas omisiones)    |	Ajedrez Completo                 | 	Ajedrez Completo e IA            |

Daría la impresión, desde ésta perspectiva que MicroChess no es mucho mas que una bonita referencia histórica, sin embargo hay un aspecto que no ha podido ser batido,
con esa arquitectura moderna era (¿es?) capaz de aportar aproximadamente un punto ELO por bit, Sargón aporta aprox. 0.09 puntos ELO por bit y Stockfish, con todo lo
impresionante que es, aporta 0.0000035 puntos ELO por bit. El sistema ELO, del cual nos ocuparemos en detalle mas adelante, es de naturaleza logaritmica, pero aún asi
la performance de MicroChess es impresionante. Algunas ideas generales han sido utilizadas posteriormente en éste trabajo.


#### Desempeño y Limitaciones

A nivel de juego puro, la crítica de la época y los historiadores posteriores (como Tim Harding) llegaron a catalogar el juego de Microchess como "terrible" en comparación con lo que vendría después. El motor cometía despistes graves y tácticos debido a su corta profundidad de cálculo y a que omitía cálculos complejos de finales. [1] (https://translate.google.com/translate?u=https://en.wikipedia.org/wiki/Microchess&hl=es&sl=en&tl=es&client=sge)
Sin embargo, su potencia radicaba en la eficiencia. Mientras que competidores posteriores como Sargon requerían máquinas mucho más caras con al menos 8K o 16K de memoria, Microchess demostró que la optimización de código extrema podía suplir la falta de hardware, convirtiéndose en una leyenda irrepetible de la ingeniería informática. [1] (https://www.schach-computer.info/wiki/index.php?title=Jennings,_Peter_En), [2] (https://translate.google.com/translate?u=https://en.wikipedia.org/wiki/Microchess&hl=es&sl=en&tl=es&client=sge)

Sería interesante estudiar en mas detalle un fragmento de su código fuente en ensamblador 6502, ver cómo resolvía problemas específicos como el enroque o la promoción o
incluso  saber más sobre el duelo histórico entre Bobby Fischer y el Commodore ChessMate basado en este software?
Pero dejamos las cuestiones técnicas para mas adelante, cuando las analizaremos con algún detalle.


## Sargon: the old buddy (1978/1979)

[FOTOGRAFIA DE SARGON]

Sargón fue el primer motor de juego para ajedrez automático relativamente completo comercialmente accesible, si bien existieron esfuerzos anteriores estaban normalmente
implementados en grandes plataformas de cómputos (mainframe, VAX y otras) que tenían escasas opciones de accederlas. 
**Sargon** fue desarrollado por **Dan y Kathe Spracklen** y presentado en 1978. Ese año ganó las cinco partidas del torneo de ajedrez para microcomputadoras
celebrado en la **West Coast Computer Faire**, uno de los primeros hitos competitivos del ajedrez en computadoras personales.
Su importancia no radica en haber inventado la búsqueda ajedrecística, sino en demostrar que una microcomputadora de 8 bits, con memoria y potencia muy limitadas, podía
ejecutar un jugador competitivo para su época. También contribuyó a popularizar el ajedrez informático entre aficionados y programadores.
Sargon fue escrito en **lenguaje ensamblador Z80**. Según la descripción de sus autores, ocupaba aproximadamente **8 KB de RAM**, distribuidos en unos 4 KB de lógica de juego,
2 KB de datos y 2 KB de interfaz gráfica.

Sus principales componentes eran:

- Representación del tablero y generación de movimientos:** rutinas especializadas por pieza, con comprobaciones de legalidad, jaques, enroque y captura al paso.
- **Búsqueda:** exploración en profundidad de un árbol de movimientos mediante **poda alfa-beta**, para descartar ramas que no podían mejorar la decisión.
- **Evaluación:** puntuación heurística de las posiciones, basada en material y consideraciones ajedrecísticas; incluía análisis de intercambios para reducir errores tácticos con un costo computacional contenido.
- **Interfaz:** visualización del tablero e interacción con el usuario, adaptadas a las capacidades de los equipos de la época.

No utilizaba redes neuronales ni aprendizaje automático: sus decisiones procedían de reglas, búsqueda y evaluación diseñadas explícitamente.
Sargon ayudó a consolidar el ajedrez como demostración práctica de **búsqueda heurística en hardware restringido**.
El libro *Sargon: A Computer Chess Program* (1978)[LINK], que incluía su código fuente comentado, facilitó el estudio, la adaptación y la enseñanza de técnicas de programación
de motores de ajedrez.
La familia Sargon tuvo posteriores versiones y adaptaciones para diversas computadoras personales.
Su legado resulta especialmente relevante para proyectos contemporáneos que combinan motores clásicos y evaluadores neuronales: permite observar qué aporta
la búsqueda y qué aporta el mecanismo de evaluación, dos componentes conceptualmente separables. En algún sentido es el punto de partida para muchas de las iniciativas que
se describen en el resto de éste material y de hecho se constituye en la "referencia" al momento de hacer evaluaciones preliminares de la fuerza ajedrecística de un enfoque.

### Fuentes

- Computer History Museum, [*Sargon: A Computer Chess Program*](https://www.computerhistory.org/chess/sft-431614f63c4c4/).
- Dan y Kathe Spracklen, [*Sargon: A Computer Chess Program* (1978), texto y listado histórico](https://chessforeva.bitbucket.io/govs/Oldies/Sargon.htm).
- Computer History Museum, [Dan y Kathe Spracklen en el campeonato ACM de 1978](https://www.computerhistory.org/chess/stl-431f4cc14ba4b/).


# La arquitectura

En la arquitectura se resume todo lo que tiene que tener una plataforma, y también lo que no va a tener nunca. Es en cierta
medida el contrato intelectual o técnico de lo que se quiere conseguir con un desarrollo.

Es posible que los objetivos que se persiguen difieran, incluso substancialmente, de los objetivos de otros desarrolladores.

A sus ojos ésta plataforma puede lucir muy poco atractiva, de bajo poder o incluso no totalmente necesaria.

Sin embargo hay algunos desafíos técnicos, que de alcanzarse, permitirán considerar el resultado un aporte original.

La plataforma combina motores de ajedrez, con sistemas embebidos, con técnicas avanzadas de optimización. En muchos casos
será *un perro que canta tangos* , no es maravilloso como lo hace, sino el mero hecho que lo haga.

## El desafío

El contexto de los motores de ajedrez ha evolucionado significativamente en la medida que aparecen plataformas mas veloces
y algoritmos mas novedosos. O meramente algoritmos que eran impensables en una plataforma Z80 de 8 bits y pocos K de memoria RAM
son ahora triviales en un procesador de 64 bits con 32 GBytes de memoria y acceso a un procesador GPU de alta potencia, es una
cuestión de perspectiva.

Pero en la esencia el problema no es, una vez actualizado, diferente a como lo planteo Claude Shannon, sigue habiendo dos
tipos de algoritmos de juego

* la Tipo A (fuerza bruta, evaluar todas las jugadas posibles)
* la Tipo B (búsqueda selectiva, evaluar solo las mejores jugadas).

Y los dos tipos han evolucionado. Los de *Tipo A* se han rendido ante la evidencia de un juego que logra presentar el
formidable desafío de $10^{130}$ combinaciones a explorar, imposible.

**Claude Shannon** lo formuló como una famosa analogía basada en sus conclusiones elementales: 
si convirtiéramos cada uno de los átomos del universo observable (aproximadamente \(10^{80}\)) en una supercomputadora
—incluso en un computador cuántico operando a la máxima velocidad permitida por las leyes de la física— y
las pusiéramos a calcular combinaciones desde el Big Bang hasta hoy, apenas habrían analizado una fracción infinitesimal
del total.

Sin embargo el enfoque de fuerza bruta es abordable si se limita el *horizonte* dentro del cual se analizan las jugadas
posibles; planteado de ésta forma el problema pasa a ser que tan lejos permite el algoritmo y la tecnología mover ese horizonte
hacia el futuro. 

**MicroChess** o **Sargon** hacen eso, aplican un método **minimax alpha/beta* para tratar de reducir el árbol de posibilidades
y, en un tiempo objetivo que se considere razonable examnar la mayor cantidad de jugadas posibles y elegir la mejor. Esos motores
en sus ambientes de hardware originales no podían hacerlo mas que dos jugadas hacia adelante, hoy en hardware moderno el mismo
algoritmo puede analizar hasta 7 u 8 jugadas hacia adelante. Pero alli aparece la siguiente limitación, como evaluamos el 
posible valor de cada jugada comparada con otras. Aparecen los otros componentes de la estrategia, el valor de la i-esima
posición **Valor ($V_i$)** y la **Política ($P_i$ o $\pi_{i}$), es decir que capacidad tiene una jugada para darme el mayor
beneficio (usualmente tratar de ganar la partida) y entre las posibles cual es el criterio para elegir una movida en lugar de
otra.

**MicroChess** o **Sargon** tenían analisis muy simplificados basado en una heurística determinada que asigna valor a las 
piezas, a la ocupación de ciertos sectores del tablero y a la chance que en la próxima jugada ocurra algo relevante (tal como
comer una pieza de mas valor o dar jaque mate). Pero como es de imaginar heurísticas de ese tipo son relativamente limitadas.

Básicamente capturan la **"ideología"** ajedrecistica de quien las formula, sus preferencias si se quiere. Pero ciertamente es
dudoso que provengan de un experto jugador a nivel *Maestro* o *Gran Maestro*. Como resultado estas estrategias sorprenden a
un jugador casual, que quizás no realiza análisis de esa profundidad o con alguna heurística simple pero robusta, pero rara
vez pueden sorprender, mucho menos ganar a un jugador de cierto nivel.

En la medida que la potencia de cálculo aumentó se desarrollan casi concurrentemente algoritmos sofisticados que permiten
explorar mas posiciones o seleccionar aquellas posiciones mas prometedoras respecto a otras y al mismo tiempo algoritmos 
mas complejos para obtener el material para decidir que jugada es mejor que otra ($V_i$) y que jugada será mejor seleccionar
como movida propia $\pi_{i}$.

El epítome de fuerza bruta fue el programa *Deep Blue*, fue una supercomputadora de ajedrez desarrollada por IBM que hizo historia al convertirse en el
primer sistema informático en derrotar a un campeón del mundo vigente,  Garry Kasparov, en un encuentro con ritmo de juego de torneo.
Su desarrollo comenzó a finales de los años 80 bajo el nombre de ChipTest y luego Deep Thought en la
Universidad Carnegie Mellon, de la mano de los científicos Feng-hsiung Hsu y Murray Campbell,
quienes posteriormente fueron reclutados por IBM para culminar el proyecto.

¿Cómo funcionaba y en qué se basaba? 

A diferencia de la Inteligencia Artificial moderna basada en redes neuronales y aprendizaje autónomo
(como AlphaZero, al que veremos luego), Deep Blue funcionaba mediante fuerza bruta computacional combinada con reglas heurísticas.

* Poder de procesamiento masivo:
 Consistía en un superordenador masivamente paralelo compuesto por dos torres de dos metros de altura que
 albergaban más de 500 procesadores y 216 chips aceleradores específicamente diseñados para calcular movimientos de ajedrez.
* Velocidad de cálculo:
 La versión de 1997 era capaz de analizar y evaluar hasta 200 millones de posiciones por segundo.
* Algoritmo de búsqueda (Minimax):
 Calculaba los árboles de decisiones explorando masivamente las opciones de jugadas hacia adelante
 (profundidad de cálculo) y seleccionaba la mejor opción asumiendo que el rival también elegiría su mejor jugada.
* Función de evaluación humana:
 Para decidir si una posición final en su cálculo era "buena" o "mala", utilizaba una función programada
 con conocimientos conceptuales de ajedrez (valor de las piezas, seguridad del rey, estructura de peones, espacio).
 El equipo contó con la asesoría de Grandes Maestros de ajedrez para afinar esta base de datos y su libro de aperturas.

En esencia se trata de cantidades masivas de potencia de cálculo para explorar millones de jugadas por segundo (**Sargon**
puede, en un día bueno explorar algunos miles a 2 jugadas hacia adelante) pero usando el algoritmo *minimax* y una funcion
de ($V_i$) y  $\pi_{i}$ dada por una combinación de posiciones recordadas y comparadas de partidas pasadas y preferencias
de los entrenadores. El programa nunca se hizo público y solo se dispone de descripciones superficiales de su funcionamiento.

Pero estaba claro que el enfoque de *Deep Blue* ponía el sendero de la fuerza bruta muy lejos de la disponibilidad habitual
de experimentadores con menos recursos.

La evolución progresó hasta la disponibilidad moderna de programas como *stockfish* [LINK] que puede mostrar niveles de juego
que solo los grandes maestros puede batir, a veces.

Este programa, y algunos similares, pueden funcionar en computadores modernos, los que de por si son bastante mas poderosos
que en la época de *Deep Blue* vs. Kasparov, con algoritmos muy especializados para reducir el espacio de exploración y con
heurísticas mas sofisticadas para evaluar las movidas. El resultado es que *stockfish* puede evaluar el equivalente a 20 o 
30 jugadas hacia adelante en sus versiones mas extremas (las hay menos potentes). Recientemente, luego de la irrupción de
algoritmos como *AlphaZero* basado en redes neuronales *stockfish* también abraza el uso de técnicas de inteligencia 
artificial para mejorar sus capacidades de exploración y valoración de jugadas. 

Pero todos los métodos explorados, y algunos mas no mencionados, se caracterizan por ser pertenecientes a la familia de 
*fuerza bruta*, pero que hay de la otra familia los de *busqueda selectiva*?

Por cierto que tambien hay exponentes en ésta familia, algunos muy famosos.

## AlphaZero

[FOTO DE ALPHAZERO-KASPAROV]

AlphaZero es un programa de Inteligencia Artificial desarrollado por Google DeepMind que revolucionó los juegos
de mesa de estrategia (ajedrez, shogi y go) al aprender a dominarlos de forma completamente autónoma.
A diferencia de los motores tradicionales que dependen del conocimiento acumulado por humanos durante siglos,
AlphaZero aprendió a jugar partiendo de cero, jugando millones de partidas contra sí mismo utilizando únicamente
las reglas básicas del juego.
AlphaZero nació a finales de 2017 en los laboratorios de Google DeepMind, la división de IA de Google. Es la evolución directa de AlphaGo (la IA que derrotó al campeón mundial del milenario juego de Go) y AlphaGo Zero.
El equipo de DeepMind, liderado por Demis Hassabis, adaptó este sistema para crear un algoritmo más generalizado y aplicable a múltiples juegos complejos, publicando un histórico artículo científico donde demostraron que, en pocas horas de autoaprendizaje, la IA podía destruir a los campeones mundiales informáticos de ajedrez (Stockfish) y shogi (Elmo).
AlphaZero no utiliza la "fuerza bruta" de los ordenadores tradicionales ni funciones de evaluación programadas por humanos. Se basa en dos pilares tecnológicos:
* Redes Neuronales Profundas:
 Tiene una red que evalúa las posiciones del tablero y otra que predice cuáles son  las jugadas más prometedoras. 
 En lugar de calcular millones de variantes absurdas, AlphaZero utiliza una intuición artificial similar a la
 humana para enfocarse solo en las mejores líneas.
* Aprendizaje por Refuerzo (Tabula Rasa): 
 El programa comenzó sabiendo únicamente las reglas del ajedrez.
 Jugó contra copias de sí mismo a una velocidad asombrosa. 
 Al principio hacía movimientos aleatorios, pero la red neuronal se iba actualizando tras cada partida,
 aprendiendo qué estrategias llevaban a la victoria y cuáles a la derrota.
 En solo 4 horas de autoentrenamiento en ajedrez, superó el nivel de Stockfish (en ese momento).
* Búsqueda de Árboles de Monte Carlo (MCTS):
 En vez del algoritmo clásico Minimax que analiza posiciones de forma simétrica a gran profundidad,
 AlphaZero utiliza *Monte Carlo Tree Search (MCTS)* para simular los resultados más probables, 
 calculando "solo" unas 80,000 posiciones por segundo (frente a los 70 millones de Stockfish), pero con una precisión
 y calidad estratégica radicalmente superiores.

*AlphaZero* no es un software comercial ni de código abierto; fue un proyecto de investigación científica interna 
de Google y no está disponible para que el público general lo descargue o lo use en su computadora.
Sin embargo, el mundo del ajedrez no se quedó de brazos cruzados, el proyecto *Leela Chess Zero (Lc0)* resultó del esfuerzo 
de una comunidad de ajedrez y programadores la que creó este proyecto de código abierto para replicar primero 
el funcionamiento de AlphaZero y luego extenderlo.
*Lc0* se entrena gracias a la potencia comunitaria de miles de usuarios que prestan sus tarjetas gráficas (GPUs).
Cualquier aficionado puede descargar Lc0 de forma gratuita, conectarlo a una interfaz (como Arena o ChessBase)
y usarlo en su propia PC para analizar partidas con el "estilo AlphaZero".
El estilo de AlphaZero cambió para siempre la teoría del ajedrez moderno debido a sus marcadas diferencias con los motores clásicos:

| Característica	| Motores Tradicionales (Ej. Stockfish clásico)	| AlphaZero / Motores de Red Neuronal|
|-----------------------|-----------------------------------------------|------------------------------------|
|Origen del conocimiento|	Heurísticas y conceptos de estrategia programados por Grandes Maestros humanos.| Aprendizaje autónomo absoluto jugando contra sí mismo|
|Velocidad de cálculo	|Brutal. Evalúa decenas o cientos de millones de posiciones por segundo.| Eficiente. Evalúa decenas de miles de posiciones por segundo, pero muy selectas.|
|Estilo de juego	|Ultra-calculador, materialista, defensivo y busca la perfección táctica concreta.|Profundamente posicional, intuitivo, dinámico y famoso por sacrificar piezas a largo plazo por iniciativa.|
|Hardware ideal		|Procesadores comunes (CPU).	|Tarjetas gráficas de alta potencia o procesadores de IA (GPU / TPU)|

El éxito de AlphaZero fue tan rotundo que obligó a los motores tradicionales a evolucionar, hoy en día, el propio Stockfish
ya no es puramente tradicional pues adoptó la tecnología de redes neuronales (llamada *NNUE*) fusionando lo mejor de la
fuerza bruta clásica con la enorme comprensión estratégica inspirada por AlphaZero.

Se explorarán algunos de los algoritmos involucrados en la medida que se discutan implementaciones concretas, pero lo cierto
es que claramente define una posible estrategia para un recorrido de aprendizaje y comprensión.

Carece de sentido tratar de emular o superar a *stockfish* (o por caso a *AlphaZero*), es un esfuerzo de muchas personas,
con enormes recursos materiales, de tiempo y tecnológicos por lo que tratar de conseguir algo distinto
es un desafío que requiere calibrar los recursos disponibles.

## Stockfish

[FOTO DE STOCKFISH]

Ese enfoque, al no competir con *stockfish*, lleva a preguntarse cual es el diferenciador de éste proyecto.

La respuesta no es lineal ni simple, siquiera quizás robusta. 

Se trata de aprender, explorar, comprender y eventualmente aplicar técnicas conocidas para familiarizarse con ellas,
y quizás encontrar estrategias que permitan aplicarlas en computadores mas simples y de mucha menos potencia en forma efectiva.
microcontroladores, problema de optimización de performance. O quizás solo haber disfrutado el camino de aprendizaje.

# Planteo conceptual

El planteo conceptual es determinar que componentes, sub-sistemas o módulos, tendrá
la implementación para permitir ayudar en los objetivos y luego definir como se
conectarán entre si aplicando que convenciones.

[AQUI VIENE UN DIAGRAMA]

Los objetivos van mutando con el aprendizaje, por lo tanto es mas facil contarlos 
cuando el proyecto esté terminado que al comenzar. 
Pero si se puede describir el punto de partida y la idea general.

* Explorar los distintos algoritmos.
* Entender las interacciones entre ellos.
* Experimentar el problema de ajedrez como compuesto de dos partes:
  * Explorar el valor de las jugadas que son factibles.
  * Evaluar que criterios se pueden usar para determinar la mejor.
* Probar que combinación da una performance razonable en ambientes muy pequeños.
* Desarrollar un protocolo de evaluación de los distintos enfoques propuestos.

Uno de los aprendizajes mas tempranos consiste en comprender como es el ciclo de vida
de un determinado esquema de juego, el que podría resumirse en algunos pasos que
se repiten:

* Se parte de una idea o estrategia para medir $V_i$ y $\pi_{i}$
* Implementarlo.
* Encontrar la forma de calibrarlo o entrenarlo.
* Probar el funcionamiento básico (**dry run**).
* Entender la performance y la capacidad de exploración que tiene.
* Calibrar la potencia relativa de cada algoritmo respecto a los restantes.
* Tomar alguna medida objetiva del potencial *"ajedrecistico"* que tiene.
* Optimizar la performance.
* Mover a las distintas plataformas, repetir la evaluación.
* .... tomar el siguiente 

Finalmente, 

¿como evaluar si una estrategia es "*suficientemente buena*" para declararla exitosa?

Esta determinación está plagada de intangibles, pero a los efectos de éste proyecto se tomará el criterio de *fortaleza competitiva recíproca* 

'''
Una combinación de algoritmos de evaluación y juego será mejor que otra cuando en competencia recíproca muestre tener un ELO relativo superior.
'''

Y un criterio de *aceptabilidad*

'''
Un motor será aceptable a los efectos de la experimentación cuando tenga un ELO superior al de un algoritmo Sargón histórico.
'''

Se verá mas adelante los mecanismos de medición de fortaleza ajedrecistica relativa,
en particular el sistema ELO.

Pero, para poder progresar, es necesario entender que es el ajedrez primero.

## Las reglas del ajedrez

Para poder adentrarse en el desarrollo de un motor es claro que debe asegurarse que los algoritmos (*motores*) utilizados cumplan algunas reglas del ajedrez en cuanto a como conducir las partidas y como realizar el movimiento de las piezas.

El ajedrez es un juego de estrategia para dos jugadores (blancas y negras) cuyo objetivo principal es dar jaque mate al rey adversario.
A continuación, tienes un resumen claro y estructurado de sus componentes y reglas fundamentales basadas en el reglamento oficial de la Federación Internacional de Ajedrez (FIDE):

### El Tablero (El Casillero)

El tablero de ajedrez es una cuadrícula perfecta de 8x8 casillas, alternadas en colores claros y oscuros, sumando un total de 64 casillas.
• Orientación: Se coloca de forma que cada jugador tenga una casilla clara (blanca) en su esquina inferior derecha ("blanca a la derecha").
• Columnas: Las líneas verticales se identifican con letras de la a a la h.
• Filas: Las líneas horizontales se identifican con números del 1 al 8.

###♟️ Cantidad y Tipo de Piezas

Cada jugador comienza la partida con un ejército de 16 piezas (32 piezas en total sobre el tablero).

|Pieza		|Cantidad por jugador	|Valor sugerido (en puntos)|
|---------------|-----------------------|--------------------------|
|Peón		|8			|1	                   |
|Caballo	|2			|3                         |
|Alfil		|2         		|3                         |
|Torre		|2			|5		           |
|Dama (Reina)	|1			|9                         |
|Rey		|1			|Infinito (Invalorable)    |

El valor sugerido de las piezas es un factor que tiene que tomarse, como mucho, ligeramente. El real valor de una
pieza es su fuerza táctica en un contexto de juego determinado. Cada pieza tiene bondades y debilidades estratégicas
pero su valor depende del contexto. Por ejemplo, un peon a un paso de *coronar* no vale 1, aunque todavía no vale 
tanto como una Dama.


### Movimiento de las Piezas

Ninguna pieza puede saltar sobre otra, a excepción del caballo. Tampoco pueden ocupar una casilla donde ya haya una pieza de su propio color.

* ♟️ Peón: Avanza una casilla hacia adelante por turno. En su primer movimiento de la partida, tiene la opción de avanzar dos casillas. Captura en diagonal, avanzando una casilla hacia la izquierda o derecha. Nunca puede retroceder.
* ♞ Caballo: Se mueve en forma de "L" (dos casillas en una dirección y luego una en perpendicular). Es la única pieza que puede saltar sobre otras piezas.
* ♝ Alfil: Se mueve en línea recta por las diagonales tantas casillas como quiera. Cada jugador tiene un alfil para casillas claras y otro para oscuras.
* ♜ Torre: Se mueve en línea recta por las filas y columnas (horizontal y vertical) tantas casillas como desee.
* ♛ Dama: Es la pieza más poderosa. Puede moverse cualquier número de casillas en cualquier dirección: horizontal, vertical o diagonal.
* ♚ Rey: Se mueve solo una casilla en cualquier dirección. Es la pieza que se debe proteger a toda costa.


### Condiciones de Terminación de la Partida

Una partida de ajedrez termina cuando ocurre alguna de las siguientes situaciones:

* Victoria (Ganar la partida)

	* Jaque Mate: El rey de un jugador está bajo ataque directo (en jaque) y no tiene ningún movimiento legal para escapar, cubrirse o capturar a la pieza atacante.
	* Abandono: Un jugador decide rendirse de forma voluntaria al ver que su posición es indefendible.
	* Por tiempo: En partidas con reloj, si a un jugador se le agota el tiempo asignado, pierde automáticamente (siempre que el rival tenga material suficiente para dar mate).

* Tablas (Empate)

	* Ahogado: Es el turno de un jugador cuyo rey no está en jaque, pero no puede realizar ningún movimiento legal con ninguna de sus piezas en el tablero.
	* Insuficiencia de material: Ninguno de los dos bandos tiene piezas suficientes para forzar un jaque mate (por ejemplo: Rey contra Rey, o Rey y Caballo contra Rey).
	* Triple repetición: La misma posición exacta del tablero se repite tres veces durante la partida.
	* Regla de los 50 movimientos: Pasan 50 jugadas consecutivas de cada jugador sin que se haya movido un solo peón ni se haya capturado ninguna pieza.
	* Mutuo acuerdo: Ambos jugadores deciden y acuerdan que la partida es un empate.

### Modalidades de juego

Las modalidades en el ajedrez se definen principalmente por el control de tiempo asignado a cada jugador para toda la partida. Cuanto menos tiempo hay, el juego pasa de ser puramente estratégico y profundo a volverse un ejercicio de reflejos, intuición y pura táctica.
De acuerdo con el reglamento oficial de la FIDE y las principales plataformas en línea (como Chess.com y Lichess), las modalidades se dividen de la siguiente manera:

#### ⏱️ Modalidades Oficiales de Ritmo Corto/Medio

* Ajedrez Clásico (Pensado): Es el formato tradicional de los torneos de élite. Cada jugador suele tener 90 minutos o más para las primeras 40 jugadas, muchas veces con un "incremento" (segundos extra que se añaden al reloj tras cada movimiento). Las partidas pueden durar entre 3 y 7 horas, priorizando la máxima precisión y profundidad estratégica.
* Ajedrez Rápido (Rapid): Un punto medio ideal. El tiempo asignado es de más de 10 minutos pero menos de 60 minutos por jugador. Es un ritmo muy popular en torneos híbridos porque exige calcular rápido sin perder por completo la calidad de las jugadas.
* Blitz (Relámpago): Una de las modalidades más populares y frenéticas. El tiempo total es de 10 minutos o menos por jugador (el estándar más común es 3 minutos con 2 segundos de incremento, o 5 minutos limpios). Aquí los errores tácticos son frecuentes y el manejo del reloj es vital.

#### 🚀 Modalidades Ultra Rápidas y En Línea

* Bullet (Bala): El tiempo es extremadamente escaso, usualmente menos de 3 minutos para toda la partida (el ritmo rey es 1 minuto por jugador). No hay tiempo para pensar; se juega por puro instinto, memoria muscular y velocidad con el ratón o la pantalla táctil.
* Hyperbullet / Ultrabullet: Modalidades exclusivas de internet donde el tiempo es de 30 o 15 segundos en total por jugador. Ganar por tiempo ("relojear" al rival) es casi más importante que dar jaque mate.

#### 📆 Modalidades de Ritmo Extendido o Asincrónico

* Ajedrez por Correspondencia: El extremo opuesto al Bullet. Los jugadores tienen días o semanas para hacer un solo movimiento. Antiguamente se jugaba por correo postal; hoy se realiza mediante servidores web. Permite un análisis profundo, científico y casi perfecto de la posición.

#### 🎭 Variantes Populares del Juego (Cambios de Reglas)

Además del tiempo, existen modalidades donde cambias las reglas o la configuración inicial del tablero:

* Ajedrez 960 (Fischer Random): Creado por el campeón mundial Bobby Fischer. Las reglas de movimiento son las mismas, pero la posición de las piezas en la primera fila se sortea aleatoriamente antes de empezar (manteniendo los peones al frente). Existen 960 combinaciones posibles. Su objetivo es anular la memorización de aperturas teóricas.
* Pasapiezas (Bughouse): Se juega en parejas (dos tableros contiguos). Cuando capturas una pieza del rival, se la pasas a tu compañero, quien en su turno puede elegir entre mover una de sus piezas o "soltar" la pieza capturada en cualquier casilla vacía de su propio tablero.
* Ajedrez a la Ciega (Blindfold): Los jugadores disputan la partida sin ver el tablero ni tocar las piezas. Deben llevar la posición en su mente y cantar sus jugadas utilizando la notación algebraica (ej. "e4", "Cc3").

### Fortalezas y debilidades 

Desde el punto de vista táctico, cada pieza tiene una "personalidad" única definida por su geometría de movimiento. Entender sus ventajas y limitaciones te permite coordinarlas mejor en el tablero:

* ♟️ El Peón

	* Fortalezas: Son el "alma del ajedrez". Sirven como un escudo protector para tu propio rey, son excelentes para reclamar y controlar espacio en el centro, y son ideales para crear cadenas defensivas difíciles de romper. Su mayor fortaleza táctica es la promoción: si un peón llega al final, se transforma en Dama.
	* Debilidades: Son las piezas menos móviles y nunca pueden retroceder. Cada vez que avanzas un peón, dejas casillas débiles ("huecos") detrás de él que jamás podrá volver a defender.

* ♞ El Caballo

	* Fortalezas: Su movimiento en "L" le permite saltar sobre otras piezas, lo que lo convierte en el rey de las posiciones cerradas o bloqueadas. Es letal ejecutando dobletes (atacar dos piezas a la vez sin que ninguna pueda bloquear el ataque) y puede ubicarse en casillas fuertes del campo enemigo donde los peones rivales ya no lo puedan expulsar.
	* Debilidades: Tienen un alcance muy corto y tardan varios turnos en trasladarse de un lado al otro del tablero. En los bordes o esquinas pierden hasta el 75% de su potencia defensiva y de ataque.

* ♝ El Alfil

	* Fortalezas: Tienen un gran alcance a larga distancia y brillan en posiciones abiertas donde no hay peones estorbando. Son excelentes para clavar piezas enemigas y pueden cortar el tablero por la mitad controlando diagonales enteras desde la distancia.
	* Debilidades: Están limitados a la mitad del tablero, ya que un alfil que empieza en casillas claras jamás podrá tocar o defender una casilla oscura. Si la estructura de peones bloquea sus diagonales, se convierte en un "alfil malo", atrapado detrás de sus propias líneas.

* ♜ La Torre

	* Fortalezas: Tienen una enorme potencia en el final de la partida. Su objetivo táctico es dominar columnas abiertas (líneas verticales sin peones) para infiltrarse en la séptima u octava fila enemiga, donde suelen arrasar con los peones rezagados del rival.
	* Debilidades: Al inicio de la partida suelen estar atrapadas y desconectadas en las esquinas. Necesitan que el tablero se vacíe un poco o que los peones se muevan para poder activar su tremendo poder a larga distancia.

* ♛ La Dama

	* Fortalezas: Combina la fuerza de la Torre y el Alfil, lo que la convierte en la fuerza ofensiva más destructiva del juego. Su versatilidad la hace perfecta para crear ataques dobles, dar jaques continuos y castigar instantáneamente cualquier error de cálculo o casilla desprotegida del rival.
	* Debilidades: Es tan valiosa que no puede exponerse temprano en la partida. Si la sacas antes de tiempo, las piezas menores del rival (caballos y alfiles) la atacarán constantemente para ganar turnos de desarrollo mientras tú te ves obligado a moverla para salvarla.

* ♚ El Rey

	* Fortalezas: En la fase inicial y media es una pieza puramente defensiva, pero en el final de la partida se transforma en un atacante activo. Al quedar pocas piezas, el rey debe centralizarse para escoltar a sus propios peones hacia la promoción o frenar el avance de los peones rivales.
	* Debilidades: Su vulnerabilidad es absoluta durante la mayor parte del juego. Al moverse solo una casilla, es fácil de arrinconar o rodear si no cuenta con un enroque seguro o un escudo sólido de peones.


## Notaciones

[TABLERO CON REFERENCIA]

Las notaciones en el ajedrez son los sistemas de escritura utilizados para registrar los movimientos de una partida. Esto permite recrear juegos históricos, estudiar teoría, publicar libros y permitir que las computadoras procesen el juego.
A lo largo de la historia han existido varios sistemas, pero hoy en día la Notación Algebraica es el estándar internacional oficial de la FIDE.
A continuación, te presento una descripción detallada con ejemplos de los métodos de notación más importantes.

### Notación Algebraica (El Estándar Moderno)

Este sistema trata al tablero como un plano cartesiano. Es el único sistema legal en torneos oficiales.

La Geometría del Tablero:

* Columnas (verticales): Se nombran con letras de la a a la h (de izquierda a derecha desde la perspectiva de las blancas).
* Filas (horizontales): Se nombran con números del 1 al 8 (desde la primera fila blanca hasta la octava fila negra).
* Casillas: Cada una tiene una dirección única uniendo su letra y número (ej. e4, c6, h8).

Identificación de las Piezas (en español):

Se utiliza la letra inicial mayúscula de la pieza. Los peones ♟️ no tienen letra; si solo se escribe la casilla, se entiende que se movió un peón.

* ♚ R = Rey
* ♛ D = Dama
* ♜ T = Torre
* ♝ A = Alfil
* ♞ C = Caballo

### Reglas de Escritura y Símbolos Especiales:

* Movimiento simple: Letra de la pieza + casilla de destino. (Ej: Cf3 significa "Caballo a la casilla f3").
* Movimiento de peón: Solo la casilla de destino. (Ej: e4 significa "Peón a la casilla e4").
* Captura: Se intercala una x entre la pieza y la casilla de destino. (Ej: Axb5 significa "Alfil captura en b5").
* Captura de peón: Se indica la columna de origen del peón, la x, y la casilla de destino. (Ej: exd5 significa "Peón de la columna e captura en d5").
* Jaque: Se añade un signo de más (+) al final de la jugada. (Ej: Dh5+).
* Jaque Mate: Se añade un signo de almohadilla o doble más (# o ++). (Ej: Dh7#).
* Enroque corto (flanco de rey): Se escribe 0-0.
* Enroque largo (flanco de dama): Se escribe 0-0-0.
* Promoción de peón: Se escribe la casilla de destino y la inicial de la pieza elegida. (Ej: e8=D).

### ⚠️ Resolución de Ambigüedades:

Si dos piezas idénticas (como dos caballos) pueden ir a la misma casilla, se debe especificar de dónde venía el que se movió, añadiendo su columna o fila de origen.
• Ejemplo: Si tienes caballos en f3 y d2, y ambos pueden ir a e4: si mueves el de f3, escribes Cfe4. Si estuvieran en la misma columna (ej. d2 y d4) y van a e4, escribes C2e4.

### Formato PGN (Portable Game Notation)

Es el estándar digital derivado de la notación algebraica. Es el formato de texto plano que leen páginas como Chess.com, Lichess o programas como ChessBase para guardar bases de datos de partidas.
Utiliza la notación algebraica pero siempre con las iniciales de las piezas en inglés (K=King, Q=Queen, R=Rook, B=Bishop, N=Knight) para que sea universal. Además, agrupa los metadatos de la partida entre corchetes antes de las jugadas.

Ejemplo real de un archivo PGN (El famoso "Mate del Pastor"):

text
[Event "Partida Amistosa"]
[Site "Mar del Plata, ARG"]
[Date "2026.10.31"]
[White "Jugador Blanco"]
[Black "Jugador Negro"]
[Result "1-0"]

1. e4 e5 2. Ac4 Cc6 3. Dh5 Cf6 4. Dxf7# 1-0
Usa el código con precaución.

### Notación Descriptiva (El Sistema Antiguo)

Fue el sistema dominante en los países de habla hispana e inglesa hasta la década de 1980. Si abres un libro de ajedrez viejo, estará escrito así. Es mucho más complejo porque las casillas cambian de nombre según quién esté jugando.

Reglas principales:

* Las columnas no se llaman de la 'a' a la 'h', sino por el nombre de la pieza que la ocupa al inicio: TD (Torre Dama), CD (Caballo Dama), AD (Alfil Dama), D (Dama), R (Rey), AR (Alfil Rey), CR (Caballo Rey), TR (Torre Rey).
* Las filas se cuentan del 1 al 8 desde el punto de vista del jugador que mueve. Por lo tanto, la fila 4 de las blancas es la fila 5 de las negras.
* Se describe el origen y el destino.

Ejemplo de comparación (Algebraica vs Descriptiva):

Imagina el primer movimiento típico del peón de rey:
• En Algebraica: 1. e4 (Fácil, la casilla e4 es fija para ambos).
• En Descriptiva: 1. P4R (Significa: "Peón a la cuarta casilla del Rey"). Si las negras responden avanzando su peón equivalentemente, en descriptiva también se escribe 1. ... P4R (porque para el negro, es su propia cuarta fila). En algebraica, ese movimiento negro sería 1. ... e5.

### Notación FEN (Forsyth-Edwards Notation)

No registra los movimientos, sino que es un método de notación para describir una posición exacta del tablero en una sola línea de texto. Es una "fotografía" que las computadoras usan para guardar partidas suspendidas o puzzles tácticos.
* Lee el tablero fila por fila, desde la fila 8 hasta la fila 1 (de izquierda a derecha).
* Las piezas blancas van en Mayúsculas (P, N, B, R, Q, K) y las negras en minúsculas (p, n, b, r, q, k).
* Los números representan las casillas vacías consecutivas.
* Las filas se separan con una barra diagonal /.

Ejemplo:

La posición inicial del ajedrez en formato FEN se escribe así:
rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1
(Donde la w indica que juegan blancas, y KQkq indica que ambos bandos aún pueden enrocar en ambos lados).
¿Te gustaría que hagamos un pequeño ejercicio donde te escriba una jugada en notación algebraica y tú intentes deducir qué pieza se movió y qué ocurrió en el tablero?

## Sistema ELO

La utilización del sistema ELO es central para poder realizar comparaciones objetivas
sobre la potencia ajedrecística entre dos algoritmos, o entre el mismo algoritmo 
corriendo en plataformas diferentes donde la velocidad de procesamiento o las 
restricciones de memoria disponible determinan la profundidad alcanzable del 
análisis en determinados tiempos.

El Sistema de Puntuación ELO es un método matemático utilizado para calcular la habilidad relativa de los jugadores en juegos de suma cero, principalmente en el ajedrez.
Fue inventado por el físico estadounidense de origen húngaro Arpad Elo para reemplazar los imprecisos sistemas de clasificación previos y fue adoptado oficialmente por la Federación Internacional de Ajedrez (FIDE) en 1970. No es un acrónimo; lleva ese nombre en honor a su creador.

Es importante entender que el sistema ELO es de naturaleza logarítmica (o si se lo
prefiere, exponencial) de manera que una diferencia relativamente pequeña en los
puntajes entre dos jugadores cambia profundamente las probabilidades de éxito
cuando compiten.


### 🎯 ¿Para qué se usa?

* Medir el nivel real: Permite saber con precisión matemática qué tan fuerte es un jugador en comparación con toda la población activa.
* Emparejamiento (Matchmaking): En plataformas digitales como Chess.com o Lichess, se usa para emparejarte automáticamente con rivales de tu misma fuerza.
* Otorgar Títulos: La FIDE exige alcanzar ciertos umbrales de Elo (junto con otros requisitos) para otorgar títulos vitalicios:
	* Maestro FIDE (FM): 2300 puntos.
	* Maestro Internacional (IM): 2400 puntos.
	* Gran Maestro (GM): 2500 puntos.

### 📊 Cómo calcular la probabilidad de victoria basada en el Elo

Antes de actualizar los puntos de un jugador, el sistema necesita calcular la expectativa de puntuación (probabilidad de victoria) de un Jugador A frente a un Jugador B.
Un resultado de 1 representa una victoria, 0.5 un empate y 0 una derrota. La fórmula matemática para hallar la expectativa del Jugador A (\(E_{A}\)) es:
\(E_{A}=\frac{1}{1+10^{\frac{R_{B}-R_{A}}{400}}}\)
Donde:
• \(R_{A}\): Elo actual del Jugador A.
• \(R_{B}\): Elo actual del Jugador B.
• El número 400 es un factor de escala estándar: una diferencia de 400 puntos de Elo significa que el jugador superior tiene aproximadamente un 91% de probabilidad de ganar.

📝 Ejemplo de Probabilidad:

Imagina una partida entre Jugador A (Elo 1800) y Jugador B (Elo 1600). La diferencia es de 200 puntos.
1. Aplicamos la fórmula: \(E_A = \frac{1}{1 + 10^{\frac{1600 - 1800}{400}}} = \frac{1}{1 + 10^{-0.5}}\)
2. \(10^{-0.5} \approx 0.3162\)
3. \(E_A = \frac{1}{1 + 0.3162} \approx 0.76\)
Resultado: El Jugador A tiene una expectativa del 76% (0.76 puntos esperados). Esto significa que si juegan 10 partidas, se espera matemáticamente que el Jugador A sume 7.6 puntos (por ejemplo, 7 victorias, 1 empate y 2 derrotas). Por consiguiente, la expectativa del Jugador B (\(E_{B}\)) es el complemento: \(1 - 0.76 = 0.24\) (24%).

### 🧮 Cómo se calcula el intercambio de Elo tras una partida

Cuando dos jugadores terminan una partida, sus puntuaciones se actualizan según la diferencia entre el resultado real y el resultado esperado. La fórmula es:
\(R_{A}^{\prime }=R_{A}+K\times (S_{A}-E_{A})\)
Donde:
• \(R_{A}^{\prime }\): El nuevo Elo del Jugador A.
• \(R_{A}\): El Elo anterior del Jugador A.
• \(S_{A}\): El resultado real de la partida (1 si ganó, 0.5 si empató, 0 si perdió).
• \(E_{A}\): La expectativa de puntuación calculada en el paso anterior.
• \(K\) (Factor K): Es una constante que determina el impacto de la partida. Varía según el jugador para dar estabilidad al sistema:
	• K = 40: Para nuevos jugadores (primeras 30 partidas) o menores de 18 años. El Elo sube y baja muy rápido.
	• K = 20: Para la mayoría de los jugadores de club y torneos estándar.
	• K = 10: Para jugadores de élite que han alcanzado un Elo de 2400 o más (evita fluctuaciones drásticas).

📝 Ejemplo de Cálculo de Intercambio (K = 20):

Siguiendo el caso anterior donde Jugador A (1800, \(E_A = 0.76\)) juega contra Jugador B (1600, \(E_B = 0.24\)):
• Escenario 1: Gana el Jugador A (el favorito).
	• Nuevo Elo de A: \(1800 + 20 \times (1 - 0.76) = 1800 + 20 \times (0.24) = \mathbf{1804.8}\) (+4.8 puntos).
	• Nuevo Elo de B: \(1600 + 20 \times (0 - 0.24) = 1600 - 4.8 = \mathbf{1595.2}\) (-4.8 puntos).
	• Nota: Como el favorito ganó, el cambio de puntos es pequeño.
• Escenario 2: Sorpresa, gana el Jugador B (el menos fuerte).
	• Nuevo Elo de A: \(1800 + 20 \times (0 - 0.76) = 1800 - 15.2 = \mathbf{1784.8}\) (-15.2 puntos).
	• Nuevo Elo de B: \(1600 + 20 \times (1 - 0.24) = 1600 + 15.2 = \mathbf{1615.2}\) (+15.2 puntos).
	• Nota: Las sorpresas se premian y castigan con muchos más puntos.

### 📈 Cómo calcular la diferencia de Elo basada en la proporción de partidas ganadas

Si dos jugadores disputan un bloque o match largo de muchas partidas (lo suficientemente grande para mitigar la varianza), podemos usar la proporción de puntos obtenidos para calcular la diferencia exacta de Elo (\(\Delta R\)) que existe entre ellos.
La fórmula matemática para despejar la diferencia de Elo a partir del porcentaje de puntos ganados o proporción (\(P\)) es la inversa de la fórmula logística:
\(\Delta R=400\times \log _{10}\left(\frac{P}{1-P}\right)\)
Donde \(P\) es la proporción de puntos obtenidos (Puntos ganados / Puntos totales disputados).

📝 Ejemplo Basado en Proporción:

Dos amigos juegan un match de 20 partidas. El Jugador A obtiene 15 puntos (combinando victorias y empates) y el Jugador B obtiene 5 puntos.
1. Calculamos la proporción de A: \(P = \frac{15}{20} = 0.75\) (75% de los puntos).
2. Aplicamos la fórmula inversa: \(\Delta R = 400 \times \log_{10}\left(\frac{0.75}{1 - 0.75}\right)\)
3. \(\Delta R = 400 \times \log_{10}\left(\frac{0.75}{0.25}\right) = 400 \times \log_{10}(3)\)
4. Como \(\log_{10}(3) \approx 0.4771\):
5. \(\Delta R = 400 \times 0.4771 \approx \mathbf{190.8}\)
Resultado: Basado puramente en el desempeño de este match, el rendimiento del Jugador A estuvo 191 puntos de Elo por encima del Jugador B. Si el Jugador B tuviera un Elo estimado de 1500, el Jugador A jugó al nivel de un Elo de 1691.

### ELO aplicado a algoritmos

En el ajedrez computarizado y las plataformas en línea, el sistema Elo se aplica de forma idéntica en su matemática básica tanto para humanos como para bots, pero difiere drásticamente en cómo se gestionan sus ecosistemas y la velocidad de sus fluctuaciones. Mientras que el Elo de un jugador humano evoluciona lentamente a lo largo de los años debido a limitaciones físicas, fatiga y un número reducido de partidas, los motores de ajedrez (bots) pueden disputar miles de partidas en cuestión de horas. Esto permite que plataformas de evaluación especializadas, como la CCRL (Computer Chess Rating Lists), utilicen factores de escala extremadamente precisos y calibraciones constantes para medir diferencias milimétricas de rendimiento entre versiones de un mismo programa.
El mayor desafío radica en que las poblaciones de humanos y bots rara vez comparten el mismo ecosistema cerrado, lo que genera una inflación o deflación del Elo relativo. Un bot de Chess.com con un Elo asignado de 2000 no necesariamente juega con la misma fuerza que un ser humano con 2000 de Elo en la FIDE, ya que los puntos Elo solo miden la habilidad en relación con los demás integrantes de ese grupo específico. Además, a diferencia de los humanos, los bots de competencia pura no sufren de inconsistencia psicológica: sus funciones de evaluación son deterministas, lo que significa que ante una misma ventaja táctica siempre rendirán igual, obligando a los desarrolladores a introducir algoritmos artificiales de "reducción de fuerza" o "errores programados" cuando se diseñan bots destinados a jugar de forma realista contra aficionados humanos.
Comparar el Elo de los mejores humanos con el de las computadoras actuales demuestra que la brecha entre la inteligencia humana y los motores de ajedrez es absoluta e insalvable. Mientras que los humanos medimos el progreso en pequeños márgenes, las máquinas han entrado en una escala de fuerza completamente diferente. [1] (https://www.quora.com/What-kind-of-ELO-rating-would-a-computer-bot-like-Stockfish-need-to-beat-Magnus-Carlson-everytime), [2] (https://vocal.media/education/can-a-human-beat-the-best-chess-computer), [3] (https://mychessplan.com/stockfish-vs-leela-chess-zero-adult-improver-engine-audit-2026/)
A continuación, se detalla la comparativa entre los picos humanos y las versiones más recientes de los motores dominantes (con datos actualizados a octubre de 2026):

#### 🧠 El Techo Humano: Magnus Carlsen (https://www.google.com/search?kgmid=%2Fm%2F0291j3&q=Magnus+Carlsen)

* Elo Máximo Histórico (Ritmo Clásico): 2882 puntos (alcanzado por Magnus Carlsen (https://www.google.com/search?kgmid=%2Fm%2F0291j3&q=Magnus+Carlsen) en mayo de 2014 y replicado en agosto de 2019). [1] (https://www.guinnessworldrecords.es/world-records/68289-highest-chess-rating-men)
* Contexto: Este es el Elo oficial de la FIDE más alto jamás registrado en la historia del ajedrez (superando el pico de 2851 de Garry Kasparov). Ningún ser humano ha logrado romper la barrera de los 2900 puntos en ajedrez clásico presencial. [1] (https://en.wikipedia.org/wiki/Magnus_Carlsen), [2] (https://www.facebook.com/100088946902343/posts/did-you-know-that-magnus-carlsen-holds-the-record-for-the-highest-peak-classical/988116074163280/), [3] (https://www.chess.com/forum/view/chess-players/magnus-carlsen-70)
* Nota en línea: Aunque Carlsen ha rozado los 3340 puntos de Elo en plataformas de internet para ritmos ultra rápidos (Blitz), ese es un ecosistema cerrado inflado y no comparable con el Elo de torneo internacional. [1] (https://www.youtube.com/watch?v=4YzYk0shhn0&t=447)

#### 💻 Las Bestias de Silicio: Motores Actuales

Para medir a los motores se utilizan listas de clasificación de computadoras especializadas, siendo la más famosa la CCRL (Computer Chess Rating Lists). A diferencia de los humanos, el Elo de los motores varía según la potencia del procesador (CPU) o la tarjeta gráfica (GPU) donde se ejecuten. [1] (https://computerchess.org.uk/ccrl/4040/rating_list_all.html), [2] (https://ramachess.com/stockfish-chess/elo/), [3] (https://ramachess.com/topchessengines/e/lczero.html), [4] (https://chess.stackexchange.com/questions/42730/why-is-leela-chess-zero-rated-low-on-ccrl-leaderboards)

#### Stockfish 19 (El Rey Absoluto)

* Elo Estimado: ~3650 - 3690 puntos (en el control de tiempo estándar de torneo 40/15).
* Versión actual: Stockfish 19 (lanzado en septiembre de 2026).
* Particularidad: Utiliza redes neuronales eficientemente actualizables (NNUE) combinadas con un cálculo bruto masivo que analiza millones de jugadas por segundo. En listas de Blitz informáticos con hardware de múltiples núcleos, llega a superar los 3800 puntos de Elo. [1] (https://www.facebook.com/c24live/posts/stockfish-is-simply-a-monster/1562998360427947/), [2] (https://chessnextmove.ai/blog/stockfish-19), [3] (https://www.uscfsales.com/blogs/chess-technology/the-best-chess-engine-in-the-world), [4] (https://ramachess.com/stockfish-chess/elo/)

#### Leela Chess Zero / Lc0 (La Red Neuronal Pura)

* Elo Estimado: ~3580 - 3670 puntos (corriendo en hardware óptimo con GPU dedicada).
* Particularidad: Inspirada en AlphaZero de DeepMind, Leela aprendió a jugar al ajedrez jugando millones de partidas contra sí misma. Su estilo es famoso por tener una "intuición posicional" más parecida a la humana, aunque respaldada por una fuerza de cálculo perfecta. [1] (https://checkmatex.app/blog/stockfish-vs-leela-vs-komodo-best-chess-engine-2026), [2] (https://chessnextmove.ai/blog/stockfish-18), [3] (https://mychessplan.com/stockfish-vs-leela-chess-zero-adult-improver-engine-audit-2026/), [4] (https://www.rankred.com/chess-engines/)

#### 📊 Comparativa Directa de Datos
|Competidor	Tipo	|Elo Máximo / Actual (Normalizado)	|Diferencia Magnus Carlsen|
|-------------------|-----------------------------------|-------------------------|
|Humano         	| 2882	                            |Base (0) |
|Leela Chess Zero	Motor (Red Neuronal / GPU)|	~3620	|+738 puntos|
|Stockfish 19	    Motor (Fuerza Bruta + NNUE)	|~3650	|+768 puntos|

[1](https://www.google.com/search?kgmid=%2Fm%2F0291j3&q=Magnus+Carlsen)

#### 📉 ¿Qué pasaría en un enfrentamiento real? (Análisis Táctico)

La diferencia de más de 750 puntos de Elo entre Magnus Carlsen (https://www.google.com/search?kgmid=%2Fm%2F0291j3&q=Magnus+Carlsen) y Stockfish 19 se traduce, matemáticamente, en una disparidad abismal utilizando la fórmula de expectativa de Arpad Elo: [1] (https://chessnextmove.ai/blog/stockfish-18)
* Probabilidad de victoria: La probabilidad de que Magnus Carlsen (https://www.google.com/search?kgmid=%2Fm%2F0291j3&q=Magnus+Carlsen) le gane una sola partida a Stockfish 19 es prácticamente del 0%. [1] (https://www.quora.com/What-kind-of-ELO-rating-would-a-computer-bot-like-Stockfish-need-to-beat-Magnus-Carlson-everytime)
* Un Match de 100 partidas: Si Carlsen (https://www.google.com/search?kgmid=%2Fm%2F0291j3&q=Carlsen) jugara un match a 100 partidas contra el Stockfish actual, el resultado más probable sería de 95 a 98 derrotas para el humano y apenas 2 o 4 empates (tablas). Carlsen (https://www.google.com/search?kgmid=%2Fm%2F0291j3&q=Carlsen) no ganaría un solo juego. Las únicas tablas ocurrirían si el motor entra de forma forzada en una línea teórica donde el juego esté matemáticamente simplificado ("muerto") desde la apertura. [1] (https://www.quora.com/What-kind-of-ELO-rating-would-a-computer-bot-like-Stockfish-need-to-beat-Magnus-Carlson-everytime)
* Ventajas insalvables: Las computadoras no cometen errores tácticos de un solo movimiento, tienen acceso a "tablabases" de finales (saben perfectamente cómo ganar o empatar cualquier posición si quedan 7 piezas o menos en el tablero) y no sufren de cansancio, nervios ni presión psicológica. [1] (https://vocal.media/education/can-a-human-beat-the-best-chess-computer)
En el ajedrez moderno, la IA ya no compite contra el ser humano; los grandes maestros humanos ahora utilizan a Stockfish y Leela simplemente como "oráculos" o herramientas de entrenamiento para intentar comprender la profundidad de un juego que las máquinas ya dominan por completo. [1] (https://checkmatex.app/blog/stockfish-vs-leela-vs-komodo-best-chess-engine-2026)

## Correcciones al método de medición de ELO cibernético

Para normalizar el rendimiento de distintos motores de ajedrez que corren en plataformas de hardware radicalmente diferentes, no podemos basarnos en variables teóricas aisladas (como la velocidad del reloj en GHz), ya que la arquitectura de un chip moderno o el uso de hilos (threads) no escalan de forma lineal.
En ciencias de la computación y ajedrez informático, la métrica reina para medir el rendimiento puro es la velocidad de nodos por segundo (NPS). Los "nodos" representan la cantidad de posiciones que el motor analiza y evalúa cada segundo.
Dado que la utilización del ELO es central en la estrategia de éste proyecto se 
utilizará un algoritmo de normalización matemática llamado *Algoritmo de Elo Corregido por Eficiencia de Silicio (ECES)*.

🧪 El Algoritmo: Elo Corregido por Eficiencia de Silicio (ECES)

El objetivo del algoritmo es calcular un Elo Base de Software (\(Elo_{Base}\)). Este indicador representa la fuerza táctica intrínseca del código del motor si todos compitieran exactamente sobre la misma máquina de referencia.

Paso 1: Obtener el Factor de Rendimiento Bruto (NPS)

En lugar de multiplicar GHz por RAM por núcleos, dejamos que el motor corra en su máquina objetivo un set estandarizado de posiciones complejas (por ejemplo, el test suite *Colditz* o *Arasan*) durante 3 minutos y extraemos el NPS promedio reportado por el motor mediante el protocolo UCI.
• Para motores tradicionales (CPU): El NPS mide posiciones tradicionales evaluadas por segundo.
• Para motores de redes neuronales puras (GPU como Lc0): El NPS suele medir "Nodos de Búsqueda" o evaluaciones de la red por segundo.

Paso 2: Calcular el Factor de Penalización/Bonificación por Hardware (\(F_{H}\))

Definimos una Máquina de Referencia Estándar (por ejemplo: 1 CPU de 4 núcleos a 3.0 GHz, sin GPU, 8 GB RAM). Esta máquina produce un número de nodos de referencia conocido como \(NPS_{Ref}\) para un motor base.
Calculamos el coeficiente de ventaja de hardware (\(F_{H}\)) mediante la siguiente fórmula logarítmica (el logaritmo es crucial porque en ajedrez, duplicar la velocidad del hardware no duplica la fuerza, sino que ofrece retornos decrecientes):
\(F_{H}=\log _{2}\left(\frac{NPS_{Motor}}{NPS_{Ref}}\right)\)
Si un motor corre en una supercomputadora y genera 16 veces más NPS que la máquina de referencia, su \(F_{H}\) será \(\log_{2}(16) = 4\).

Paso 3: Aplicar la Equivalencia de Elo por Duplicación de Velocidad (\(\Delta Elo_{NPS}\))

Históricamente, en el desarrollo de motores como Stockfish, se ha demostrado una regla empírica constante: Duplicar la velocidad de cálculo (nodos por segundo) equivale a un aumento de aproximadamente entre 50 y 70 puntos de Elo reales (utilizaremos el estándar de la industria de 60 puntos de Elo).
El factor de corrección por hardware en puntos de Elo (\(C_{Elo}\)) es:
\(C_{Elo}=F_{H}\times 60\)

Paso 4: Calcular el Elo Neto de Software (\(Elo_{Base}\))

Finalmente, tomamos el Elo observado en las partidas del torneo (\(Elo_{Medido}\)) y le restamos la ventaja otorgada por la potencia de su computadora:
\(Elo_{Base}=Elo_{Medido}-C_{Elo}\)

📝 Ejemplo Práctico de Aplicación

Imaginemos que ponemos a competir a dos motores en un torneo en línea y obtenemos sus Elos medidos tras 100 partidas. Queremos saber cuál software es mejor si corrieran en igualdad de condiciones.
• Establecemos el \(NPS_{Ref}\) de la comunidad: 1,000,000 nodos por segundo (1 MNPS).

Caso Motor A: Stockfish (Corriendo en una Laptop Modesta)

• Hardware: CPU 4 núcleos, 2.5 GHz, 8 GB RAM.
• Rendimiento: Genera 2,000,000 de nodos por segundo (2 MNPS).
• Elo Medido en el torneo: 3300.
1. \(F_H = \log_{2}(2,000,000 / 1,000,000) = \log_{2}(2) = 1\)
2. \(C_{Elo} = 1 \times 60 = 60\) puntos de ventaja por hardware.
3. \(Elo_{Base} = 3300 - 60 = \mathbf{3240}\)

Caso Motor B: Leela Chess Zero (Corriendo en una PC Gamer de Gama Alta)

• Hardware: CPU 16 núcleos, 5.0 GHz, 64 GB RAM, Tarjeta Gráfica dedicada (GPU RTX 4090).
• Rendimiento: Gracias a su potente GPU, su equivalencia de procesamiento alcanza los 16,000,000 de nodos por segundo (16 MNPS).
• Elo Medido en el torneo: 3450 (Ganó el torneo).
1. \(F_H = \log_{2}(16,000,000 / 1,000,000) = \log_{2}(16) = 4\)
2. \(C_{Elo} = 4 \times 60 = 240\) puntos de ventaja por hardware.
3. \(Elo_{Base} = 3450 - 240 = \mathbf{3210}\)

🏆 Conclusión del Algoritmo

Aunque el Motor B ganó el torneo en la práctica con un Elo de 3450 frente a los 3300 del Motor A, el algoritmo ECES demuestra que en nivel de igualdad de condiciones (Elo Base), el código del Motor A es superior (3240 vs 3210). Si mudáramos el Motor A a la computadora del Motor B, el Motor A alcanzaría un Elo real estimado de 3240 + 240 = 3480, aplastando al Motor B.
¿Te gustaría que adaptemos este algoritmo para incluir una penalización por la gestión de la Memoria RAM (Tablas de Hash), las cuales reducen drásticamente el NPS necesario en los finales de partida?

Para integrar la gestión de la memoria RAM en el algoritmo, debemos entender cómo la utiliza un motor de ajedrez. Los motores no usan la RAM de forma pasiva; la destinan principalmente a las Tablas de Hash (Transposition Tables).
Estas tablas actúan como una memoria caché de cortísimo plazo: si el motor ya calculó una posición en una línea profunda, guarda el resultado en la RAM. Si vuelve a encontrarse con esa misma posición por otro orden de jugadas (transposición), no la vuelve a calcular; lee la respuesta directamente de la memoria.
Tener mucha RAM ahorra millones de cálculos, lo que significa que un motor con una tabla de hash gigante tiene una ventaja invisible que el indicador de Nodos por Segundo (NPS) no siempre llega a reflejar en su totalidad.
A continuación, actualizamos el algoritmo para transformarlo en el Algoritmo ECES-H (Elo Corregido por Eficiencia de Silicio y Hash).

🧮 El Algoritmo Actualizado: ECES-H

Añadiremos un nuevo factor independiente de penalización por el tamaño de las tablas de Hash asignadas en la memoria RAM.

Paso 1: Definir los Parámetros de la RAM de Referencia

Establecemos un tamaño estándar de Tablas de Hash en RAM para la comunidad informática como base neutra:
• \(Hash_{Ref} = 1024 \text{ MB}\) (1 GB asignado exclusivamente al motor).

Paso 2: Calcular el Coeficiente de Ventaja por Hash (\(F_{Hash}\))

De acuerdo con las pruebas empíricas acumuladas en torneos informáticos como el TCEC (Top Chess Engine Championship), duplicar de forma constante el tamaño del Hash ofrece un retorno decreciente que equivale a un aumento de entre 8 y 12 puntos de Elo (fijaremos el estándar de la industria en 10 puntos de Elo por cada duplicación).
Calculamos el factor logarítmico de ventaja por memoria:
\(F_{Hash}=\log _{2}\left(\frac{Hash_{Motor}}{Hash_{Ref}}\right)\)
El factor de corrección por RAM en puntos de Elo (\(C_{RAM}\)) es:
\(C_{RAM}=F_{Hash}\times 10\)

Paso 3: Combinar los Factores en la Fórmula Final de Elo Base

Ahora, el cálculo del Elo Neto de Software (\(Elo_{Base}\)) restará tanto la potencia bruta de procesamiento (\(C_{Elo}\)) calculada previamente, como la ventaja táctica de memoria caché (\(C_{RAM}\)):
\(Elo_{Base}=Elo_{Medido}-C_{Elo}-C_{RAM}\)
Donde (recordando el paso anterior):
• \(C_{Elo} = \log_{2}\left(\frac{NPS_{Motor}}{NPS_{Ref}}\right) \times 60\)

📝 Ejemplo Práctico con Corrección de RAM

Ponemos a competir a dos versiones del mismo motor en dos servidores diferentes:
• Máquina de Referencia Común: \(NPS_{Ref} = 1 \text{ MNPS}\)  |  \(Hash_{Ref} = 1024 \text{ MB}\) (1 GB).

Caso Motor A: (Poco Procesamiento, pero mucha RAM)

• Rendimiento Bruto: Genera 2,000,000 de nodos por segundo (2 MNPS).
• Memoria Asignada: 16,384 MB (16 GB de Hash).
• Elo Medido en el torneo: 3200.
1. Corrección por CPU (\(C_{Elo}\)):
	• \(F_H = \log_{2}(2 / 1) = 1\)
	• \(C_{Elo} = 1 \times 60 = \mathbf{60}\)
2. Corrección por RAM (\(C_{RAM}\)):
	• \(F_{Hash} = \log_{2}(16384 / 1024) = \log_{2}(16) = 4\) (Ha duplicado 4 veces la RAM de referencia)
	• \(C_{RAM} = 4 \times 10 = \mathbf{40}\)
3. Resultado Elo Base:
	• \(Elo_{Base} = 3200 - 60 - 40 = \mathbf{3100}\)

Caso Motor B: (Mucho Procesamiento, pero "ahogado" en RAM)

• Rendimiento Bruto: Genera 8,000,000 de nodos por segundo (8 MNPS).
• Memoria Asignada: Solo 1,024 MB (1 GB de Hash, igual al de referencia).
• Elo Medido en el torneo: 3210.
1. Corrección por CPU (\(C_{Elo}\)):
	• \(F_H = \log_{2}(8 / 1) = 3\) (Ha duplicado 3 veces los nodos por segundo)
	• \(C_{Elo} = 3 \times 60 = \mathbf{180}\)
2. Corrección por RAM (\(C_{RAM}\)):
	• \(F_{Hash} = \log_{2}(1024 / 1024) = \log_{2}(1) = 0\)
	• \(C_{RAM} = 0 \times 10 = \mathbf{0}\)
3. Resultado Elo Base:
	• \(Elo_{Base} = 3210 - 180 - 0 = \mathbf{3030}\)

🏆 Conclusión del Análisis de Eficiencia

Al introducir la RAM, vemos un comportamiento sumamente realista: el Motor B tiene mucha potencia bruta de CPU, pero su baja memoria RAM le impidió sacarle el máximo provecho, perdiendo eficiencia.
Aun así, al limpiar el ruido del hardware, el Motor A demuestra tener un código más eficiente (\(3100\) vs \(3030\)). Si al Motor A le diéramos la misma velocidad de procesamiento que al B, su ventaja en las Tablas de Hash lo haría destrozar por completo la competencia.
Este modelo ya cubre CPU, GPU (mediante el mapeo de nodos equivalentes), hilos y RAM. ¿Te gustaría que incluyéramos la última frontera de optimización de hardware: el uso de las Syzygy Tablebases (discos de estado sólido SSD / NVMe que almacenan finales perfectos resueltos)?



## Análisis de una partida

🔎 ¿Qué significa analizar una partida?

En ajedrez, analizar una partida significa desarmar el juego jugada por jugada después de haberlo terminado. Consiste en una autopsia crítica para descubrir la verdad oculta de la posición: qué se hizo bien, qué se hizo mal, qué oportunidades se dejaron pasar y cuáles eran los planes correctos que ninguno de los dos jugadores logró ver mientras corría el reloj.
Antiguamente, el análisis se hacía de forma puramente humana (moviendo las piezas sobre el tablero junto al rival o un entrenador). Hoy en día es un proceso híbrido: el jugador intenta comprender sus propios pensamientos y luego contrasta sus conclusiones con el veredicto infalible de un motor de ajedrez (como Stockfish).

📉 Ejemplos prácticos de un análisis

Durante un análisis, las jugadas se evalúan y se clasifican mediante símbolos universales. Aquí tienes cómo se vería un fragmento de análisis:
* Identificar el Error Grave (Blunder - ??):
	* Ejemplo: "En la jugada 14, moví 14. Tfe1??. No me di cuenta de que al quitar la torre de f1, desprotegí el peón de f2. El motor me muestra que mi rival tenía la jugada táctica 14... Cg4!, atacando f2 y ganando la partida de inmediato."
* Descubrir la Jugada Brillante (Brilliant - !!):
	* Ejemplo: "Mi rival sacrificó su dama con 22... Dxf3!!. En el momento pensé que se había equivocado, pero analizando la línea completa descubrí que tras mi captura 23. gxf3, sus alfiles coordinaban un jaque mate inevitable en tres movimientos. Fue un sacrificio profundamente calculado."
* Encontrar "La Jugada Profiláctica" (Prevención):
	* Ejemplo: "Antes de lanzar mi ataque en el flanco de dama, debí jugar 18. h3!. El análisis me demuestra que esa jugada silenciosa evitaba que el caballo enemigo saltara a g4 y arruinara mis planes ofensivos."

🏆 ¿Qué se obtiene al analizar?

Analizar tus propias partidas es el método número uno en el mundo para mejorar tu nivel de ajedrez. De este proceso obtienes:
* Detección de patrones de error: Descubres si tiendes a perder por errores tácticos (colgadas de piezas), por una mala gestión del tiempo o por no saber cómo jugar los finales de partida.
* Ampliación del repertorio: Entiendes en qué jugada exacta te desviaste de la teoría de aperturas y qué debiste haber respondido ante la sorpresa del rival.
* Pensamiento autocrítico: Rompes la ilusión de que "jugaste perfecto y perdiste por mala suerte". El análisis destruye el ego y te muestra la realidad matemática de tus decisiones.

🏷️ ¿Por qué determinadas partidas o jugadas tienen nombres?

En el ajedrez, los nombres no se asignan de forma automática; nacen de la historia, la geografía y el impacto cultural. Existen tres categorías principales de nombres:

### Aperturas y Defensas (Los primeros movimientos)

Tienen nombre para que los jugadores no tengan que memorizar secuencias numéricas largas, sino conceptos estratégicos.
* Por origen geográfico: Se nombran según el lugar donde se jugaron por primera vez o donde se popularizó su estudio.
	* Ejemplo: La Apertura Española (1. e4 e5 2. Cf3 Cc6 3. Ab5) o la Defensa Siciliana (1. e4 c5).
* Por el apellido del jugador: En honor al ajedrecista que la descubrió o la llevó a la élite.
	* Ejemplo: La Defensa Alekhine (1. e4 Cf6), nombrada por el campeón mundial Alexander Alekhine.

### Partidas Históricas (Bautizos por su belleza o contexto)

Cuando una partida alcanza un nivel de genialidad artística o drama político inigualable, la comunidad internacional le otorga un nombre propio.
* La Partida Inmortal (1851): También conocida como *evergreen* donde Adolf Anderssen sacrificó casi todas sus piezas mayores (sus dos torres y la dama) para dar un jaque mate espectacular con sus tres piezas menores restantes. Se le llamó así porque su belleza vivirá para siempre.
* La Partida del Siglo (1956): Un joven Bobby Fischer de solo 13 años derrotó al maestro Donald Byrne realizando un sacrificio de dama alucinante que revolucionó el ajedrez mundial.

### Patrones Tácticos y de Mate

Ciertas configuraciones de piezas que se repiten constantemente reciben nombres visuales o históricos para facilitar su reconocimiento rápido durante el juego.
* El Mate del Pastor: El clásico mate en 4 jugadas que aprovecha la debilidad del peón en f7.
* El Mate del Pasillo: Ocurre cuando un rey queda atrapado detrás de su propia barrera de peones y una torre o dama enemiga lo ataca en la octava fila.
* La Clavada / El Tenedor: Nombres descriptivos de recursos tácticos (un "tenedor" es cuando un caballo ataca a dos piezas importantes a la vez, como si las pinchara juntas).


## Métodos de aprendizaje

Aprender ajedrez de forma eficiente es un viaje que va desde el control muscular básico (mover las piezas sin tirarlas) hasta el desarrollo de una mente estratégica capaz de predecir el futuro. Un humano no aprende acumulando datos, sino automatizando patrones.
Es útil entender la hoja de ruta descriptiva de los pasos que hay que dar para 
lograrlo. El desarrollo de métodos automatizados tiene similitudes notables con el 
mismo proceso hecho por humanos, quizás con otros tiempos.
La hoja de ruta puede ser dividida en 4 etapas lógicas para dominar el juego, diseñada para transformar a un principiante absoluto en un jugador competitivo de club.

🗺️ Hoja de Ruta para Aprender Ajedrez

[Etapa 1: Alfabetización] ➔
[Etapa 2: El Despertar Táctico] ➔ 
[Etapa 3: Pensamiento Estratégico] ➔
[Etapa 4: Competencia]

## Etapa 1: La Alfabetización Visual y Reglas (Elo 0 - 600)

El objetivo en esta fase es acostumbrar al ojo a la geometría del tablero y no cometer ilegalidades.

* Paso 1: Mecánica del tablero. Aprender las reglas básicas, los movimientos y los movimientos especiales (enroque, captura al paso y promoción).
* Paso 2: Fluidez de la Notación. Aprender a leer y escribir en notación algebraica de forma fluida. Si no puedes "hablar" el idioma del ajedrez, no podrás leer libros ni entender análisis.
* Paso 3: Evitar la "ceguera de piezas". Jugar partidas amistosas con un único objetivo táctico: no regalar piezas en una sola jugada (comúnmente llamado colgarse una pieza). Antes de mover, el cerebro debe hacerse la "pregunta de seguridad": ¿A qué casillas ataca la pieza que voy a mover y qué casillas deja de defender?

## Etapa 2: El Despertar Táctico (Elo 600 - 1200)

En el ajedrez amateur, el 99% de las partidas se deciden por táctica (errores de cálculo inmediatos). Aquí aprendes a usar la fuerza bruta calculada.

* Paso 1: Patrones de Mate Esenciales. Estudiar los mates básicos que terminan la partida rápidamente (Mate del pasillo, mate del beso de la dama, mate con dos torres, rey y torre contra rey).
* Paso 2: Resolución masiva de "Puzzles" (Problemas). Dedicar el 70% del tiempo de estudio a resolver problemas de táctica de 1 o 2 jugadas. El cerebro humano aprende esto por reconocimiento de formas. Debes automatizar los conceptos de:

	* El Tenedor / Ataque doble: Una pieza ataca dos objetivos.
	* La Clavada: Inmovilizar una pieza enemiga porque detrás hay una más valiosa.
	* La Enfilada: Un ataque en línea recta a una pieza valiosa que, al moverse, expone a la que está detrás.

* Paso 3: Construir un "Repertorio de Aperturas" minimalista. No memorizar líneas profundas. Aprender los Principios de la Apertura: controlar el centro con los peones, desarrollar los caballos y alfiles rápidamente, y poner el rey a salvo mediante el enroque. Elegir una sola apertura con Blancas (ej. Apertura Italiana) y una defensa sólida con Negras (ej. Defensa Karo-Kann o e5).

## Etapa 3: Pensamiento Estratégico y Posicional (Elo 1200 - 1600)

Aquí el jugador descubre que no siempre hay un golpe táctico disponible. Se aprende a formular planes a largo plazo cuando el tablero está en calma.
* Paso 1: Estructura de peones y casillas. Aprender que los peones dictan los planes. Identificar peones doblados, peones aislados y peones pasados. Aprender a identificar "casillas fuertes" (debilidades en el campo rival donde puedes meter un caballo de forma permanente).
* Paso 2: El Método de Análisis Post-Partida. Aplicar obligatoriamente la regla de oro: revisar cada partida jugada. El humano progresa cuando encuentra el momento exacto donde su plan estratégico falló y busca la alternativa correcta utilizando el motor como asistente.
* Paso 3: Introducción a los Finales. Estudiar la teoría de finales básicos. El ajedrez se aprende al revés: es más fácil entender el poder de tres piezas en un tablero vacío que el de 32 piezas al inicio. Dominar los finales de peones (regla del cuadrado, la oposición del rey) y finales básicos de torres.

## Etapa 4: Especialización y Competición (Elo 1600+)

El juego se vuelve un deporte psicológico y de resistencia. El entrenamiento se asemeja al de un atleta.
* Paso 1: Gestión del tiempo y psicología. Aprender a jugar bajo la presión del reloj, gestionar los nervios tras un error y aprender a "recular" o defender posiciones inferiores (resiliencia en el tablero).
* Paso 2: Estudio de Clásicos. Analizar partidas de los Campeones Mundiales (Capablanca para la sencillez posicional, Alekhine o Kasparov para el ataque dinámico, Carlsen para los finales). El cerebro absorbe la "intuición" de los maestros.
* Paso 3: Transición al Ajedrez Presencial (Over the Board). Jugar torneos oficiales con relojes físicos y piezas reales. El salto del tablero bidimensional de la pantalla al tablero tridimensional real requiere una adaptación visual y espacial crucial.


## De las máquinas
Guiado por .pgn vs. aprendizaje al azar

# Redes neuronales

Concepto y detalles de arquitecturas
Representación
Metodos numéricos

## Entrenamiento (Backpropagation)

### Pytorch
### Tensorflow
### Tensorflow Lite

### Arquitectura NNUE
### Arquitectura MCTS
### Arquitectura Transformer (Search less)


## Destilado

### Destilado con red
### Destilado con motor

## Comunicación

### Sistema freechess.org
### Sistema Universal Chess Interface (UCI)

#### Comunicación
#### Convenciones
#### Métodos de enlace
#### Repositorios de partidas

Describir Entrada-Salida estándar * TCP/IP

### Motores vs. GUI

## Reglas del ajedrez

#### Modos

Clásico, Blitz, Bullet y otros modos especiales significado de cada uno

## Sistema de puntuación ELO

Explicar el sistema ELO y las fórmulas, como se usa en Ajedrez y como se usa en 
éste proyecto para evaluar la potencia relativa entre distintas alternaivas
Explicar como calcular el ELO en forma relativa

# El problema

Describir el ajedrez como problema de optimización y describir la dimensión de su dificultad

Explicar que el objetivo es encontrar algoritmos de razonable competitividad para plataformas pequenas

La competencia entre motores como validación de capacidades 

Explicar el problema de evaluar el resultado de un algoritmo, concepto de antagonismo y competencia
uso del sistema ELO

## Evolución del proyecto

Explicar brevemente las iniciativas y sus problemas

### Bobby
### Nyx
### Akkad

### Dificultades de recursos
El problema del entrenamiento, uso de CPU y de GPU, doble problema acoplado optimizar y entrenar,
importar redes, destilar redes.

## Random

## Heurística pura 

Descripción y limitaciones

## Ecuación de Bellman

Política y acción, descripción matemática exhaustiva
Comparar Ta-Te-Ti con Damas y Ajedrez la maldición de la dimensionalidad
El problema del entrenamiento
Posibles alternativas (¿Bellman restringido?)


## Minimax Alpha/Beta

Descripción y limitaciones
Algoritmo Sargón en detalle

### Negamax
.....
### Estrategias de poda (pruning)
### Heurísticas extremas

## Redes neurales

Distintas estrategias para su uso

### Redes NNUE
Descripción exhaustiva de su formulación arquitectura y entrenamiento
Como representar el espacio de juego
Distintos tipos y usos

Aqui hay que hablar algo de Cerebrum, npz y  grumpy

### Redes convolucionales
El ajedrez como un problema de interpretación visual y su aplicación a enfoque *search less*
Arquitectura de las redes necesarias

### Monte Carlo Tree Search
El ajedrez como un problema de política y valor
Arquitectura de las redes necesarias 

### Algoritmos genéticos

Que se puede aportar aqui

### Algoritmos cuánticos

### Evaluación vs. Jugada

Ver la necesidad de partir la evaluación vs. la jugada


# Implementación

## Plataforma Sargon-NNUE

Descripción de arquitectura

'''
⬅️Akkad/
├── .gitignore
├── .vscode/
├── createPackage.ps1
├── excluidos.txt
├── listZipFolders.ps1
│
├── AlphaZero/                           [NUEVO: migrado desde Sargon-NNUE/x86/AlphaZero]
│   ├── CMakeLists.txt
│   ├── README.md
│   ├── README_ARM64.md
│   ├── README_CONFIG_v0.1.2.md
│   ├── README_GPU_v0.1.1.md
│   ├── README_DEBIAN_ARM64.md
│   ├── brain_example.json
│   ├── build.ps1                        [Windows]
│   ├── build_debian.sh                  [Debian]
│   ├── build_macos.sh
│   ├── build_posix.sh
│   ├── build_raspberrypi.sh
│   ├── src/
│   │   ├── akkad_alphazero_main.cc
│   │   └── config.h
│   ├── tests/
│   │   └── uci_smoke.ps1
│   └── tools/
│       └── bash/
│           ├── build.sh
│           ├── run.sh
│           ├── diagnostics.sh
│           ├── uci_smoke.sh
│           └── run_benchmark.sh
│
├── Sargon-NNUE/                         [orquestador Python / benchmark / match / rally]
│   ├── examples/
│   │   ├── lc0/
│   │   └── lc0_uci/
│   ├── scripts/
│   │   ├── crypt/
│   │   ├── data/
│   │   ├── legacy/
│   │   ├── rally/
│   │   ├── sargon_benchmark.py
│   │   ├── sargon_match.py
│   │   ├── sargon_listen.ps1
│   │   └── ...
│   ├── src/
│   │   ├── sargon_nnue/
│   │   │   ├── evaluators/
│   │   │   ├── players/
│   │   │   ├── brains.py
│   │   │   ├── factory.py
│   │   │   ├── sargon_listen.py
│   │   │   ├── sargon_arbiter.py
│   │   │   └── ...
│   │   ├── sargon_nnue.egg-info/
│   │   └── __pycache__/
│   ├── tests/
│   ├── data/                            [usado operativamente aunque no se vea completo en el ZIP]
│   │   ├── brains/
│   │   │   ├── brains.json
│   │   │   ├── brains_amelia.json
│   │   │   └── ...
│   │   ├── runs/
│   │   │   └── lc0/
│   │   │       └── t1-256x10-distilled-swa-2432500.pb.gz
│   │   ├── benchmark/
│   │   ├── match/
│   │   └── ...
│   └── x86/                             [LEGADO / histórico]
│       ├── AlphaZero/                   [origen anterior de AlphaZero]
│       │   ├── src/
│       │   └── tests/
│       └── picoKeras/
│           ├── build/
│           ├── include/
│           ├── scripts/
│           ├── src/
│           ├── tests/
│           └── tools/
│
├── challenger/
│   ├── data/
│   ├── docs/
│   │   ├── AlphaZero_Algorithm/
│   │   ├── Sargon_Adaptativo/
│   │   ├── Sargon_Algorithm/
│   │   ├── Sargon_Learning_Algorithm/
│   │   └── StockFish_Algorithm/
│   ├── scripts/
│   ├── src/
│   │   └── challenger/
│   └── tests/
│
├── fics-uci/
│   ├── archive/
│   ├── __pycache__/
│   ├── fics_uci.py
│   ├── fics_stats.py
│   ├── config.yml
│   └── tools/                           [AGREGADO operativamente]
│       └── bash/
│           ├── run_fics_uci.sh
│           └── run_fics_uci_amelia.sh
│
├── picoAlpha/
│   ├── ARM/
│   │   ├── config/
│   │   ├── include/
│   │   ├── src/
│   │   ├── tests/
│   │   └── tools/
│   └── x86/
│       └── picoAlpha/
│           ├── build/
│           ├── include/
│           ├── src/
│           ├── tests/
│           └── tools/
│
├── picoKeras/
│   ├── ARM/                             [placeholder / port futuro a arquitectura Pico]
│   │   ├── include/
│   │   └── src/
│   ├── x86/                             [motor válido de escritorio original]
│   │   └── picoKeras/
│   │       ├── build/
│   │       ├── include/
│   │       ├── src/
│   │       └── third_party/
│   ├── debian/                          [NUEVO: port Debian con TFLite]
│   │   ├── CMakeLists.txt
│   │   ├── model_tflite.cpp
│   │   └── picoKeras/                   [salida/estructura de build del port]
│   ├── scripts/
│   ├── tools/
│   │   └── bash/
│   │       ├── build.sh
│   │       ├── run.sh
│   │       └── uci_smoke.sh
│   └── README_DEBIAN.md
│
└── picoSargon/
    ├── .vscode/
    ├── ARM/
    │   ├── assets/
    │   ├── build/
    │   ├── config/
    │   ├── include/
    │   ├── reference/
    │   ├── scripts/
    │   ├── src/
    │   └── tests/
    ├── x86/
    │   └── picoSargon/
    │       ├── assets/
    │       ├── build/
    │       ├── build-host-windows/
    │       ├── host_build_source/
    │       ├── include/
    │       └── src/
    ├── debian/                          [NUEVO: port Debian]
    │   └── picoSargon/
    │       ├── CMakeLists.txt
    │       ├── assets/
    │       │   └── grumpy.bin
    │       ├── build/
    │       └── ...
    ├── tools/
    │   ├── bash/
    │   │   ├── build.sh
    │   │   ├── run.sh
    │   │   ├── run_brain.sh
    │   │   ├── run_listen.sh
    │   │   ├── run_match.sh
    │   │   ├── run_benchmark.sh
    │   │   ├── uci_smoke.sh
    │   │   └── ...
    │   └── uci_screen_gui/
    └── README_PORT_DEBIAN_v0.2.21.md
'''


flowchart TD
    AK["Akkad / Raíz del proyecto"]

    AK --> AZ["AlphaZero"]
    AK --> SN["Sargon-NNUE"]
    AK --> PS["picoSargon"]
    AK --> PA["picoAlpha"]
    AK --> PK["picoKeras"]
    AK --> FI["fics-uci"]
    AK --> CH["challenger"]

    AZ --> AZS["src / Núcleo C++"]
    AZ --> AZW["build.ps1 / Windows"]
    AZ --> AZD["tools/bash / Debian"]
    AZ --> AZT["tests"]

    SN --> SNS["src/sargon_nnue"]
    SN --> SNC["data/brains"]
    SN --> SND["data/runs"]
    SN --> SNT["scripts"]
    SNS --> SNP["players"]
    SNS --> SNE["evaluators"]
    SNT --> SNB["benchmark"]
    SNT --> SNM["match / rally / listen"]

    PS --> PSW["x86/picoSargon"]
    PS --> PSP["ARM / Pico W y 2W"]
    PS --> PSD["debian/picoSargon"]
    PS --> PST["tools/bash"]
    PSD --> PSG["Grumpy NNUE"]
    PSW -. "Fuentes C++ compartidos" .-> PSD

    PA --> PAW["x86/picoAlpha"]
    PA --> PAP["ARM / Pico W y 2W"]

    PK --> PKW["x86/picoKeras"]
    PK --> PKP["ARM / Placeholder Pico"]
    PK --> PKD["debian"]
    PK --> PKT["tools/bash"]
    PKD --> PKL["TensorFlow Lite"]
    PKW -. "Núcleo C++ compartido" .-> PKD

    FI --> FIP["fics_uci.py"]
    FI --> FIC["config_amelia.yml"]
    FI --> FIS["Scripts Bash"]

    CH --> CHS["src/challenger"]
    CH --> CHT["tests / docs"]

    SNM -. "UCI" .-> AZ
    SNM -. "UCI" .-> PS
    SNM -. "UCI" .-> PA
    SNM -. "UCI" .-> PK
    FIP -. "UCI/TCP" .-> PSD

    classDef root fill:#253858,color:#fff,stroke:#172b4d
    classDef core fill:#e1edff,color:#17365d,stroke:#5c91ca
    classDef debian fill:#d8f3df,color:#14532d,stroke:#45a06c
    classDef pico fill:#fff0cd,color:#7a4a06,stroke:#d49b37
    classDef placeholder fill:#efefef,color:#666,stroke:#aaa,stroke-dasharray:5 3

    class AK root
    class AZ,SN,PS,PA,PK,FI,CH core
    class AZD,PSD,PKD,PKL debian
    class PSP,PAP pico
    class PKP placeholder

### Arquitecturas soportadas

ARM (Raspberry Pi Pico)
X86 (Windows)
MAC
Debian (Raspberry Pi)

### Ciclo de desarrollo

#### Desarrollo y evaluación en Python (Sargon-NNUE)
#### Desarrollo o adaptación de red neuronal o mecanismo de evaluación
#### Evaluación de performance
#### Competencia entre brains
#### Competencia abierta (lichess y fics)


### Player y Evaluador con bus comun
### Posibilidad de incorporar motores (Stockfish, lc0)
### Posibilidad de importar "cerebros"
### Definición de caracteristicas de un jugador (cerebro).
### Interfaces (UCI TCP/IP)
### Challenger
### Ciclo de entrenamiento
#### Entrenamiento NNUE
#### Entrenamiento MCTS
#### Entrenamiento KERAS
#### Destilado
#### Peso de las redes (FP32 vs. INT8)

## Players Genéricos

### Random
### Sargon
### SargonPlus
### Keras
### Cerebrum
### AlphaZero
### StockFish
### lc0
### External
### microChess

## Players Optimizados

### Keras
### picoSargon (x86)
### picoAlpha (x86)
### Alphazero (x66) ELO 2500
### picoSargon (ARM) ELO 1800
### picoAlpha (ARM)
### picoChess (ARM)

## Evaluadores Genericos

### Null
### Classic
### npz
### Keras
### Grumpy
### Cerebrum-v1.1
### lc0
### microChess

## Evaluadores especializados
### tinyGyal
### picoGyal
### picoChess

# Plataforma

Como se juntan e interconectn players con evaluadores

## Definición de configuraciones (brains.json)

## Evaluación de performance (benchmark)

## Evaluación de capacidad mutua (match)

## Evaluación de capacidad cruzada (rally)

## Cruces entre player y evaluador

Al ser un bus comun se pueden intercambiar, algunas experiencias

## Entrenamiento

### Preparación

#### Lectura de PGN
#### Extracción de muestra
#### Valuación
#### Entrenamiento (PyTorch)
#### Auditoría

## Servidor (TCP/IP)

## Servidor (E/S Estándar)

## Challenger

## Bridges

### lichess-bot

### fics-uci
#### fics-stat

## Motores optimizados 

### picoSargon (X86)
### picoSargon (ARM)
### picoSargon (Debian)
### picoSargon (MacOS)

### picoAlpha (X86)
### picoAlpha (ARM)
### picoAlpha (Debian)
### picoAlpha (MacOS)

### picoKeras (X86)
### picoKeras (ARM)
### picoKeras (Debian)
### picoKeras (MacOS)

### picoChess (X86)
### picoChess (ARM)
### picoChess (Debian)
### picoChess (MacOS)

## Motores experimentales

### Bellman-Restricted
### Quantum
### Genetic

# Construcción

## Entrenamiento convencional 

## Entrenamiento destilado

## Adopción de redes pre-entrenadas

### Cerebrum

### Red nativa npz

### Red semi-nativa grumpy

### Redes leela zero chess

#### Red muy grande
#### Red grande
#### tinyGyal
#### destilado de picoGyal

### Redes transformadoras

#### medium y small.keras


## Evaluación de performance

## Capacidades relativas

Marcar que la referencia es sargon classic

## Competencia abierta

Casos de lichess.org y fics

# Apéndice A - Notación 

Para registrar y leer las partidas de ajedrez se utiliza un sistema universal llamado Notación Algebraica. Este sistema sustituyó al antiguo sistema descriptivo (como "P4R" o "Peón 4 Rey") y es el estándar oficial de la FIDE (Federación Internacional de Ajedrez).
A continuación, te presento un resumen detallado con ejemplos claros de cómo funciona:

## Identificación del Tablero (Filas y Columnas)

El tablero se divide mediante un sistema de coordenadas similar a una batalla naval:
• Columnas (verticales): Se nombran con letras minúsculas de la a a la h (de izquierda a derecha desde la perspectiva de las piezas blancas).
• Filas (horizontales): Se nombran con números del 1 al 8 (la fila 1 es donde se colocan las piezas mayores blancas y la 8 donde se colocan las negras).
• Casillas: Cada casilla se identifica combinando su letra y su número. Ejemplo: e4, c6, h7.

## Identificación de las Piezas

Cada pieza se representa con la primera letra de su nombre en mayúscula.
• R = Rey
• D = Dama (o Reina)
• T = Torre
• A = Alfil
• C = Caballo
• Nota importante: Los peones no llevan ninguna letra. Si solo aparece el nombre de la casilla, significa que se movió un peón.
(En libros internacionales es común ver la notación en inglés: K=King, Q=Queen, R=Rook, B=Bishop, N=Knight).

## Reglas de Escritura y Ejemplos

Una jugada normal se escribe indicando la letra de la pieza + la casilla de destino.

Movimiento Simple

• Nf3 (en inglés) o Cf3 (en español): El Caballo se mueve a la casilla f3.
• Be4 o Ae4: El Alfil se mueve a e4.
• e4: Un peón se mueve a la casilla e4 (recuerda que no lleva letra).

Capturas (Símbolo x)

Cuando una pieza captura a otra, se coloca una x entre la letra de la pieza y la casilla donde se realiza la captura.
• Cxf7: El Caballo captura la pieza que estaba en f7.
• Axd5: El Alfil captura la pieza que estaba en d5.
• Captura de peón: Se escribe la columna de origen del peón (en minúscula), la x y la casilla de destino. Ejemplo: exd5 (El peón de la columna e captura en d5).

Enroques

• 0-0: Enroque corto (hacia el flanco de rey).
• 0-0-0: Enroque largo (hacia el flanco de dama).

Jaque (+) y Jaque Mate (#)

• Dh5+: La Dama se mueve a h5 y da jaque al Rey enemigo.
• Dxf7#: La Dama captura en f7 y es Jaque Mate (fin de la partida).

Coronación o Promoción (Símbolo =)

Cuando un peón llega a la octava fila (o primera fila en el caso de las negras) y se transforma en otra pieza, se añade = seguido de la letra de la nueva pieza.
• e8=D: El peón avanza a e8 y corona una Dama.
• b1=C: El peón negro avanza a b1 y se transforma en Caballo.

## Resolución de Ambigüedades

A veces, dos piezas iguales (por ejemplo, dos caballos) pueden moverse a la misma casilla. Para evitar confusiones, se especifica la columna o la fila de origen de la pieza que se va a mover:
• Por columna: Si los caballos están en g1 y d2, y uno va a f3, se escribe: Cgf3 (El caballo de la columna g va a f3).
• Por fila: Si los caballos están en g1 y g5, y uno va a f3, se escribe: C1f3 (El caballo de la fila 1 va a f3).

## "El Mate del Pastor"

Así se escribiría una partida real completa utilizando esta notación:

1. e4 e5 (Ambos bandos mueven sus peones centrales)
2. Ac4 Cc6 (Las blancas desarrollan el alfil a c4; las negras desarrollan su caballo a c6)
3. Dh5 Cf6 (La dama blanca va a h5 amenazando mate; las negras desarrollan su otro caballo sin notar el peligro)
4. Dxf7# (La dama blanca captura el peón de f7 y es Jaque Mate)

# Apéndice B - El formato Portable Game Location (PGN)

El formato PGN (**Portable Game Notation**) es el estándar universal absoluto para almacenar, registrar y compartir partidas de ajedrez en formato digital. Fue diseñado para ser fácilmente legible tanto por seres humanos como por computadoras, lo que permitió que millones de partidas históricas y modernas se guarden en archivos de texto plano sumamente ligeros.
A continuación, te presento una descripción detallada de su origen, estructura técnica y un ejemplo real de su funcionamiento.

## Origen del formato PGN

El formato PGN fue desarrollado y especificado en 1993 por Steven J. Edwards, un informático y entusiasta del ajedrez. Su objetivo principal era solucionar la enorme fragmentación que existía en el naciente software de ajedrez de principios de los años 90, donde cada programa utilizaba su propio formato propietario cerrado.
Edwards diseñó PGN de uso libre y gratuito, basándose en la Notación Algebraica estándar, lo que garantizó una rápida adopción comunitaria. Hoy en día, cualquier plataforma de ajedrez (Chess.com, Lichess, ChessBase) o motor de inteligencia artificial (Stockfish, Lc0) exporta e importa archivos .pgn por defecto.

## Estructura Técnica

Un archivo .pgn es simplemente un archivo de texto con la extensión modificada. Se divide estrictamente en dos secciones consecutivas por cada partida: la Sección de Etiquetas (Tags) y la Sección de Movimientos (Movetext).

### Sección de Etiquetas (STR - Seven Tag Roster)

Al principio de la partida aparecen una serie de metadatos encerrados entre corchetes [ ]. Para que un archivo PGN sea válido a nivel internacional, debe incluir obligatoriamente siete etiquetas específicas (conocidas en inglés como el Seven Tag Roster), escritas en este orden exacto:
1. [Event "Name"]: El nombre del torneo o evento.
2. [Site "City, Region COUNTRY"]: El lugar geográfico o plataforma en línea donde se jugó.
3. [Date "YYYY.MM.DD"]: La fecha de inicio de la partida. Si se desconoce un dato, se usan signos de interrogación (ej. 2026.10.??).
4. [Round "Number"]: El número de ronda del torneo.
5. [White "LastName, FirstName"]: Nombre completo del jugador de las piezas blancas.
6. [Black "LastName, FirstName"]: Nombre completo del jugador de las piezas negras.
7. [Result "Result"]: El resultado final. Solo se admiten cuatro opciones: 1-0 (ganan blancas), 0-1 (ganan negras), 1/2-1/2 (tablas) o * (partida en desarrollo o resultado desconocido).

### Sección de Movimientos (Movetext)

Justo debajo de las etiquetas se escriben las jugadas de forma secuencial. Cada turno consta del número de la jugada, un punto, el movimiento de las blancas y el movimiento de las negras separados por espacios.
El texto finaliza obligatoriamente repitiendo el resultado exacto que se indicó en la etiqueta Result.

## Archivo PGN del "Mate del Pastor"

Si abrieras un archivo llamado pastor.pgn en un bloc de notas de Windows, su contenido se vería exactamente así:
pgn
[Event "Partida Amistosa de Práctica"]
[Site "Mar del Plata, ARG"]
[Date "2026.10.30"]
[Round "1"]
[White "Perez, Juan"]
[Black "Gomez, Carlos"]
[Result "1-0"]

1. e4 e5 2. Ac4 Cc6 3. Dh5 Cf6 4. Dxf7# 1-0


### Interpretación

1. Lectura de Metadatos: Cualquier software lee primero los corchetes para catalogar la partida en su base de datos. Sabrá instantáneamente que Juan Pérez le ganó a Carlos Gómez en Argentina el 30 de octubre de 2026.
2. Procesamiento del Tablero: El programa inicializa un tablero virtual con las 32 piezas en sus casillas de origen.
3. Ejecución paso a paso: El lector busca el número 1. y arrastra el peón blanco a e4, luego busca la respuesta negra a e5. Avanza secuencialmente interpretando las letras de las piezas y las casillas de destino.
4. Detección de Fin: Al encontrar el símbolo #, el programa detiene la partida, valida el Jaque Mate y confirma el cierre mediante el marcador numérico 1-0.
Si te interesa, puedo mostrarte cómo se añaden variantes alternativas (jugadas que pudieron pasar) o comentarios de texto dentro de este mismo código PGN para que los programas los muestren de forma interactiva. ¿Te gustaría verlo?


# Apéndice C - El formato Brains.json
# Apéndice D - El formato Rally.json
