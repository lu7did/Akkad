# AlphaZero-x86 — Akkad / Sargon-NNUE

**Ubicación:** `Akkad/Sargon-NNUE/x86/AlphaZero/`

Motor UCI C++ independiente con búsqueda PUCT, basado en el comportamiento de
`src/sargon_nnue/players/alphazero.py` de la línea de base adjunta. Utiliza
**la interfaz neuronal C++ de LCZero**, sin ejecutar `lc0.exe` ni reutilizar su
motor de búsqueda.

## Compilación Windows 11 x64

Requiere Visual Studio 2022 con compilador C++, Python, Git, Meson y Ninja.
Para backend Eigen se necesitan las dependencias que LC0 prepara con Meson;
puede ser necesario un entorno de compilación LC0 funcional. El proyecto
separa el código propio del checkout de LC0 en `build/lc0-src`.

```powershell
cd .\Sargon-NNUE\x86\AlphaZero
.\build.ps1 -Backend eigen
```

Alternativamente, con fuentes LC0 ya clonadas:

```powershell
.\build.ps1 -LC0Source C:\dev\lc0 -Backend eigen
```

El script configura **desde cero** un directorio Meson de compilación,
inserta el punto de entrada de Akkad en la copia de LC0, enlaza los
componentes del backend y copia el resultado como:

`Sargon-NNUE/x86/AlphaZero/build/AlphaZero.exe`

No instala `lc0.exe` ni lo lanza. El backend C++ queda enlazado al binario.
LC0 usa **Meson** para sus bibliotecas y generación de protobuf; el
`CMakeLists.txt` incluido sirve como envoltorio opcional, no sustituye Meson.

## Ejecución

```powershell
.\build\AlphaZero.exe --weights C:\networks\t1-256x10-distilled-swa-2432500.pb.gz --backend eigen
```

Opciones CLI: `--weights`, `--backend`, `--backend-options`. Los mismos valores
pueden establecerse con `setoption` mediante UCI. La carga de la red ocurre
al primer `isready`/`go`. Pesos inexistentes producen error en telemetría.

### Opciones UCI

| Opción | Default | Función |
|---|---:|---|
| `WeightsFile` | vacío | Red LC0 `.pb.gz` |
| `Backend` | `eigen` | Nombre del backend C++ LC0 compilado |
| `BackendOptions` | vacío | Parámetros LC0 de backend |
| `Simulations` | `128` | Límite de simulaciones por jugada |
| `Cpuct` | `1.5` | Constante de exploración PUCT |
| `TMax` | `15000` | Tiempo máximo por jugada (ms) |
| `Verbose` | `1` | Telemetría UCI |

`go nodes N` sobreescribe el número de simulaciones y `go movetime N`
sobreescribe el tiempo. Implementa `uci`, `isready`, `setoption`,
`ucinewgame`, `position startpos/fen ... moves ...`, `go`, `stop`, `quit`.
La búsqueda se ejecuta en un hilo para que `stop` se procese durante el cálculo.
Las líneas `info` contienen simulaciones, nodos, visitas, valor y tiempo.
Toda la salida en stdout es UCI; errores fatales del proceso se dirigen a stderr.

## Modelo matemático

La selección usa `argmax[Q(s,a)+Cpuct*P(s,a)*sqrt(max(1,sum_b N(s,b)))/(1+N(s,a))]`.
Al expandir se obtiene `q` y política por movimiento legal del backend neuronal,
se normalizan los priors y se retropropaga `v <- -v` al subir un ply. La jugada
se selecciona por máximo `(visitas, Q, P)`; si todas tienen 0 visitas, por
prior de política. Las estadísticas del árbol no persisten entre búsquedas.
`score cp` es una proyección para telemetría, no una evaluación independiente.

## Brain para Sargon-NNUE

El ejemplo `brain_example.json` utiliza **el esquema real** de
`data/brains/brains.json` y selecciona `player=lc0`, `evaluator=null`.
El adaptador Python `LC0UCIPlayer` emplea `lc0-uci-path`, `lc0-weights`,
`lc0-backend`, `lc0-uci-nodes` y `lc0-uci-options`; por lo tanto no es
necesario cambiar el factory de players para invocar `AlphaZero.exe`.
La clave `lc0-uci-options` se expresa como JSON serializado y contiene
las opciones UCI específicas `Cpuct`, `TMax` y `Verbose`.
En la configuración de ejecución deben ajustarse las rutas relativas
al punto donde `sargon_listen` resuelve los archivos y la red.

## Alcance de validación

La lógica de búsqueda y el protocolo UCI se implementan en C++.
El enlace y la ejecución con LC0 no se han verificado en Windows 11 en este
entorno; la compilación depende también del checkout de LC0 y su toolchain.
Se recomienda comparar posiciones, políticas, Q y jugadas contra el player
Python antes de declarar equivalencia funcional numérica.

**Licencias:** el programa final que enlaza componentes LCZero está sujeto a
las obligaciones de distribución de GNU GPL v3 (o posterior), además de las
licencias de dependencias aplicables.
