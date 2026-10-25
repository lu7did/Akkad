# picoAlpha — AlphaZero/MCTS para Raspberry Pi Pico W y Pico 2 W

> **Estado:** proyecto experimental en evolución. Referencia técnica basada en la línea de base `picoAlpha(3).zip` de octubre de 2026. El `CMakeLists.txt` del firmware declara **v0.2.54**. Las redes, compilaciones y resultados sobre placas deben validarse para cada configuración; este documento no certifica rendimiento ajedrecístico ni equivalencia numérica con LC0.

## 1. Propósito y origen

**picoAlpha** es una adaptación en **C++** de la línea de motores **AlphaZero/MCTS** integrada en **Akkad / Sargon-NNUE**. Su finalidad es ejecutar, de forma autónoma, un jugador de ajedrez con búsqueda **Monte Carlo Tree Search (MCTS)** guiada por una red neuronal de **política (P)** y **valor (V)** en microcontroladores **Raspberry Pi Pico W (RP2040)** y **Pico 2 W (RP2350)**. No se trata de ejecutar el binario LC0 completo ni de trasladar un entorno Python a la placa: se implementan los componentes estrictamente necesarios para generar jugadas legales, codificar posiciones, realizar inferencias y seleccionar movimientos.

El proyecto mantiene una vinculación conceptual y funcional con los jugadores AlphaZero de Sargon-NNUE y dispone de una contraparte C++ para Windows, útil como referencia y banco de pruebas. **picoAlpha no es picoSargon**: este último sigue otra línea de jugador/evaluador. Algunas piezas de infraestructura —tablero compacto, interfaz UCI por TCP, conectividad y utilidades— comparten antecedentes y nomenclatura con picoSargon.

Los objetivos de investigación son comprobar cuánto del procedimiento AlphaZero puede conservarse bajo recursos muy reducidos, medir el compromiso entre calidad de la red, latencia y memoria, y construir una cadena reproducible de **destilación, entrenamiento, exportación e inferencia**.

## 2. Hardware y restricciones

| Característica | Raspberry Pi Pico W | Raspberry Pi Pico 2 W |
|---|---|---|
| Microcontrolador | RP2040 | RP2350 |
| CPU | Dos núcleos Arm Cortex-M0+ | Dos núcleos Arm Cortex-M33 (configuración Arm del SDK) |
| SRAM integrada | 264 KiB | 520 KiB |
| Flash habitual de placa | 2 MiB | 4 MiB |
| Conectividad | Wi-Fi 2,4 GHz | Wi-Fi 2,4 GHz y Bluetooth, según soporte de firmware |
| Capacidad para redes/MCTS | Muy restrictiva | Más margen, pero todavía muy limitada |

A diferencia de un ordenador personal, no hay gigabytes de RAM, aceleración GPU, sistema operativo general ni capacidad razonable para cargar bibliotecas LC0/PyTorch completas. **Los pesos de la red deben residir preferentemente en Flash**; la SRAM se reserva para activaciones temporales, estado de tablero, pila, árbol de búsqueda, buffers de comunicaciones y Wi-Fi/lwIP. No debe confundirse tamaño de los pesos con ocupación total de RAM: el espacio de trabajo de una capa y el árbol MCTS pueden imponer el límite real.

La Pico 2 W es el destino predeterminado en esta línea. La Pico W sigue contemplada con límites de búsqueda más modestos, pero su viabilidad efectiva exige verificar el enlazado, el uso de RAM y la operación física. Los archivos `.uf2` de una placa no son intercambiables con los de la otra.

## 3. Arquitectura general

```text
Cliente de ajedrez / torneo Sargon-NNUE
                 │ UCI sobre TCP / Wi-Fi
                 ▼
       pico_main.cpp (protocolo y control)
                 │
          Tablero y legalidad
            board.cpp/hpp
                 │
      MCTS / selección PUCT / backup
            mcts.cpp/hpp
                 │
      Codificación del historial (112×8×8)
                 │
         Evaluador integrado P/V
             ├── TinyGyal 2×16
             └── picoGyal 1×8
                 │
        Pesos compilados en Flash
```

El cliente proporciona la posición UCI y los movimientos previos. La placa reconstruye el tablero, genera acciones legales, crea o recupera parte del árbol, consulta la red para obtener **prioridades de política** y un **valor escalar** de la posición, ejecuta simulaciones y devuelve `bestmove`. No necesita una instancia de `lc0.exe` ni bindings de LC0 durante la partida.

### 3.1 Tablero: herencia de Sargon

Para reducir complejidad de dependencias y uso de memoria se utiliza una representación interna **mailbox de 120 casillas** (tablero 10×12 con borde), asociada históricamente al diseño de **Sargon**. Permite recorrer direcciones de movimiento e identificar límites sin recurrir a las estructuras extensas de motores modernos de PC. El tablero define piezas y atributos compactos; las jugadas contienen índices de origen y destino y promoción; `push`/`pop` aplican y revierten movimientos; se manejan jaque, enroque, captura al paso, promociones, repetición y condiciones de tablas.

La implementación actual usa `std::array<uint8_t,120>` para las casillas y contenedores **de capacidad fija** para listas de jugadas, deshacer y registros de posiciones (`FixedVector`, `MoveList`). Esto evita muchas asignaciones dinámicas durante el cálculo. Conviene distinguir la representación compacta de juego de la **representación de entrada de la red**: al evaluar se reconstruyen los planos de características requeridos por el modelo; no se pretende sustituir los 112 planos por los 120 bytes del tablero.

### 3.2 MCTS y PUCT

Cada arista candidata reúne un prior de política **P**, número de visitas **N** y estadísticas de valor **Q**. La selección sigue el criterio PUCT, conceptualmente:

\[
 a^* = \arg\max_a \left[ Q(s,a)+c_{\mathrm{puct}}P(s,a)\frac{\sqrt{\sum_b N(s,b)}}{1+N(s,a)} \right]
\]

Una simulación selecciona una trayectoria, expande el nodo encontrado, obtiene la evaluación P/V y retropropaga el resultado invirtiendo correctamente la perspectiva al cambiar de bando. Al finalizar el presupuesto de simulaciones, tiempo o nodos, se elige una jugada de la raíz según las estadísticas de búsqueda. La **política** prioriza dónde explorar; **el valor** estima el resultado favorable a quien mueve. Ninguno de los dos garantiza, por sí solo, jugadas correctas.

Entre las adaptaciones presentes se encuentran los topes de profundidad y nodos, control de vencimiento también durante la exploración, interrupción cooperativa, reserva estática del árbol y **expansión progresiva** de las aristas más prometedoras. El código contiene mecanismos de reutilización de descendientes de la búsqueda previa, sujetos a comprobaciones de continuidad de posición e historial; esto **no** es un caché persistente entre partidas ni garantiza que toda la búsqueda anterior pueda conservarse.

### 3.3 Evaluador embebido y relación con LC0

LC0 proporciona la inspiración del formato de entrada y de la combinación **política + valor**, pero incorporar sus bindings, dependencias, protobuf, motor de inferencia y backend genérico excedería el presupuesto razonable de la placa. picoAlpha implementa directamente en C++ un evaluador limitado a arquitecturas concretas. Los pesos se transforman en una representación compilable y quedan **embebidos en Flash**, evitando abrir o descomprimir una red `.pb.gz` en cada arranque.

Los **112 planos** incluyen información posicional de hasta ocho estados históricos, atributos relacionados con el turno y el enroque y otras características; conservar el historial correcto importa tanto para la paridad de la red como para la detección de repeticiones. La política del estudiante se expresa mediante **73 planos × 64 casillas = 4.672 índices**, y en MCTS se consultan únicamente los índices de las acciones legales. La codificación exacta de movimientos, incluidos promociones y enroque, debe coincidir en preparación de datos, entrenamiento, exportación y firmware.

**Compatibilidad con LC0 no significa identidad automática de jugadas o evaluaciones.** Es necesario verificar estructura, orden de tensores, escalas, metadatos, correspondencia de política, historial y resultados numéricos con el mismo checkpoint.

## 4. Dos redes, un evaluador seleccionado al compilar

| | **TinyGyal original (2×16)** | **picoGyal experimental (1×8)** |
|---|---|---|
| Función | Red de partida y referencia de paridad | Estudiante compacto para hardware restringido |
| Bloques residuales | 2 | 1 |
| Filtros del tronco | 16 | 8 |
| Entrada | 112 planos | 112 planos |
| Salida | Política P y valor V | Política P de 4.672 índices y valor V |
| Pesos | Red originalmente distribuida como `.pb.gz`, convertida para firmware | Aprendidos como `.pt`, exportables a cabeceras C++ y experimentalmente a `.pb.gz` |
| Estado | Ruta original conservada | Entrenamiento y validación en progreso |

> El nombre de proyecto es **picoAlpha**; para la red reducida se utiliza **picoGyal**. Las grafías «tinyGlyal» o «picoGlyal» no son los nombres de los artefactos del código.

### 4.1 TinyGyal 2×16: primera aproximación

La aproximación inicial consistió en utilizar una red TinyGyal ya entrenada, en vez de intentar entrenar una red grande en el microcontrolador. El formato original se convierte fuera de la placa a una representación C++ con **convoluciones cuantizadas INT8**, escalas de cuantización y operaciones de normalización por lotes fusionadas cuando corresponde. Las rutas iniciales conservaron partes de las cabezas y operaciones de activación en FP32 para limitar las desviaciones numéricas; las versiones posteriores añaden cuantización y optimización de la capa densa FC1. Por tanto, **INT8 no implica que absolutamente toda la inferencia sea aritmética entera**.

La red original debe mantenerse sin alterar: la conversión produce una representación derivada para el firmware. Los archivos generados, entre ellos `generated_tinygyal.hpp` y variantes de FC INT8, son artefactos de compilación, no un formato que deba cargarse por Wi-Fi durante el juego.

El cuello de botella motivador no es únicamente el tamaño del archivo, sino el volumen de multiplicaciones, activaciones intermedias y ancho de memoria por cada inferencia. Incluso una red pequeña respecto de los estándares de LC0 puede resultar costosa en RP2040/RP2350.

### 4.2 picoGyal 1×8: reducción estructural

Para disponer de un evaluador más liviano se implementó `AlphaZeroMicroNet`, con **112 canales de entrada, 8 filtros y un solo bloque residual**. Conserva el esquema de conexiones residuales y atención SE y las dos cabezas diferenciadas. La cabeza de política emplea convoluciones 8→8 y 8→80, de las que el perfil actual utiliza los primeros 73 canales; la de valor emplea convolución 8→32, aplanamiento y capas densas 2048→128→1 con salida `tanh`.

Esto reduce el trabajo del tronco convolucional, pero **no reduce proporcionalmente toda la memoria**: la entrada 112×8×8, la cabeza de política y especialmente FC1 siguen siendo relevantes. Se deben medir por separado los tamaños de red, workspace y árbol. El firmware selecciona `1x8` o `2x16` **al compilar**, sin cargar ambas redes dinámicamente en la misma ejecución.

## 5. Entrenamiento de picoGyal: destilación supervisada

El procedimiento implementado es una forma de **destilación teacher–student**: una red TinyGyal entrenada actúa como *profesora* y picoGyal aprende a reproducir su política y valor con menor capacidad. **No equivale todavía a un ciclo AlphaZero completo de autojuego → búsqueda MCTS → reentrenamiento**. En particular, las etiquetas descritas aquí proceden de la evaluación directa de la profesora, no de las distribuciones de visitas MCTS obtenidas mediante partidas de autojuego.

### 5.1 Datos y reconstrucción de partidas (`picoPrepare.py`)

La fuente es un archivo Sargon `.pb`, **base SQLite**, con tablas de partidas y posiciones: no debe confundirse con los pesos de LC0 en formato protobuf `.pb.gz`. El preparador comprueba el identificador `SARGON-PB-SQLITE-1`, reconstruye tableros legales desde las características del juego y exige una secuencia histórica consistente. Puede reconocer partidas que comienzan en la posición inicial (ply 0) o inmediatamente después de la primera jugada (ply 1) si puede reconstruirla unívocamente; **rechaza historias incompletas**, en lugar de inventar movimientos anteriores.

Para cada posición reconstruida genera el tensor de **112×8×8**, consulta a la profesora a través del evaluador LC0 disponible en el PC, recupera la política para las jugadas legales y un valor escalar, y anota estos resultados en una tabla separada `pico_distillation` del mismo SQLite. Cada etiqueta conserva la identidad SHA-256 de la red profesora, una marca de historia completa, los planos, la política y el valor. Esto permite verificar procedencia y evitar mezclar profesores diferentes.

Ejemplo orientativo desde `tools/picoDistiller/` (adaptar rutas locales):

```powershell
python .\picoPrepare.py `
  --input "..\..\..\..\Chess_History_pb\pb\zod_sample.pb" `
  --weights "..\..\..\data\runs\lc0\tinygyal-8.pb.gz"
```

La disponibilidad efectiva del backend LC0 en el PC es un requisito de esta etapa. La placa no lo necesita.

### 5.2 Separación, entrenamiento y función de pérdida (`picoDistiller.py`)

Antes de entrenar se verifica que **todas las posiciones estén etiquetadas**, que exista un único hash de profesora y que cada muestra disponga de historial completo. Se divide el conjunto **por partidas completas**, no por posiciones sueltas, para disminuir la fuga de información entre entrenamiento y validación. El porcentaje de validación es configurable (20 % en el script de ejemplo); la semilla predeterminada es 42.

La entrada de cada muestra comprende tensores de planos, vector de probabilidades de política, máscara de acciones legales y valor objetivo. La función objetivo suma:

- **Política:** entropía cruzada contra la distribución de la profesora, calculada sobre los logits de movimientos legales (con máscara).
- **Valor:** error cuadrático medio (MSE) entre el valor del estudiante y el valor objetivo.

En símbolos, con los pesos implementados actualmente: **L = L_política + L_valor**. No se debe atribuir al código una ponderación ajustable de ambas pérdidas si no existe en la línea de base.

Se utiliza **Adam**, mini-lotes, validación al terminar cada época y reducción suave del *learning rate* mediante una trayectoria cosenoidal desde `--lr` hasta `--min-lr`. En Intel XPU se deshabilitan explícitamente las variantes `foreach` y `fused` del optimizador para evitar problemas de backend observados en esa configuración. La clase `PBDataset` carga a memoria los **identificadores** de posiciones, pero lee los tensores SQLite **bajo demanda**; así se evita duplicar todo el conjunto de entrenamiento en RAM.

La infraestructura emite checkpoints `epoch1-XX.pt`, conserva `epoch_best.pt` según pérdida de validación y escribe `training_manifest.json` con identidad de profesora, partición de partidas, semilla y arquitectura. En `Ctrl+C` intenta guardar `epoch_interrupted.pt`.

Ejemplo del perfil incluido:

```powershell
python .\picoDistiller.py `
  --input "..\..\..\..\Chess_History_pb\pb\zod_sample.pb" `
  --out "..\data\runs" `
  --epoch 10 --lr 0.0001 --validation 20 `
  --batch-size 256 --device xpu
```

`--device` admite `cpu`, `cuda`, `xpu` y `auto`. Es importante evaluar la generalización sobre partidas no vistas, no solamente informar que disminuye la pérdida de entrenamiento.

### 5.3 Exportación y uso en el motor

El estudiante entrenado en PyTorch se guarda como **`.pt`**. Existen dos rutas de exportación complementarias:

1. `picoExport.py` convierte pesos entrenados en cabeceras para la implementación C++ embebida, mediante `run_createheader.ps1`.
2. `picoExportPb.py` construye experimentalmente un archivo **`picoGyal.pb.gz`**, utilizando una red TinyGyal `.pb.gz` válida como **plantilla de metadatos**, sin sobrescribirla. La compatibilidad efectiva debe verificarse mediante una carga y evaluación con `lc0.exe` y mediante comparación de tensores/salidas.

```powershell
python .\picoExport.py --input "..\data\runs\epoch_best.pt" --out "..\..\include" --name picoGyal

python .\picoExportPb.py `
  --input "..\data\runs\epoch_best.pt" `
  --template "C:\redes\tinygyal-8.pb.gz" `
  --out "C:\redes\picoGyal.pb.gz"
```

Que un archivo `.pb.gz` pueda generarse **no prueba por sí solo** que LC0 lo interprete correctamente, ni que la salida coincida con el firmware INT8. El proceso requiere una auditoría de paridad de capa, de logits legales y de valor antes de realizar afirmaciones de compatibilidad operativa.

### 5.4 Trabajo todavía abierto

El entrenamiento 1×8 **está en progreso**. La línea adjunta contiene checkpoints `.pt` y un manifiesto, lo que demuestra disponibilidad de la infraestructura y productos de entrenamiento, pero no sustituye un informe reproducible de pérdidas, paridad, ELO o fuerza de juego. Las prioridades son revisar el conjunto de ejemplos, comprobar las etiquetas y la equivalencia de codificación de política, medir discrepancias FP32/INT8, validar el `.pb.gz` con LC0 y comparar partidas sobre posiciones y presupuestos iguales. También queda por decidir si el objetivo de destilación directa es suficiente o si debe añadirse aprendizaje a partir de búsquedas/autojuego.

## 6. Optimizaciones de memoria y rendimiento

La mejora perseguida combina **menos cómputo por inferencia**, **menos asignaciones** y **más reutilización**. La línea de base incorpora, entre otras, las siguientes técnicas:

| Optimización | Mecanismo | Beneficio esperado / límite |
|---|---|---|
| Cuantización INT8 | Pesos de convoluciones y FC1, con escalas y acumuladores | Reduce almacenamiento de pesos y determinadas operaciones; activaciones y otras capas pueden seguir en FP32 |
| Kernels específicos ARM | Ruta de operaciones DSP cuando la arquitectura lo permite | Acelera productos internos compatibles; no debe suponerse en Cortex-M0+ |
| Reutilización de workspace | Buffers estáticos/reutilizables para inferencias secuenciales | Evita reservas frecuentes y picos de fragmentación |
| Evaluación selectiva de política | Recuperar logits de acciones legales sin construir innecesariamente todo el vector en MCTS | Menor memoria temporal y procesamiento auxiliar |
| Árbol compacto en SRAM | Arena estática de nodos e índices estables, límites estrictos | Uso de RAM acotado y menos trabajo del asignador |
| Expansión progresiva | Dar prioridad a aristas más prometedoras | Menos nodos expandidos inicialmente; cambia el perfil de búsqueda |
| Caché neuronal | Caché de 8 entradas con clave dependiente de los **112 planos históricos** y acciones legales | Evita recalcular evaluaciones idénticas; rendimiento depende de la tasa de aciertos |
| Reutilización MCTS | Recuperación verificada del subárbol de una jugada anterior | Ahorra exploración cuando puede reutilizarse; no es almacenamiento persistente |
| Tablero/historial compacto | `FixedVector`, movimientos pequeños, `push/pop` y posiciones compactas | Menos asignaciones, mayor control del uso de SRAM |
| Segundo núcleo | Ruta opcional de paralelismo de inferencia, condicionada por placa y compilación | Potencial de acelerar capas; hay que contar sincronización y esperas |
| picoGyal 1×8 | Reducir filtros de 16 a 8 y bloques de 2 a 1 | Menor coste de tronco frente a 2×16, sujeto al coste restante de cabezas |

**Resultados verificables frente a resultados pendientes.** La línea de base confirma la **implementación** de estas optimizaciones y contiene mecanismos de perfilado de capas, caché y memoria, así como pruebas nativas de reutilización/caché. Sin embargo, no se incorpora aquí una tabla de aceleraciones `×N`, latencias medias, ahorros exactos de SRAM o Elo porque **no se ha identificado un benchmark consolidado y homogéneo** que permita defender esas cifras para ambas placas y redes. Es incorrecto transformar el beneficio teórico de reducir el tronco 2×16→1×8 en un porcentaje medido del tiempo total de búsqueda.

Para medir progreso, registrar siempre placa/reloj/compilador, versión de firmware, arquitectura/red/hash de pesos, FEN e historial, número de simulaciones, inferencias reales, aciertos de caché, tiempos por capa, nodos visitados, arena/heap máximo, tiempo hasta `bestmove`, consumo y motivo de terminación. La comparación correcta debe hacerse bajo el **mismo conjunto de posiciones**, con y sin cada optimización, sin modificar simultáneamente red y presupuesto MCTS.

## 7. Compilación, configuración y operación

### 7.1 Estructura útil

```text
picoAlpha/
├── ARM/
│   ├── CMakeLists.txt, build.ps1
│   ├── include/          # tablero, MCTS, redes, config y pesos generados
│   ├── src/              # board.cpp, mcts.cpp, net.cpp, net_1x8.cpp, pico_main.cpp
│   └── tests/            # auditorías nativas de heap, caché y reutilización
├── tools/picoDistiller/   # preparación, entrenamiento y exportaciones
├── data/runs/lc0/        # red TinyGyal de referencia, si está disponible
└── x86/                  # contraparte y compilaciones Windows
```

### 7.2 Selección de placa y red

Se requieren Pico SDK, CMake, Ninja y toolchain ARM apropiados para el SDK instalado. El archivo `ARM/CMakeLists.txt` declara **pico2_w** como objetivo y `PICOALPHA_NET=1x8` como selección predeterminada; `2x16` se conserva como alternativa. Ejecutar desde `ARM/` o apuntar CMake a esa carpeta:

```powershell
# Utilizar los scripts de compilación disponibles en ARM/
.\build.ps1
.\build.ps1 -Board pico_w

# Alternativamente, configuración explícita en un build separado
cmake -S . -B build-pico2-w -DPICO_BOARD=pico2_w -DPICOALPHA_NET=1x8
cmake --build build-pico2-w

# Red TinyGyal original, conservando artefactos separados
cmake -S . -B build-pico2-w-2x16 -DPICO_BOARD=pico2_w -DPICOALPHA_NET=2x16
cmake --build build-pico2-w-2x16
```

La cabecera de pesos generados correspondiente debe existir y ser compatible. Verificar la versión y el identificador de red comunicados por el firmware después de instalar el `.uf2` correcto. Compilar y enlazar no basta para acreditar que la búsqueda y Wi-Fi funcionan simultáneamente dentro de los límites físicos.

### 7.3 Parámetros y protocolo UCI

Los límites y la conectividad se fijan en `ARM/include/config.h` y requieren recompilación: Wi-Fi, puerto TCP, depuración, mDNS, `AZ_SIMULATIONS`, `AZ_MAX_NODES`, `AZ_CPUCT`, `TIMEOUT_MS` y `TMAX_MS`. En la línea revisada, la Pico W tiene **48 simulaciones y 320 nodos** predeterminados; Pico 2 W, **300 simulaciones y 8576 nodos**. No son recomendaciones universales: el uso de memoria se debe inspeccionar para cada build, y el límite estático del árbol también condiciona el máximo real.

El firmware acepta comandos UCI básicos tales como `uci`, `isready`, `ucinewgame`, `position startpos`, `position fen ...`, `go`, `stop` y `quit` por el enlace TCP/Wi-Fi. Puede anunciarse por mDNS si la red lo permite. El control `stop` es cooperativo: los kernels de inferencia ya iniciados no necesariamente se interrumpen en el acto. La telemetría puede incluir información de búsqueda, motivos de corte y perfiles de memoria/inferencia.

**Seguridad:** `config.h` contiene parámetros Wi-Fi en texto claro y debe tratarse como un archivo de configuración sensible. No publicar claves ni incorporar credenciales reales a documentación, parches públicos o registros de diagnóstico. Considerar además el servicio UCI TCP como una interfaz local, no autenticada: mantenerlo en una red de confianza y evitar exponer el puerto a Internet.

## 8. Validación y criterios de aceptación

Antes de considerar lista una combinación placa + red, verificar:

1. **Integridad de red:** hash de la profesora, identidad del `.pt`, cabecera generada, selección CMake y correspondencia de dimensiones.
2. **Legalidad:** FEN, jugadas especiales, historia, jaque, tablas y respuesta UCI; ninguna jugada ilegal.
3. **Paridad del evaluador:** comparar índices legales, logits P y valor V entre PyTorch, LC0 (si se exportó `.pb.gz`), C++ Windows y firmware, con tolerancias explícitas para INT8.
4. **Memoria:** inspeccionar mapa de enlace, Flash, `.bss`, pila, SRAM dinámica y lwIP, tanto en Pico W como Pico 2 W.
5. **Tiempo:** registrar tiempo de inferencia por capa y por jugada, caché, nodos y causas de terminación bajo varias aperturas y finales.
6. **Robustez:** probar conexión/desconexión Wi-Fi, reinicio, `stop`, watchdog, límites de árbol y búsquedas consecutivas prolongadas.
7. **Calidad ajedrecística:** medir resultados contra oponentes y controles fijos. Una menor pérdida de destilación o menor latencia **no garantiza** mejora de Elo.

## 9. Alcance actual y próximos pasos

picoAlpha es a la vez un firmware de ajedrez y una plataforma de experimentación sobre inferencia neuronal en microcontroladores. La ruta original **TinyGyal 2×16** se mantiene como referencia; **picoGyal 1×8** persigue un presupuesto de cómputo menor mediante destilación de una red entrenada, conservando los 112 planos y la interfaz P/V.

El siguiente paso de mayor valor es **cerrar una validación reproducible del estudiante 1×8**: dataset y hash de profesora congelados, métricas de validación, prueba de exportación `.pb.gz` en LC0, paridad PyTorch/Windows/firmware e inferencias por segundo en hardware real. Solo después deberían compararse fuerza ajedrecística, consumo energético y ventajas de una posible fase de autojuego MCTS.

---

**Referencias internas de esta línea de base:** `ARM/src/{board,mcts,net,net_1x8,pico_main}.cpp`, `ARM/include/`, `ARM/CMakeLists.txt`, `tools/picoDistiller/{common,model,picoPrepare,picoDistiller,picoExport,picoExportPb}.py`, scripts `run_*.ps1` y notas de parches históricas. Este README documenta el estado observado, sin modificar el programa ni sus redes.
