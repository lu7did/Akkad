# Sargon-NNUE — Manual de arquitectura, algoritmos y operación

**Proyecto Akkad · Sargon-NNUE · Windows 11 / Python / motores UCI**

## 1. Alcance

Sargon-NNUE es una plataforma de experimentación con motores de ajedrez, funciones de evaluación clásica y neuronal, búsqueda minimax/alpha-beta, búsqueda Monte Carlo tipo AlphaZero, etiquetado de posiciones, aprendizaje supervisado, competiciones y auditoría. Separa tres responsabilidades: **player** (elige una jugada legal), **evaluator** (estima el estado) y **orquestador** (partidas, entrenamiento, red, métricas y archivos). Un player puede ser nativo de Python, un ejecutable UCI local o un motor UCI remoto por TCP.

Este documento describe Sargon-NNUE y sus **adaptadores** hacia motores externos; no documenta el diseño, implementación, compilación o firmware de picoSargon ni picoAlpha.

## 2. Organización y contratos

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

## 3. Players y evaluadores

### 3.1 Players

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

### 3.2 Evaluadores

- `classic`: evaluación heurística de Sargón, sin red neuronal.
- `npz`: red local con parámetros serializados por NumPy.
- `stockfish`: análisis escalar obtenido de Stockfish cuando se utiliza como evaluador de otro player.
- `lc0`: inferencia neuronal LCZero con probabilidades de política y valor/WDL, según el adaptador y la arquitectura de la red.
- `tinygyal`: acceso especializado a redes compactas LC0 compatibles con el backend configurado.
- `grumpy`: evaluación mediante pesos de red Grumpy, cuando se usa como evaluador independiente.
- `cerebrum-1.1`, `cerebrum-2`/`cerebrum`: importadores de redes Cerebrum.
- `null`: evaluador nulo para programas externos con motor de búsqueda y evaluación autónomos.

**Perspectiva de los valores.** Una utilidad de preparación puede almacenar valores en `[0,1]`, un evaluador de búsqueda puede producir centipeones y LC0 puede informar WDL. No son magnitudes intercambiables sin una transformación explícita. Una conversión habitual es `v = P(win) - P(loss)` desde la perspectiva del jugador al turno; la esperanza de puntuación es `P(win) + 0.5 P(draw)`.

## 4. Sargón básico: minimax, negamax y alpha-beta

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

## 5. SargonPlus: mejoras de búsqueda y control de recursos

`SargonPlusPlayer` parte del núcleo Sargon y dispone de dos máscaras **independientes**: `--boost` de 16 bits (`0..65535`) y `--turbo` de 8 bits (`0..255`). El valor `0` desactiva las mejoras controladas por esa máscara; esto permite contrastar el motor con la línea de ejecución del núcleo básico.

### 5.1 Máscara `--boost`

| Bit | Máscara hexadecimal | Mejora |
|---|---|---|
| 1 | `0x0001` | *History heuristic*: priorización de jugadas que provocaron cortes |
| 2 | `0x0002` | *Killer moves*: jugadas no capturadoras exitosas a una misma profundidad |
| 3 | `0x0004` | PVS / NegaScout: ventana estrecha para jugadas posteriores a la primera |
| 4 | `0x0008` | Tabla de transposición con cotas `EXACT`, `LOWER`, `UPPER` |
| 5 | `0x0010` | Examinar primero la mejor jugada almacenada en la tabla hash |
| 6 | `0x0020` | *Static exchange evaluation* (SEE) para podas tácticas |
| 7 | `0x0040` | Ventanas de aspiración alrededor de la evaluación anterior |
| 8 | `0x0080` | *Late move reductions* (LMR): reducción selectiva en jugadas tardías |
| 9 | `0x0100` | *Futility* / *reverse futility pruning* |
| 10 | `0x0200` | *Delta pruning* en búsqueda de quietud |
| 11 | `0x0400` | *Razoring*: transición temprana a comprobación táctica |
| 12 | `0x0800` | *Null move pruning*: prueba de ceder el turno en condiciones admisibles |
| 13 | `0x1000` | *ProbCut* / *MultiCut*: inferencia de cortes mediante búsquedas reducidas |
| 14 | `0x2000` | Evaluación incremental: reutilización de contribuciones entre posiciones |

La combinación se expresa como OR binario. Por ejemplo, history + killers + TT-bounds + hash-first = `0x0001 | 0x0002 | 0x0008 | 0x0010 = 0x001B`, equivalente a decimal `27`. Las características pueden habilitarse de forma individual para medir efecto en fuerza, tiempo y nodos.

**Tabla de transposición.** Una entrada contiene profundidad, puntuación, bandera de cota y mejor movimiento. Su uso como cota exige cotejar la profundidad cubierta y el intervalo original de búsqueda. **PVS** busca la primera variante con ventana completa y trata de refutar las restantes con ventana estrecha; si una alternativa supera la expectativa estrecha puede requerir nueva búsqueda completa. **LMR**, *null move*, *razoring*, *futility* y *ProbCut* son heurísticas selectivas: aceleran a costa de poder alterar la exploración de un minimax exhaustivo.

### 5.2 Máscara `--turbo`

| Bit | Máscara | Operación |
|---|---|---|
| 1 | `0x01` | `adaptive-full-width`: decisión de ejecutar o saltar el siguiente nivel completo según presupuesto proyectado |
| 2 | `0x02` | `adaptive-candidate-selection`: profundización de un subconjunto de candidatos atendiendo al coste y tiempo restante |

La duración esperada de un nivel puede aproximarse mediante `T(d+1) ≈ T(d)·g`, donde `g` es el factor de crecimiento observado. Si `T_estimado` supera el tiempo disponible, el planificador evita comenzar una iteración que probablemente no terminará y conserva la mejor información completada. La selección de candidatas permite invertir la fracción restante del presupuesto en las principales jugadas; cuando queda una sola candidata, profundizarla no constituye una comparación competitiva adicional y la política de búsqueda debe respetar el presupuesto establecido.

`--boost` cambia la *eficiencia o selectividad de la búsqueda*; `--turbo` gestiona *qué trabajo se intenta* dentro del presupuesto de tiempo. Ambos sistemas mantienen contadores de auditoría para comparar activaciones y efectos. Los valores de máscaras no representan una escala ordinal de fuerza: cada bit tiene significado específico.

## 6. AlphaZero: red de política/valor y MCTS

AlphaZero sustituye la expansión determinista a profundidad fija por una búsqueda Monte Carlo guiada por una red `f_θ(s) = (P_θ(s), V_θ(s))`. La salida `P` distribuye probabilidades entre acciones legales; `V` representa expectativa de resultado en la perspectiva seleccionada. En los casos LC0/WDL se conserva el vector `(W,D,L)` hasta que un adaptador necesite un valor escalar.

### 6.1 Codificación de acciones

El catálogo de acciones implementado por `az_core.py` tiene **64 × 73 = 4672** índices. Se toma la casilla inicial (64 opciones) y uno de 73 planos: 56 desplazamientos direccionales (8 direcciones × distancias 1..7), 8 saltos de caballo y 9 promociones menores (3 piezas × 3 desplazamientos). Las promociones a dama se cubren mediante el movimiento direccional correspondiente. Antes de normalizar probabilidades, se enmascaran todas las acciones ilegales. `action_id(board,move)` es una operación de codificación, no de valoración.

### 6.2 PUCT

Por arista `(s,a)` se conservan estadísticas `N(s,a)` (visitas), `W(s,a)` (valor acumulado), `Q(s,a)=W/N` (promedio) y `P(s,a)` (prior de la red). Una variante estándar de la regla de selección es:

\[
a^* = \arg\max_{a\in A(s)}\left[Q(s,a)+c_{puct}P(s,a)\frac{\sqrt{\sum_b N(s,b)}}{1+N(s,a)}\right].
\]

El primer término favorece jugadas que los recorridos valoraron bien; el segundo asigna exploración a alternativas prometedoras aún poco visitadas. `c_puct` determina el equilibrio. Las variantes pueden incorporar normalizaciones, ruido de exploración en raíz y reglas particulares de desempate.

### 6.3 Una simulación

1. **Selección:** se desciende desde la raíz aplicando la regla PUCT.
2. **Expansión:** en un nodo aún no desarrollado se obtienen jugadas legales y sus prioridades `P` mediante la red. Las probabilidades ilegales se anulan y el resto se normaliza.
3. **Evaluación:** se obtiene `V` o WDL para la hoja. Una posición terminal aporta su resultado definitivo en lugar de inferencia.
4. **Backup:** se actualizan `N`, `W` y `Q` a lo largo del trayecto. En ajedrez de suma cero, el valor cambia de signo cuando cambia el jugador al turno.
5. **Decisión:** tras consumir tiempo/simulaciones se selecciona la jugada de raíz conforme a visitas y a la temperatura definida por el modo de juego o entrenamiento.

La formulación de respaldo, en una arista visitada, es `N ← N+1`, `W ← W+v`, `Q ← W/N`, utilizando la perspectiva correcta. Un mayor número de visitas no demuestra exhaustividad: MCTS prioriza una estimación estadística guiada por la red.

### 6.4 Estado, historial, caché y límites

El estado de una posición contiene las piezas y datos de legalidad, pero algunas propiedades (repetición, contexto de jugadas, planes de red dependientes del historial) requieren secuencia de posiciones. Las etiquetas LC0 distinguen historial disponible e incompleto. La **caché de inferencias** puede compartirse durante una partida y se libera al concluirla; no se persisten entre partidas las estadísticas de árbol `N/W/Q` ni se mezclan evaluaciones obtenidas mediante redes de distintas identidades.

## 7. LCZero como evaluador, generador de etiquetas y player

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

## 8. Preparación y etiquetado: `sargon_prepare`

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

## 9. Entrenamiento: `sargon_train` y modelos AlphaZero

### 9.1 Evaluador clásico NPZ

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

### 9.2 Política/valor AlphaZero

Para una red dual, el objetivo puede reunir error de valor, entropía cruzada de política y regularización:

\[
L(\theta)=(v_\theta-z)^2-\pi^T\log p_\theta+\lambda\|\theta\|_2^2.
\]

`z` es el resultado o valor objetivo, `π` es la distribución objetivo sobre acciones (histórica o derivada de visitas MCTS) y `p_θ` es la predicción de política. Las acciones ilegales se enmascaran tanto al entrenar como al utilizar la red. Para evitar contaminación de validación entre posiciones de una misma partida, la partición se realiza por **partidas completas**, y el muestreo de posiciones se aplica posteriormente dentro del conjunto de entrenamiento.

Los programas `az_prepare.py`, `az_policy.py`, `az_seed_train.py`, `az_train.py`, `az_model.py` y `az_mcts_label.py` separan preparación, construcción de políticas, aprendizaje de semilla, entrenamiento de política/valor y generación de objetivos MCTS. En el aprendizaje por autojuego, la distribución de visitas proporciona la política objetivo, y el resultado de la partida proporciona crédito de valor a estados anteriores, con signo según el jugador.

## 10. Formatos de red: NPZ, NPX, PB.GZ y otros

| Extensión | Identidad | Contenido / interoperabilidad |
|---|---|---|
| `.npz` | Red de evaluación de Sargon-NNUE | Archivo de arrays NumPy, con arquitectura 781–64–1 y claves descritas arriba |
| `.npx` | Formato NNUE de **picoSargon** | Representación propia de pesos NNUE asociada al motor picoSargon; distinta del contenedor NumPy NPZ |
| `.pb.gz` | Redes **LC0** | Pesos y metadatos de arquitectura serializados y comprimidos, interpretados por el backend LC0 |
| `.pt` | Checkpoint PyTorch | Estado de tensores de entrenamiento; para utilización por LC0 se requiere conversión compatible a `.pb.gz` |
| `.bin` | Pesos binarios externos | Por ejemplo, pesos Grumpy usados por adaptadores específicos; no es automáticamente equivalente a NPX |

La capa de integración de Sargon-NNUE no presupone que `.npz`, `.npx` y `.pb.gz` sean formatos intercambiables. Sus lectores interpretan arquitecturas distintas. La existencia de `grumpy.bin` dentro de un proyecto no cambia la definición de `.npx`: son artefactos diferentes y deben identificarse por su lector/serializador concreto.

## 11. Integración local C++ x86 por UCI

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

## 12. Player `external`: motor UCI sobre TCP

El adaptador `players/tcp_external.py` acepta un endpoint **`host:puerto`**, sin prefijo `tcp://` ni `http://`. Ejemplos válidos: `127.0.0.1:6100`, `motor.ejemplo.local:6110` o `[::1]:6100`. El puerto debe estar en `1..65535`; el timeout del adaptador es positivo y su valor inicial en la clase es `30000 ms`.

Una sesión se establece con la secuencia `uci`/`uciok`, `isready`/`readyok`, `ucinewgame` y una nueva comprobación `isready`. Para jugar se transmite el **historial completo** de la partida cuando existe, preferentemente `position startpos moves ...`, o `position fen <fen> moves ...` si parte de una posición inicial personalizada. Se envía después `go` **sin límites impuestos por el cliente**, porque el servidor externo gobierna sus propios recursos. Se consume telemetría `info` cuando esté disponible y se espera `bestmove`. La jugada se valida antes de incorporarse a la partida. En cierre se envía `quit`.

Este contrato hace que un motor C++ ubicado en otro equipo o un UCI accesible mediante puente TCP pueda participar sin copiar sus pesos ni sus fuentes a Sargon-NNUE.

## 13. Configuración de brains, CLI y defaults

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

## 14. Auditoría, benchmarks y reproducibilidad

`Sargon-NNUE` incluye herramientas de comparación de jugadores y de evaluadores. Las métricas incluyen victorias/tablas/derrotas, puntuaciones, Elo, duración, profundidad, nodos y, en pares de evaluaciones para las mismas posiciones, desviación media absoluta y máximo error. `sargon_arbiter` lee posiciones FEN y escribe tablas comparables como `data/test/arbiter.csv` y `data/test/arbiter_pairs.csv`.

En entrenamiento se diferencian pérdidas de *train* y *validation*, las fuentes de etiquetas y la identidad de cada red. Para motores MCTS, el número de simulaciones y de nodos explorados no debe confundirse con la profundidad alpha-beta. En las pruebas de `--boost`/`--turbo`, el criterio comparativo es medir fuerza, latencia y nodos en las mismas posiciones y presupuestos, además del resultado de las partidas.

## 15. Secuencias operativas de referencia

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

## 16. Referencia de módulos

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
