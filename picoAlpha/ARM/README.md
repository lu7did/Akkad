# picoAlpha ARM — Raspberry Pi Pico 2W

**Versión:** `picoAlpha-ARM v0.1.43`  
**Destino:** `akkad/picoAlpha/ARM`  
**Placa:** Raspberry Pi Pico 2 W (RP2350, ARM Cortex-M33, dos núcleos)  
**Lenguaje:** C++17  
**Protocolo:** UCI sobre TCP/IP, con mDNS opcional

## Alcance de esta entrega

Adaptación de la rama C++ `picoAlpha/src` (X86) al RP2350. La lógica del
**tablero, FEN, enroque, captura al paso, promociones y jugadas legales** se copió
localmente de `picoAlpha/src/board.cpp` y `board.hpp`, versión incluida en
el parche X86 v0.1.41. Se añadió una reserva reutilizable de memoria para las
listas de candidatos y el historial, sin cambiar las reglas de juego.

La búsqueda conserva la formulación MCTS/PUCT de X86, con dos árboles locales
independientes y combinación de estadísticas de las jugadas en la raíz. La
**infraestructura de WiFi, listener TCP, callbacks raw lwIP, UCI, mDNS, servicio
cooperativo y watchdog** se adaptó directamente del patrón de
`picoSargon/ARM/src/pico_main.cpp`. No se modifican los proyectos preexistentes.
Como el despachador debe llamar al motor picoAlpha, el archivo de transporte
no es una copia binaria sin cambios de picoSargon.

### No es todavía un firmware validado en placa

**El entorno de generación no dispone del Pico SDK ni de `arm-none-eabi-g++`**.
Por tanto no se generó un `.uf2` y no se ha comprobado el enlace, el presupuesto
real de SRAM ni el funcionamiento de WiFi/UCI en la placa. Hay pruebas de
compilación de núcleo C++ en host, paridad INT8, coordinación con dos hilos
simulados y análisis de sintaxis del transporte con cabeceras simuladas. Estas
pruebas **no equivalen a una compilación cruzada real**.

## Archivos relevantes

| Ruta | Función |
|---|---|
| `include/config.h` | Identidad única, nombre mDNS, puerto, límites de motor, memoria, telemetría |
| `include/wifi_secrets.example.h` | Plantilla de credenciales; copiar a `wifi_secrets.h` |
| `assets/picoalpha_nnue_weights.hpp` | Pesos INT8 adjuntos, compilados en Flash (solo lectura) |
| `src/board.cpp`, `include/board.hpp` | Copia adaptada del tablero X86 |
| `src/nnue_int8.cpp` | Inferencia sparse INT8 + ReLU + cabezas valor/origen/destino |
| `src/mcts_arm.cpp` | PUCT y expansión mediante nodos preasignados |
| `src/search_coordinator.cpp` | Trabajo en dos núcleos, sincronización y fusión de resultados |
| `src/pico_main.cpp` | CYW43, TCP/lwIP, UCI, WiFi, watchdog y mDNS |
| `tools/ps/build.ps1` | Compilación Windows/PowerShell |
| `tools/bash/build.sh` | Compilación macOS/Linux |
| `tests/` | Pruebas de host y referencias de paridad |

## Construcción

Primero, con el parche extraído en la **raíz de `akkad`**:

1. Instalar Raspberry Pi Pico SDK compatible con RP2350/Pico 2 W,
   el compilador ARM `arm-none-eabi-g++`, CMake y Ninja.
2. Configurar `PICO_SDK_PATH`.
3. Copiar `picoAlpha/ARM/include/wifi_secrets.example.h` a
   `picoAlpha/ARM/include/wifi_secrets.h` y definir las credenciales.
   **No incorporar ese archivo al repositorio.**
4. Ejecutar:

```powershell
cd akkad\picoAlpha\ARM
.\build.ps1
```

O en macOS/Linux:

```bash
cd akkad/picoAlpha/ARM
./tools/bash/build.sh
```

La compilación debe producir `build-pico2_w/picoAlphaARM.uf2`.

## Identidad y parámetros

Se configuran únicamente en `include/config.h`:

```cpp
UCI_NAME   = "picoAlpha-ARM";
VERSION    = "0.1.43";
MDNS_NAME  = "picoalpha";   // picoalpha.local
PORT       = 6200;
SIMULATIONS = 256;
TIMEOUT_MS  = 1500;
MAX_DEPTH   = 10;
C_PUCT      = 1.4f;
NODE_POOL_PER_CORE = 4096;
CORE1_STACK_BYTES  = 12288;
```

La función UCI `go` admite `depth`, `movetime` y `nodes` como **límites
superiores**: nunca incrementan los configurados. Los cambios UCI con
`setoption` no modifican persistentemente los límites por una orden `go`.

## Red neuronal exacta del entrenamiento

Cabecera provista: `picoalpha_nnue_weights.hpp`, con:

- `W_INPUT`: 780 × 16 = 12.480 bytes INT8;
- `W_VALUE`: 16 bytes INT8;
- `W_FROM`: 64 × 16 = 1.024 bytes INT8;
- `W_TO`: 64 × 16 = 1.024 bytes INT8.

**Total: 14.544 bytes de pesos INT8 + 4 escalas float.**

Identidad del archivo suministrado (SHA-256):
`c67d45b1dd1fdd99389bf62fff9b2e702f19b119e376b883250618fd0383e1d7`.

La red utiliza las mismas 780 características que X86 (768 pieza/casilla,
4 derechos de enroque, 8 posibles columnas de captura al paso) y la
misma orientación de casillas por bando.

Para cada neurona oculta:

\[
 h_j=\operatorname{ReLU}\left(\sum_{i\in A(s)} W_{ij}^{\mathrm{int8}}\right)
\]

El valor predictivo (desde el bando al turno) es:

\[
 v(s)=\tanh\left(s_{\mathrm{input}}s_{\mathrm{value}}
           \sum_j h_jW_{j}^{\mathrm{value}}\right).
\]

El prior de una jugada legal \(m=(f,t)\) proviene de:

\[
 P(m\mid s)=\mathrm{softmax}_{m\in L(s)}
 \left(s_{\mathrm{input}}s_{\mathrm{from}}F_f+
       s_{\mathrm{input}}s_{\mathrm{to}}T_t\right).
\]

Los arreglos de coeficientes se encuentran `const` en Flash; no se copia el
modelo completo a SRAM. Se utilizan acumuladores `int32_t` y productos
enteros; cuando ARM anuncia la extensión DSP se emplea `SMLAD` para dos
multiplicaciones-acumulaciones de 16 bits empaquetadas por instrucción.
El estado oculto cabe sin pérdida en 16 bits para las características indicadas.
La conversión final a `float` solamente se aplica a las escalas, `tanhf`,
`expf` y PUCT.

### Sustituir el modelo

Reemplazar **únicamente** `assets/picoalpha_nnue_weights.hpp` por una
exportación compatible de `picoAlpha/tools/train/export.py` y recompilar.
Mantener nombres de arrays, dimensiones (780 × 16 y cabezas 64/64/1)
y cuatro escalas. El `static_assert` rechazará dimensiones incompatibles.
No sustituir los pesos por una red de otra arquitectura sin adaptar la inferencia.

## Búsqueda y dos núcleos

Por cada núcleo se reserva al inicio una estructura `SearchWorker` y un arreglo
estático de **4096 nodos MCTS**. No hay tabla de nodos dinámica ni asignaciones
por expansión. Las listas y el historial se reservan antes de la búsqueda.
Cada núcleo conserva su propio `Board`, historial, árbol, estadísticas y buffer
de jugadas. El modelo es compartido pero inmutable.

La selección utiliza PUCT:

\[
 \operatorname*{argmax}_{a}
 \left[Q(s,a)+c_{\rm puct}P(s,a)
       \frac{\sqrt{N(s)}}{1+N(s,a)}\right].
\]

Los dos núcleos ejecutan simulaciones con el mismo plazo absoluto y dividen
la cantidad máxima configurada. El resultado se selecciona sumando las visitas
a cada jugada raíz, con la misma indexación de jugadas legales en ambos árboles.
El valor es el promedio de retropropagación de la jugada elegida, con el signo
convertido al bando al turno, como en X86.

**Diferencia deliberada respecto de X86:** dos árboles deterministas idénticos
pueden duplicar búsquedas. El núcleo 1 utiliza por defecto
`C_PUCT * CORE1_PUCT_MULTIPLIER = C_PUCT * 1.12`, de modo que su exploración
es ligeramente más amplia. No altera red, legalidad ni entrenamiento, pero
puede modificar las jugadas seleccionadas frente al X86. Para igualdad de
PUCT con X86, fijar `CORE1_PUCT_MULTIPLIER = 1.0f`.
No se afirma que esto garantice aceleración de fuerza ajedrecística; debe medirse.

### Limpieza, reserva y memoria

Los árboles MCTS se limpian explícitamente al final de cada búsqueda,
**después** de extraer las estadísticas por raíz. Sus arrays no se liberan.
El `Board` y sus vectores reservados se reutilizan por núcleo.
La comunicación de trabajos y resultados usa variables atómicas con semántica
`release/acquire`; no hay escritura concurrente en el árbol del otro núcleo.

Presupuesto estático aproximado de nodos: 2 × 4096 × 24 = **196.608 bytes**
(en la ABI host; el resultado ARM se confirmará con `.map`).
Más 12.288 bytes para el stack explícito del núcleo 1, buffers y runtime.

Controles:

- Lectura de `mallinfo().uordblks` y `mallinfo().fordblks`.
- Medición **aproximada** del espacio entre heap y stack del núcleo 0;
  rechazo de una búsqueda si el margen es positivo e inferior a 24 KiB.
- Marca `0xA5` en la pila reservada del núcleo 1; informe de bytes intactos
  después del cálculo (no es una prueba formal de seguridad de stack).
- Contador de intentos de expansión rechazados por agotamiento del pool.
- Capacidad de detener ambos núcleos al recibir `stop`, desconexión o deadline.

La SRAM libre real debe confirmarse en placa y mediante el mapa del enlazador;
`mallinfo`, el gap aproximado y el watermark son indicadores parciales.

## UCI y telemetría

El listener es `picoalpha.local:6200` cuando mDNS esté activo.
Recibe `uci`, `isready`, `ucinewgame`, `position startpos moves ...`,
`position fen ... moves ...`, `go`, `stop` y `quit`.

Durante el análisis, cada 32 simulaciones agregadas emite
`info string progress sims=... core0=... depth0=... core1=... depth1=...`.
Al terminar publica `info depth ... score cp ... nodes ... time ... nps ...`,
seguido de telemetría por núcleo, profundidad, límite usado,
memoria/pool y `bestmove <uci>`.

La puntuación `score cp` corresponde al **bando al turno** y se recupera
aproximadamente desde el valor normalizado:

\[
 cp=400\operatorname{atanh}\bigl(\mathrm{clip}(v,-0.999999,0.999999)\bigr).
\]

En la terminal USB se emiten además eventos de inicio, red y resultado
(respetando `DEBUG`). No imprimir cada nodo/simulación: causaría
sobrecarga I/O considerable sobre el microcontrolador.

## Auditoría ejecutada en esta preparación

| Prueba | Resultado |
|---|---|
| Compilación C++17 de tablero, red y MCTS en host | OK |
| 20 búsquedas consecutivas mononúcleo, 24 sims c/u | OK |
| 10 búsquedas consecutivas con dos hilos simulando núcleos, 120 sims c/u | OK |
| Paridad numérica con referencia matemática X86, 8 posiciones FEN y priors | OK (tolerancia 2e-6) |
| Core C++ con AddressSanitizer/UBSan | OK |
| Sintaxis de transporte con cabeceras compatibles simuladas | OK; no sustituye Pico SDK |
| Compilación ARM real / enlace / `.uf2` | **Pendiente: herramientas ausentes** |
| Medición real de SRAM, WiFi y rendimiento sobre Pico 2 W | **Pendiente** |

Para repetir pruebas desde un entorno Bash con C++17:

```bash
./tests/run_host.sh
./tests/run_host_multicore.sh
./tests/run_host_syntax.sh
python3 ./tests/test_nnue_parity.py
```

## Prioridad de validación física

Primero compilar el `.uf2` y revisar su archivo `.map` (Flash/SRAM) y los
warnings. Luego verificar encendido, WiFi y mDNS; ejecutar `uci`, `isready`,
`position startpos` y `go movetime 1000 nodes 64`, confirmar una única
respuesta legal y medir memoria, profundidad y NPS. Repetir con posiciones
complejas y sesiones múltiples, incluyendo `stop` y desconexiones.

Este parche incorpora archivos **solo** bajo `picoAlpha/ARM`, de modo que no
modifica `picoAlpha/src`, `picoSargon` ni `picoPixie`.
