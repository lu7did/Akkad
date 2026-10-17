# Sargon-NNUE

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

Manual de referencia consolidado de la arquitectura funcional de Sargon-NNUE. Se distingue el comportamiento implementado del alcance aún no verificado; la cronología de entregas se conserva exclusivamente como apéndice. La instalación operativa puede incorporar modificaciones locales: donde corresponda se debe verificar el contrato real con `--help` y los manifiestos de la corrida.


# Propósito y principio arquitectónico

## Objetivo general

Sargon-NNUE es una plataforma experimental para separar dos fuentes de fuerza a menudo entremezcladas en motores de ajedrez:

1.  el algoritmo que explora el árbol de juego (*player*);

2.  la función que asigna valor a una posición (*evaluator*).

El contrato conceptual continúa siendo:

``` python
Evaluator:
    evaluate(board) -> score_cp

Player:
    choose(board) -> MoveChoice
```

Los evaluators devuelven centipawns desde perspectiva blanca. Los players deciden qué posiciones deben ser evaluadas y cómo convertir esas evaluaciones en una jugada.

## Qué se intenta aislar

El proyecto intenta que puedan compararse por separado:

- profundidad y política de búsqueda;

- ordenamiento de jugadas;

- quiescence;

- evaluación estática;

- redes aprendidas;

- podas selectivas;

- límites de tiempo y de nodos;

- coste del backend de evaluación.

Esta separación es fundamental para interpretar correctamente experimentos del tipo:

    SARGON depth=3 + CLASSIC
    SARGON depth=3 + CEREBRUM
    SARGON depth=3 + STOCKFISH evaluator

porque el algoritmo de búsqueda puede mantenerse fijo mientras cambia únicamente la función de evaluación.

# Evolución del proyecto

## Bobby: conocimiento almacenado frente a política jugable

Bobby fue el punto de partida de la línea de investigación: un entorno de juego de ajedrez apoyado en conocimiento adquirido y almacenado en una base de datos de gran volumen. Podía acumular experiencias, posiciones y resultados, pero una colección extensa de datos no equivale a una *política* fiable para seleccionar jugadas. Se constató que aumentar la base implicaba mayor costo de almacenamiento y consulta sin garantizar una estimación consistente de la calidad de cada alternativa legal. El problema no era exclusivamente de escala: faltaba generalización a posiciones no observadas y un criterio de decisión robusto.

## Nyx: otra infraestructura, mismo cuello de botella estratégico

Nyx buscó superar el límite de Bobby mediante una organización diferente de los componentes y de los datos de aprendizaje. La nueva infraestructura facilitó experimentación, pero dejó visible un problema de fondo: el mecanismo de selección de jugadas seguía siendo débil. Mejorar la fuente de datos o la red no corregía automáticamente la lógica que exploraba las respuestas del adversario.

## Akkad: búsqueda, aprendizaje y necesidad de auditoría

Akkad incorporó experimentación más explícita con profundidad, extensiones y mecanismos de aprendizaje de la búsqueda. Esto hizo evidente la necesidad de registrar por separado cómo se elegían candidatas, cuánto se exploraba y de dónde provenía una puntuación. La arquitectura, todavía demasiado monolítica, dificultaba aislar el origen de una regresión: evaluación, búsqueda, integración y control temporal quedaban entremezclados.

## Sargon-NNUE: modularidad como principio científico

Sargon-NNUE separa *player* (genera y selecciona movimientos) de *evaluator* (estima valor posicional), y ubica fuera de ambos la preparación de datos, el entrenamiento, la comparación UCI y la auditoría. Challenger puede actuar como infraestructura de ejecución externa; MATCH y RALLY organizan enfrentamientos. El diseño permite usar una misma búsqueda con varios evaluadores y un evaluador con distintas búsquedas, conservar configuraciones reproducibles y diagnosticar límites concretos sin reemplazar subsistemas completos.

# Arquitectura

## Visión por capas

    PGN / partidas externas / maestros
            | prepare / resample / etiquetas
            v
    SQLite .pb --- audit dataset --- train --- checkpoint NPZ
            |                               |
            +-------------> evaluators <---+
                               ^
                            players
                        Sargon / Sargon-Plus /
                        Cerebrum / Stockfish / Random
                               |
                            UCI API
                      stdin / TCP listen
                               |
                        MATCH / SELFPLAY
                               |
                             RALLY
                               |
                        JSONL / PGN / CSV
                               |
                 sargon_audit / judge / differential

La *factory* resuelve una configuración de brain a una pareja player–evaluator; el controlador UCI recibe una posición y una instrucción de búsqueda. Los motores propios deben respetar la convención pública de evaluación en centipawns con signo positivo para las blancas y signo negativo para las negras. La implementación interna de negamax puede usar perspectiva del bando que mueve, pero debe convertir en los límites del contrato.

## Perfiles de brain y prioridades de configuración

Un archivo JSON contiene `schema_version` y el objeto `brains`. Cada brain selecciona `player`, `evaluator`, sus argumentos, rutas y metadatos `rating_elo`. Las opciones generales no pertinentes a un player pueden ignorarse cuando no generan inconsistencia; una combinación semánticamente inválida debe rechazarse. El caso especial `stockfish` como player exige evaluador `null`. Los nombres de las claves de red son específicos de cada tipo de evaluador.

## Flujo de búsqueda y valor

Para cada posición legal, el player considera jugadas, consulta el evaluador cuando corresponde, aplica la semántica terminal (mate, tablas, jugadas ilegales) y entrega `bestmove`. La profundidad principal mide plies; `qdepth` extiende de manera selectiva situaciones tácticamente no estabilizadas. No es correcto identificar `qdepth=3` con una búsqueda exhaustiva adicional de tres plies.

## Trazabilidad y reproducibilidad

Una corrida posee configuración de RALLY, perfiles de brains, manifiestos, procesos de motor, movimientos FEN y resultados. Las auditorías persistentes deben mantener el vínculo `run_id`, `match_id`, `game_id`, `ply` y `search_id` o equivalentes que permitan correlación sin ambigüedad. Los datos originales son JSONL; los CSV se derivan a posteriori y permanecen dentro del directorio de la misma corrida. Los hashes ayudan a identificar código y checkpoints, pero no sustituyen el control de versiones ni verifican por sí solos el comportamiento.

# Players: contratos, parámetros y algoritmos

## Resumen de motores

| Player        | Evaluadores admisibles                | Criterio de selección                                                               |
|:--------------|:--------------------------------------|:------------------------------------------------------------------------------------|
| `sargon`      | classic, npz, cerebrum-1.1, stockfish | Exploración clásica sobre árbol y valoración de hojas.                              |
| `sargon-plus` | Ídem                                  | SargonCore con BOOST (optimizaciones de búsqueda) y TURBO (presupuesto adaptativo). |
| `cerebrum`    | Principalmente cerebrum-1.1           | Selección a un ply mediante red y quiescence opcional, sin el conjunto BOOST.       |
| `stockfish`   | Sólo null                             | Stockfish selecciona y evalúa internamente.                                         |
| `random`      | null                                  | Jugada legal aleatoria; referencia de piso no basada en evaluación.                 |

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

## Sargon y SargonCore

El núcleo de búsqueda implementa exploración de árbol adversarial con alternancia MAX/MIN o su forma negamax, poda alpha–beta, manejo terminal, niveles iterativos y protección del resultado completo más reciente. En negamax: $$V(s,d,\alpha,\beta)=\max_{a\in A(s)}\{-V(T(s,a),d-1,-\beta,-\alpha)\}.$$ La poda es legítima cuando $\alpha\geq\beta$, siempre que la evaluación y los límites sean coherentes. El resultado elegido por la raíz puede depender del orden ante empates; una búsqueda selectiva puede depender del orden también por reducciones y podas. Los guardrails conservan el último nivel completo si el intento posterior agota el presupuesto. El núcleo conserva responsabilidades compartidas para evitar duplicar semántica terminal en Sargon-Plus.

## Sargon-Plus

La variante Sargon-Plus reutiliza Core y agrega un conjunto de optimizaciones independientes controladas por bits. BOOST cambia la estructura u orden del árbol; TURBO decide si continuar a profundidad mayor, reducir candidatos o abortar el siguiente nivel. Ningún bit BOOST debe interpretarse como aumento garantizado de fuerza competitiva; puede mejorar velocidad y perjudicar selección bajo determinadas condiciones.

## CerebrumPlayer

CerebrumPlayer considera las jugadas legales, aplica cada candidata y obtiene su valor de Cerebrum 1.1. Con `qdepth=0` conserva selección a un ply; con `qdepth>0` agrega negamax alpha–beta táctico, evaluando stand-pat en posiciones estables, capturas/promociones relevantes y todas las evasiones legales cuando está en jaque. La profundidad quiescence no representa una segunda búsqueda principal full-width. La red incremental reutiliza información del tablero padre cuando el contrato del evaluador lo permite. La evaluación terminal prevalece sobre el valor estimado de red.

## StockfishPlayer y RandomPlayer

StockfishPlayer delega selección y evaluación al ejecutable externo y aplica límites `depth`, `nodes`, `movetime`, `elo`, `stockfish-threads`, `stockfish-hash`, `timeout` y `engine-path`, según perfil. Su único evaluador admisible es `null`. RandomPlayer obtiene una jugada legal sin optimización; puede utilizar `null` como evaluador y no interpreta `depth/qdepth` como búsqueda estratégica.

# Evaluadores: estructura y semántica de valor

## Contrato y casos terminales

El evaluador responde un escalar en centipawns desde la perspectiva blanca, salvo contratos de entrenamiento que expresamente definan objetivos normalizados. $e(s)>0$ favorece blancas; $e(s)<0$ favorece negras. Jaque mate, ahogado, repetición y cincuenta movimientos pertenecen a la lógica de juego y pueden requerir historial no contenido en el vector de características; no se deben interpretar como una simple inferencia estática.

## CLASSIC

El evaluador clásico es una función determinista basada en características ajedrecísticas definidas por el código del proyecto, independiente del entrenamiento. Permite construir un baseline reproducible y etiquetar posiciones sin búsqueda principal. No debe confundirse la evaluación estática CLASSIC con las jugadas elegidas por Sargon usando esa evaluación.

## NPZ: red entrenada del proyecto

La variante NPZ utiliza el contrato de características posicionales de longitud lógica 781. En la arquitectura inicial consolidada se emplea una red densa $781\to64\to1$ con ReLU intermedia y un término de corrección de halfmove. Para un vector $x$, una formulación representativa es: $$h=\operatorname{ReLU}(W_1x+b_1),\qquad z=W_2h+b_2,\qquad e_{\mathrm{cp}}=400z+g_{\mathrm{hm}}(s).$$ La función concreta de halfmove y los nombres de tensores deben verificarse en el checkpoint/código; la fórmula describe el contrato funcional y no presupone una clave interna de archivo no verificada. El guardado `.npz` debe conservar dimensiones, pesos, sesgos y metadatos suficientes para comprobar compatibilidad. Un archivo existente ilegible no debe tratarse como si no existiera ni inicializar pesos aleatorios silenciosamente.

## Cerebrum 1.1

Cerebrum 1.1 consume una representación posicional propia y expone evaluación ordinaria y, cuando existe estado anterior compatible, evaluación incremental. La interfaz especializada admite `evaluate_with_hint(incremental=True, previous_state=...)` o su equivalente interno; la factory decide el evaluador. La inferencia incremental actualiza acumuladores de características a partir de la transición padre–hijo en lugar de reconstruir todo el estado; *no* cambia intencionalmente la semántica del puntaje. No se debe suponer compatibilidad binaria entre redes Cerebrum y NPZ.

## Evaluación Stockfish

Stockfish empleado como evaluador externo puede entregar la evaluación posicional de su NNUE sin entregar las candidatas de su algoritmo de búsqueda. Ese uso se distingue estrictamente de StockfishPlayer. Los valores terminales, la salida textual del motor y la perspectiva blanca requieren normalización, parsing robusto y tratamiento separado de estados en jaque.

## NULL

Indica que el player no requiere evaluador externo. Es mandatorio semánticamente para StockfishPlayer y aplicable a RandomPlayer. No significa evaluación cero para todos los players.

# BOOST: optimizaciones de Sargon-Plus

## Máscara y activación

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

## History Heuristic y Killer Moves

History asigna a una jugada tranquila $m$ una prioridad acumulada $H[m]$, incrementada cuando produce cortes beta. Un incremento típico es $\Delta H\propto d^2$; su papel es ordenar candidatas, no eliminar alternativas. Killer conserva jugadas tranquilas que anteriormente produjeron cortes a la misma profundidad o ply y las promueve en el ordenamiento. Una búsqueda alfa–beta exacta debería preservar el valor minimax aunque cambie el orden; las jugadas elegidas pueden diferir si existe empate o búsqueda selectiva.

## PVS y búsqueda de ventanas

Después de examinar la primera candidata con ventana completa $[\alpha,\beta]$, PVS prueba otras jugadas con una ventana de ancho mínimo $[\alpha,\alpha+\epsilon]$, donde $\epsilon$ es la granularidad de puntuación. Si el resultado supera $\alpha$ sin alcanzar el corte beta, reanaliza con ventana completa. La re-búsqueda no es opcional si el resultado de ventana estrecha es un límite insuficiente.

## TT Bounds y Hash Move First

La tabla indexa una clave Zobrist o equivalente, conserva profundidad, jugada y tipo de bound. Una entrada EXACT puede devolver el valor bajo condiciones de profundidad compatibles; LOWER y UPPER actualizan respectivamente los límites inferior y superior. El uso incorrecto de bounds puede cambiar la decisión. Hash Move First prioriza la jugada almacenada por TT, tras comprobar legalidad, para elevar la probabilidad de cortes tempranos.

## SEE y poda por intercambios

SEE estima el balance de un intercambio sobre una casilla mediante capturas y recapturas. Conceptualmente, para ganancias alternadas $g_k$, la secuencia satisface una recurrencia minimax local; podar una candidata por SEE negativo puede ahorrar nodos, pero no equivale a demostrar que la jugada sea globalmente mala (amenazas, jaques o tácticas intermedias pueden prevalecer).

## Aspiration Windows

Cuando existe una evaluación anterior $v_{d-1}$, la nueva búsqueda puede usar $[v_{d-1}-\delta,\,v_{d-1}+\delta]$. Si se obtiene *fail-low* o *fail-high*, se ensancha la ventana y se vuelve a buscar hasta disponer de un resultado utilizable. La elección de $\delta$ afecta costo y frecuencia de re-búsqueda.

## Late Move Reductions

LMR reduce profundidad para jugadas tardías consideradas menos críticas: $d'=d-1-r(d,i)$, con $r\geq 1$, aplicado solo si se cumplen guardrails tácticos, de profundidad y orden $i$. Si la búsqueda reducida contradice la ventana se puede requerir re-búsqueda a profundidad completa. La relación exacta $r(d,i)$ y umbrales se define en código, no en el contrato externo.

## Futility y Reverse Futility

Futility contrasta evaluación estática $e(s)$ y margen $M(d)$ con el límite alfa: $e(s)+M(d)\leq\alpha$ puede indicar que ciertas jugadas tranquilas no alcanzarán el límite. Reverse Futility compara $e(s)-M(d)\geq\beta$ para posibles cortes por límite inferior. Son heurísticas selectivas, no demostraciones exactas.

## Delta pruning en quiescence

Con evaluación $e(s)$, máxima ganancia material esperada $G(m)$ y margen $\Delta$, se puede omitir una captura si $e(s)+G(m)+\Delta <\alpha$, salvo excepciones tácticas necesarias. En posiciones de jaque deben contemplarse evasiones legales; stand-pat no es una alternativa legal a responder al jaque.

## Razoring

Prueba si un nodo de profundidad reducida, con $e(s)+R(d)$ claramente bajo alfa, puede resolverse por quiescence en lugar de búsqueda completa. La prueba debe respetar posiciones tácticamente peligrosas y las condiciones del motor.

## Null Move Pruning

Realiza una búsqueda de prueba pasando turno bajo condiciones restringidas. Si $-V(s_{null},d-R-1,-\beta,-\beta+\epsilon)\geq\beta$, considera un corte beta. Se debe proteger frente a posiciones de zugzwang, jaque y materiales reducidos; el hecho de que la máscara esté disponible no demuestra que el corte sea ajedrecísticamente seguro.

## ProbCut y MultiCut

ProbCut usa una búsqueda reducida y un umbral probabilístico sobre el bound beta para intentar un corte temprano, por ejemplo $V_{reducida}\geq\beta+\sigma$. MultiCut examina un subconjunto de jugadas a profundidad reducida y corta si suficientes producen fail-high. Son aproximaciones de selectividad con parámetros empíricos.

## Inferencia incremental

El bit `0x2000` solicita al evaluador aprovechar el estado anterior. Si éste implementa el contrato incremental (Cerebrum 1.1), puede evitar recomputación; NPZ y CLASSIC permanecen en evaluación convencional. Debe conservarse equivalencia de resultados dentro de tolerancias numéricas apropiadas.

## Alcance matemático y verificación

Estas ecuaciones describen la familia de algoritmos y sus desigualdades esenciales. No constituyen una especificación exacta de constantes ni umbrales locales: para un diagnóstico reproducible deben cotejarse con `players/sargon_plus.py` instalado. Activar un bit no prueba que el mecanismo haya encontrado oportunidades; los contadores de auditoría distinguen cobertura, intervención y efecto observado.

# TURBO: gestión adaptativa del presupuesto

## Modos y máscara

TURBO es independiente de BOOST. Se habilita mediante `0x01` (Adaptive Full Width), `0x02` (Adaptive Candidate Selection) y `0x03` (ambos). Los modos gestionan la decisión de iniciar el siguiente nivel, no reemplazan el evaluador ni el resultado terminal.

## Modelo de crecimiento

Sea $t_d$ el tiempo observado para completar profundidad $d$. Se estima un factor $\hat g_d=t_d/t_{d-1}$ y el costo del próximo nivel $\hat t_{d+1}=t_d\hat g_d$, ajustable por el controlador. La decisión de iniciar un nivel considera el tiempo restante $T_{rem}$ y un margen de seguridad $\eta$: $$\hat t_{d+1}\leq\eta T_{rem}.$$ El factor observado no debe tratarse como constante teórica: ramificación, ordenamiento y quiescence producen alta variabilidad. Datos censurados (nivel incompleto por timeout) no equivalen a una medición de nivel terminado.

## Adaptive Full Width

Evalúa si una búsqueda completa de todas las candidatas raíz es admisible bajo el presupuesto. Si no lo es, no inicia un nivel que previsiblemente no podrá completar y conserva la última búsqueda terminada. La respuesta final nunca debería proceder de un nivel parcial cuya comparación de candidatas no sea válida.

## Adaptive Candidate Selection

Puede estimar un subconjunto $K$ de las $N$ jugadas raíz. La fracción $f=K/N$ controla trabajo y riesgo de exclusión. Los guardrails evitan casos degenerados como $K=1$ cuando no habría comparación útil o no existe presupuesto para un solo candidato. Para posiciones similares, la decisión de reducir candidatos debe preservar la trazabilidad del conjunto seleccionado y la cobertura del nivel anterior.

## Reglas de fallback y criterios de seguridad

Si un nivel es interrumpido, se devuelve el mejor resultado del último nivel *completo*. Si la proyección excede tiempo restante se registra el descarte de nivel; si ninguna candidatura puede completarse se detiene. El costo de ordenar y auditar no debe ocultarse bajo el tiempo de búsqueda. Los límites deben tener prioridad sobre heurísticas de avance.

## Interacciones con BOOST

BOOST modifica el costo efectivo $t_d$ y la ramificación observada, lo que cambia la estimación de TURBO. Una aceleración de BOOST no implica mejor juego si el nivel completado o conjunto de candidatas cambia. La fuerza se evalúa con partidas; el costo con medidas de latencia/nodos; y las decisiones de TURBO con eventos de presupuesto, intentos y fallback.

# Integración de Stockfish

## Stockfish como evaluador

En esta modalidad Sargon, Sargon-Plus o CerebrumPlayer, según compatibilidad de implementación, gobiernan la selección de jugadas y piden a Stockfish un valor posicional de una posición. No debe asumirse que el motor Stockfish entrega su árbol de candidatos como parte de ese contrato. La salida se normaliza a centipawns con perspectiva blanca, se distingue evaluación NNUE de búsqueda principal y se controlan terminales. El wrapper puede gestionar proceso persistente y cache LRU cuando está configurado.

## Stockfish como player

Stockfish decide internamente la mejor jugada con sus métodos propios; por contrato, el evaluador externo es `null`. Los controles del perfil incluyen `engine-path`, `depth`, `nodes`, `movetime`, `elo`, `stockfish-threads`, `stockfish-hash` y `timeout`. La omisión de evaluator se interpreta como null; la indicación explícita de otro evaluador es incompatible.

## Performance, diagnóstico y límites de comparación

La velocidad y fuerza de Stockfish como player no son comparables directamente con un player propio al que Stockfish sólo ofrece evaluación: el primero controla orden, poda y red interna; el segundo retiene la política de Sargon. Existen riesgos específicos en cargar redes NNUE, extraer *Final evaluation*, interpretar `readyok`, distinguir errores de `bestmove`, y terminar procesos. Los parámetros restrictivos, como `nodes=1`, pueden reducir drásticamente la fuerza y deben registrarse antes de interpretar cualquier resultado. La auditoría conserva respuesta UCI y tiempo interno por separado.

# Entrenamiento y preparación de redes

## Cadena de producción

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

## Heurísticas de generación de señales

Los objetivos de aprendizaje no son intercambiables: (i) resultado de partida $R\in\{0,\frac12,1\}$, (ii) WDL del maestro $(W,D,L)$, (iii) centipawns estáticos CLASSIC, (iv) otras etiquetas cuando estén disponibles. Para WDL con unidades milésimas se obtiene una expectativa blanca $S=(W+D/2)/1000$. Para CLASSIC se usa el valor normalizado $C/400$ en la arquitectura documentada. Una mezcla supervisada genérica es: $$L(\theta)=\lambda_C\frac1N\sum_i(f_\theta(x_i)-C_i/400)^2+\lambda_S\frac1N\sum_i(f_\theta(x_i)-S_i)^2+\lambda_R L_R,$$ donde $\lambda$ sólo corresponde a objetivos habilitados. En la práctica no se deben mezclar magnitudes incompatibles sin normalizarlas explícitamente. La preparación permite filtrar etiquetas terminales de mate de la regresión estática y guardar procedencia. El remuestreo, la selección dispersa de movimientos, la ponderación por fase y la verificación de integridad deben interpretarse respecto de los argumentos reales del programa utilizado; no todos los filtros experimentales están garantizados en cada modo.

## Rol de PyTorch y backend NumPy

NumPy resuelve entrenamiento matricial CPU; PyTorch ofrece autograd, optimizadores, batch tensors y elección de dispositivo `cpu`, `cuda` o `xpu` si el entorno soporta la GPU. PyTorch no reemplaza el contrato de características ni resuelve por sí mismo una mala etiqueta. Entrenar en XPU obliga a validar tipos, operadores soportados y consistencia con checkpoints anteriores.

## SARGON TRAIN: argumentos y defaults documentados

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

## Partición, convergencia y métricas

El conjunto de validación se define por partida, para que posiciones vecinas del mismo juego no aparezcan en ambos subconjuntos. Una selección de entrenamiento por `--shuffle` se fija mediante semilla y se conserva en sucesivas épocas. Una época completa calcula MSE/RMSE, muestras válidas, pérdida de validación y, cuando procede, métricas de acierto de decisión o de aproximación WDL. La reducción de MSE mide fidelidad a un objetivo; no demuestra aumento de fuerza competitiva. La normalización de CLASSIC induce $MSE_{cp}=400^2 MSE_{norm}$ si las únicas diferencias son el factor lineal de escala. Para progreso estable deben controlarse fuga de partidas, mezcla de maestros, identidad del dataset y continuidad de checkpoint.

## Continuación e integridad del checkpoint

Un checkpoint existente debe cargarse y verificarse; un fallo de carga no autoriza reinicializar aleatoriamente los parámetros. Un checkpoint inexistente puede iniciar una red nueva si la operación lo pide explícitamente. El estado CPU/dispositivo de halfmove debe sincronizarse para evitar pérdida de aprendizaje entre sesiones. El entrenamiento conserva validación y exporta pesos con metadatos suficientes para reproducir arquitectura, escala y función objetivo.

## Herramientas adicionales de entrenamiento

`sargon_brainmaker.py` organiza la creación/evolución de brains, su experimentación y metadatos de rating; `sargon_selfplay.py` produce partidas de entrenamiento o evaluación consigo mismo, según perfil. Los scripts de pipeline PowerShell coordinan prepare, train, evaluación y rutas. El uso actual de redes Cerebrum 1.1 se refiere a inferencia a partir de un modelo ya entrenado; su entrenamiento externo no se identifica con el `sargon_train` que produce checkpoints NPZ.

# Infraestructura operativa y herramientas

## LISTEN y STDIN (UCI)

`sargon_listen` ofrece UCI sobre TCP; `sargon_stdin` o la capa UCI correspondiente permite conexión por entrada y salida estándares. Los comandos habituales son `uci`, `isready`, `ucinewgame`, `position`, `go`, `quit`; `bestmove` debe contener jugada legal o un marcador terminal válido, no un valor arbitrario `(none)` ante un fallo interno. La selección del brain y el tipo de evaluador se resuelven en el bootstrap del motor.

## MATCH

`sargon_match.py` enfrenta dos instancias UCI, asigna colores, aplica límites y conserva resultados CSV/PGN. Sus argumentos incluyen selección de perfil mediante `--brain`, `--idA`, `--idB`, `--pairs`, `--max-plies`, `--csv`, `--pgn`; cuando están disponibles, override de máscaras `--a-boost`, `--b-boost`, `--a-turbo`, `--b-turbo`, y `--boost-audit-dir`. El archivo de movimientos contiene FEN previo, jugada, proceso y tiempos.

## RALLY

`sargon_rally.py` interpreta la definición JSON de torneos `tournaments`, expande una lista de participantes a todos contra todos y lanza MATCH por pareja. Los campos de torneo incluyen `name`, `brains`, `plays_per_pair`, `max_simultaneous_games`, `max_game_seconds` y `pgn`. La CLI soporta `--id`, `--brain`, `--rally`, `--preflight-only`, `--scores`, `--boost-audit-dir`. *Preflight* valida inicialización UCI y respuesta `bestmove`. Una falla deja el torneo incompleto, no debe contabilizarse como derrota deportiva.

## SELFPLAY

`sargon_selfplay.py` ejecuta autocompetencia con perfiles y límites configurables; permite producir partidas para análisis o alimentar procesos de aprendizaje. Su captura de auditoría reutiliza el mecanismo estructurado, cuando está activado.

## AUDIT y JUDGE

`sargon_audit.py` puede analizar datasets de entrenamiento o el directorio completo de auditoría BOOST/TURBO. `sargon_judge.py` examina resultados y, cuando hay evaluación por posición, fidelidad numérica y discrepancias de decisiones. Las funciones no son intercambiables: AUDIT comprueba integridad/cobertura de capturas; JUDGE interpreta resultados competitivos.

## Auditoría persistente

Los eventos primarios se registran como JSONL independientes por motor y por enfrentamiento, con manifiesto de RALLY, configuración, FEN, jugada, tiempo de respuesta del supervisor y tiempo interno del motor. Las métricas de búsqueda incluyen nodos, profundidad completa, intentos, timeout y contadores específicos de BOOST/TURBO. Los informes derivados se conservan en la *misma carpeta de corrida*: `boost_report.csv`, `boost_report_moves.csv`, `boost_report_paired.csv`, `boost_report_levels.csv`, `boost_report_turbo_events.csv`, validación y cobertura.

    .\sargon_audit.ps1 --boost-audit --input ..\data\test\audit\RUN
    .\sargon_audit.ps1 --validate --input ..\data\test\audit\RUN

La validación comprueba la correspondencia uno a uno entre jugadas y búsquedas, ausencia de huérfanas y consistencia de manifiestos. Un informe `PASS` estructural no demuestra eficacia de BOOST ni exhaustividad de todos los eventos de cada algoritmo. `boost_audit_coverage.py` clasifica bits desactivados, habilitados sin oportunidad y observados; no atribuye causalidad individual a contadores de ordenación conjuntos.

## Auditor diferencial externo

`boost_differential.py` acepta FEN ya presentes en un `moves.jsonl`, ejecuta en procesos UCI separados el baseline y el experimento sobre cada misma posición, y genera `decisions.csv`, `divergences.jsonl`, `summary.json` y trazas independientes. Compara `bestmove`, puntuación, nodos, tiempo interno y latencia UCI. Por sí solo no demuestra cuál jugada es objetivamente mejor ni traza la primera rama de divergencia del árbol.

    .\sargon_boost_differential.ps1 -Base classic -Test s0001 `
      -Moves '..\data\test\audit\RUN\match_001\moves.jsonl' -Limit 20

## Reproducción y almacenamiento

Cada ejecución crea un directorio único. Es incorrecto reutilizar uno que ya contiene ; ello mezclaría evidencia de corridas distintas. Los CSV analíticos deben generarse por defecto al lado de los JSONL que los originaron, no en un directorio compartido global. La velocidad percibida se mide tanto en `response_ms` (UCI) como `elapsed_ms` (búsqueda interna); la diferencia corresponde a comunicación y overhead del entorno.

# Referencia de uso y ejemplos

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

# Deuda técnica, límites y trabajo pendiente

## Capacidad explicativa de la auditoría

La auditoría persistente conserva resultados, tiempo, profundidad y actividad interna, pero no garantiza atribución causal de una derrota a un bit específico. Los algoritmos de ordenamiento pueden producir diferencias por desempate o por interacción con búsquedas selectivas. No se almacenan todos los nodos ni se demuestra el contrafáctico de ramas podadas. La separación universal de nodos principales y de quiescence en `SargonCore` no está disponible en todas las rutas documentadas.

## Cobertura y coste de instrumentación

Es necesario comprobar cada bit en posiciones donde pueda intervenir; un bit habilitado sin eventos queda *no ejercitado*, no aprobado. Los contadores de reordenación conjunta no permiten atribuir causalidad si varios bits están activos. La auditoría puede agregar overhead, de modo que los tiempos auditados no sustituyen benchmark sin instrumentación.

## Trazabilidad completa

Algunos manifiestos pueden conservar una identificación de versión anterior a los módulos efectivamente desplegados; no deben confundirse versión de manifiesto/esquema con hash real de implementación. Mantener hashes de código, configuración, checkpoint y etiquetas de fuente; tratar los resultados de preflight como validación de conectividad, no como prueba de fuerza.

## Integridad del entrenamiento

Verificar continuidad de halfmove entre CPU y dispositivo, manejo atómico de checkpoints, separación por partida y estabilidad del objetivo al reanudar. No inferir convergencia a partir del MSE de entrenamiento aislado ni extrapolar jugadas necesarias desde una regresión lineal sin validación de fuerza de juego.

## Seguridad de heurísticas selectivas

LMR, Null Move, Futility, Delta, Razoring y MultiCut modifican el espacio efectivamente explorado; necesitan contrastación ajedrecística si aparecen deterioros. No modificar código por mera sospecha: cualquier corrección se fundamentará en un defecto confirmado y reproducible.

## Limitaciones experimentales conocidas

Un RALLY todos contra todos puede consumir muchas horas o días. Es imprescindible preservar directorios por corrida, resultados originales y configuración constante. Las aperturas únicas, determinismo y mezcla de colores pueden producir muestras correlacionadas. Evitar concluir que una modalidad es equivalente a otra sólo porque la diferencia no resulte significativa en pocos juegos. *Este capítulo agrupa los controles pendientes; no se incluye checklist operativo separado.*

# Arquitectura de módulos

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

# Red NPZ: arquitectura, valor y convergencia

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

# Cerebrum 1.1: modelo, incrementalidad y evaluación

## Alcance de la documentación

Cerebrum 1.1 es una red preentrenada usada desde el proyecto mediante un adaptador en ; los modelos operativos aparecen en archivos de texto como . El manual previo y los parches disponibles no contienen una especificación tensorial completa y verificable de cada capa del modelo externo. En consecuencia se documenta con detalle el contrato matemático de evaluación y la integración, pero *no se inventa* una topología exacta no sustentada por el código fuente del entrenador externo.

## Cómputo de valor

La red evalúa una posición a partir de características ajedrecísticas y devuelve un escalar que el adaptador convierte a centipawns de perspectiva blanca. En una arquitectura incremental NNUE genérica, un acumulador puede expresarse como $a(s)=b+\sum_{f\in F(s)}w_f$, seguido de activación y capas de salida $e(s)=g(a(s))$. Esto es una descripción de la familia de métodos, no una afirmación sobre dimensiones internas de Cerebrum 1.1. El adaptador asegura signos, normalización y tipos al pasar el valor al player.

## Inferencia incremental

Para pasar de un padre $s$ a su hijo $s'$, se actualiza el acumulador mediante $a(s')=a(s)-\sum_{f\in F_{removed}}w_f+\sum_{f\in F_{added}}w_f$. Así el costo depende de características modificadas por la jugada. La optimización es válida si los cambios de tablero, turno, enroque, promoción y en passant actualizan consistentemente el estado. La interfaz permite entregar `previous_state` como pista; si no es válido se requiere ruta de evaluación completa. El bit `0x2000` permite que Sargon-Plus solicite incrementalidad al evaluador compatible.

## Entrenamiento y convergencia

El proceso de entrenamiento externo de Cerebrum no es el de NPZ y no debe presentarse como si fuera intercambiable. Las métricas necesarias serían loss de aprendizaje, error de validación, calidad frente a maestro, saturaciones, estabilidad de pesos y rendimiento competitivo por checkpoint; los parches examinados sólo verifican la integración de inferencia y no aportan una serie auditable de esas métricas. Los modelos de época deben conservar su identificación y hash para comparar competencias sin introducir variaciones inadvertidas.

## CerebrumPlayer y alcance táctico

Con `qdepth=0` evalúa candidatas a un ply; con `qdepth>0` utiliza una continuación quiescence sobre capturas, promociones y jaques. En un RALLY reducido, `qdepth=3` presentó competitividad superior a otras variantes, pero esa evidencia no constituye una demostración universal de optimalidad. La mejora se atribuye al sistema completo de selección y evaluación, no únicamente a un checkpoint.

# Redes MCTS: fundamentos y posible integración

## Estado actual y nomenclatura

Monte Carlo Tree Search (MCTS) es un algoritmo de búsqueda por simulaciones; no constituye por sí mismo una red neuronal. Una integración moderna suele entrenar una red de *política* $p_\theta(a\mid s)$ y una red de *valor* $v_\theta(s)$, que alimentan la selección de nodos. Este apéndice describe una alternativa todavía no incorporada como evaluador/plataforma operativa de Sargon-NNUE; no presenta comandos ficticios.

## Selección y expansión

Una regla PUCT típica selecciona $a^*=\arg\max_a [Q(s,a)+c_{puct}P(s,a)\frac{\sqrt{\sum_b N(s,b)}}{1+N(s,a)}]$. Los términos $Q$, $N$ y $P$ representan valor medio acumulado, visitas y prior de política. El nodo nuevo se expande con sus jugadas legales y un valor inicial calculado por la red o por un mecanismo de rollouts. Durante backup, valores de bandos opuestos cambian signo.

## Entrenamiento autosupervisado

En un ciclo de autojuego, la política objetivo se obtiene de frecuencias de visitas $\pi(a\mid s)\propto N(s,a)^{1/\tau}$, y el valor objetivo $z\in\{-1,0,1\}$ proviene del desenlace desde el punto de vista correspondiente. Una pérdida frecuente es $$L=(z-v_\theta(s))^2-\pi^\top\log p_\theta(\cdot\mid s)+\lambda\lVert\theta\rVert^2.$$ Se alternan autojuego, almacenamiento de ejemplos, optimización y evaluación del nuevo checkpoint.

## Integración potencial con Sargon

Un player Sargon requiere un valor para las posiciones resultantes de jugadas candidatas, mientras que un sistema MCTS entrenado entrega tanto distribución de política como valor. Hay tres posibilidades: usar $v_\theta(T(s,a))$ como evaluador de cada jugada de Sargon; usar $p_\theta(a\mid s)$ sólo como ordenamiento; o utilizar MCTS como player completo. La primera mantiene la separación player–evaluator, pero desperdicia información de política; la segunda necesita cuidado para no confundir prior con valor; la tercera requiere un nuevo player. La semántica terminal, normalización de signos, gestión de tiempo y adquisición de entrenamiento deben definirse antes de adoptar cualquiera.

# Cronología de versiones y entregas

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

## Hitos de consolidación de la línea vigente

La configuración operativa incluye brains declarativos, evaluación NPZ y Cerebrum 1.1, CerebrumPlayer con quiescence opcional, BOOST por máscara independiente hasta `0x2000`, TURBO por máscara, competición MATCH/RALLY y auditoría persistente/diferencial. Un manual con fecha fija representa una instantánea de la instalación hasta el último paquete identificado, no una garantía de que todo script local contenga los mismos archivos.
