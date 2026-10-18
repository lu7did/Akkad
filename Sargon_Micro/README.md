# Sargon Micro — Doc + Grumpy

**Versión:** v0.1.4 (experimental)  
**Plataforma objetivo:** Raspberry Pi Pico W / Pico 2 W, MicroPython  
**Desarrollo:** Visual Studio Code + MicroPico

## 1. Criterio de funcionamiento

Sargon Micro es un motor de ajedrez independiente de Sargon-NNUE de escritorio. Ofrece **una única combinación fija**: el *player* **Doc**, que busca una jugada, y el evaluador **Grumpy**, que asigna un valor a cada posición. No existe selección dinámica de players o evaluadores ni opciones `boost` o `turbo`.

El programa arranca en la placa, carga `config.bin` y `grumpy.bin`, conecta el Wi-Fi y abre un servidor **TCP/UCI**. Acepta **un cliente por vez**. Recibe las órdenes `uci`, `isready`, `ucinewgame`, `position`, `go`, `stop` y `quit`; devuelve por TCP únicamente respuestas UCI. La telemetría de conexión, desconexión y tráfico UCI se imprime por el puerto serie de depuración. Una sesión nueva no conserva el tablero de la anterior.

La búsqueda se ejecuta con un presupuesto temporal derivado de los comandos UCI; si vence el presupuesto, se conserva la mejor jugada del último nivel completado. La implementación todavía necesita validación en una placa real.

## 2. Componentes principales

| Archivo | Responsabilidad |
|---|---|
| `device/main.py` | Arranque, carga de configuración, Wi-Fi, servidor TCP y sesión UCI. |
| `device/engine.py` | Búsqueda Doc y control de tiempo. |
| `device/chesscore.py` | Tablero, FEN, movimientos, comprobación de legalidad, reglas de jaque, mate y tablas. |
| `device/grumpy.py` | Carga y evaluación con la red neuronal compacta. |
| `device/grumpy.bin` | Pesos cuantizados y firma de integridad. |
| `device/statusled.py` | Señalización de estado mediante el LED integrado. |
| `device/config.bin` | Nombre UCI, SSID, contraseña Wi-Fi y puerto TCP. Se genera localmente. |

**Convenciones del tablero:** casillas `a1 = 0` a `h8 = 63`; piezas enteras positivas para blancas y negativas para negras; jugadas `(origen, destino, promoción)`. `chesscore.py` reemplaza la dependencia de `python-chess` en la placa.

## 3. Algoritmo de búsqueda Doc

Doc utiliza **Negamax con poda alfa-beta**. Para cada jugada legal `a`, explora la posición sucesora, invirtiendo el signo porque cambia el jugador al turno:

\[
V_d(s)=\max_{a\in A(s)}\bigl[-V_{d-1}(T(s,a))\bigr].
\]

`A(s)` es el conjunto de jugadas legales y `T(s,a)` es el tablero resultante. Los límites `α` y `β` permiten omitir ramas que ya no pueden cambiar la decisión.

La versión incluye las siguientes técnicas:

- **Iterative Deepening:** profundidades principales 1, 2, 3 y 4; devuelve el último nivel completo.
- **Principal Variation Search (PVS):** examina determinadas jugadas posteriores mediante una ventana estrecha y repite con ventana completa si es necesario.
- **Late Move Reductions (LMR):** reduce la búsqueda preliminar de jugadas tardías no capturadoras. La profundidad reducida del código depende del índice de la jugada (`depth - 2 - i // 16`), con límite inferior cero.
- **Quiescence Search:** al terminar la búsqueda nominal, prolonga el examen por capturas y promociones, y contempla evasiones de jaque; el presupuesto nominal es de cuatro niveles adicionales.
- **Tabla de transposiciones (TT):** 128 entradas para reutilizar valores de posiciones visitadas.
- **Killer moves e History heuristic:** ordenan jugadas utilizando cortes previos y estadísticas de búsqueda.
- **Reverse Futility Pruning:** permite cortes selectivos cuando una evaluación estática supera suficientemente el límite beta.
- **Extensión por jaque:** incrementa la profundidad en ciertos nodos donde el jugador está en jaque.

La puntuación estática se toma del evaluador Grumpy. Para Negamax se convierte desde la convención de **blancas** a la del **jugador al turno**:

\[
E_{\mathrm{turno}}(s)=c(s)\,E_{\mathrm{blancas}}(s),\qquad c(s)\in\{+1,-1\}.
\]

En finales reglamentarios de tablas se utiliza el valor neutral `0`; los mates reciben valores de gran magnitud que incorporan la distancia en plies.

## 4. Red neuronal Grumpy

Grumpy es un evaluador compacto de **inferencia entera**, no una red de política para MCTS. Utiliza características de **pieza, color y casilla**: `2 × 6 × 64 = 768` posibilidades. Una posición activa solo las correspondientes a las piezas presentes.

La arquitectura contiene **dos acumuladores de ocho componentes** (perspectivas opuestas), activación *Clipped ReLU* y una combinación de **16 entradas a una salida escalar**. La combinación final depende de uno de **ocho grupos (*buckets*)**, seleccionados según la cantidad de piezas.

Para cada perspectiva `c` y neurona `j`:

\[
A_{c,j}=b_j+\sum_{f\in F_c(s)} W_{f,j},\qquad
h_{c,j}=\min(32,\max(0,A_{c,j})).
\]

La característica especial es que la matriz de entrada **no se guarda completa**. Cada peso se obtiene sumando coeficientes factorizados por fila y columna:

\[
W_{f,j}=R_{p,\mathrm{fila}(q),j}+C_{p,\mathrm{columna}(q),j}.
\]

La salida utiliza un sesgo y 16 coeficientes específicos del bucket `k`:

\[
N(s)=8b^{\mathrm{out}}_k+\sum_{i=0}^{15}v_{k,i}\,h_i.
\]

Finalmente, el evaluador combina la red con un **término material explícito**:

\[
E_{\mathrm{turno}}(s)\approx
\operatorname{trunc}\!\left(\frac{400N(s)}{1024}\right)+M_{\mathrm{turno}}(s),
\]

con la disposición de los acumuladores condicionada al turno. La implementación de `grumpy.py` devuelve luego el valor desde la **perspectiva de blancas**, que es la interfaz empleada por Doc. La función material utiliza valores codificados por tipo de pieza; no invoca Classic, Stockfish ni LC0.

### Formatos de red

- **`networks/grumpy.nnx`**: representación textual `NNX1` con **1.680 coeficientes enteros** entre `-31` y `32`, modificable y procesada en la PC.
- **`device/grumpy.bin`**: representación `GRMP0001` de **1.304 bytes**: cabecera, cantidad de bloques, SHA-256 y 105 bloques de 12 bytes (16 coeficientes de 6 bits por bloque).
- Al iniciar, Grumpy verifica tamaño y cabecera, comprueba SHA-256 cuando está disponible y decodifica los coeficientes a un `bytearray` de **1.680 bytes**. Un modelo inexistente o inválido impide el arranque normal.

No se carga `grumpy.nnx` en la placa: el formato textual es únicamente fuente para el conversor de escritorio.

## 5. Decisiones de diseño y trade-offs

| Decisión | Beneficio | Coste o limitación |
|---|---|---|
| Coeficientes de 6 bits y pesos factorizados | Archivo neuronal de solo 1.304 B; muy poca SRAM para coeficientes | Cálculo adicional para reconstruir cada peso usado durante una evaluación |
| Decodificar los 1.680 coeficientes una sola vez | Elimina lecturas de archivo durante la búsqueda | Utiliza ~1,7 KiB de RAM más objetos auxiliares |
| No materializar una matriz completa de pesos | Ahorra memoria crítica en Pico W | Inferencia algo más costosa en CPU |
| Aritmética entera | Evita operaciones de punto flotante neuronal | Cuantización y rango reducido pueden limitar la precisión |
| TT de 128 entradas | Evita consumir grandes cantidades de memoria | Menor aprovechamiento de transposiciones |
| `chesscore.py` puro MicroPython | Independencia de bibliotecas de escritorio | Generación legal y copias del estado del tablero pueden resultar lentas |
| Una sola sesión TCP activa | Simplifica consumo y gestión de estados | No admite partidas simultáneas |

**Límite de validación:** el proyecto cuenta con pruebas en CPython, pero **no está comprobado todavía en hardware Pico W**. Hay que medir heap disponible con Wi-Fi activo, latencia de inferencia, nodos/segundo, consumo de memoria de la búsqueda y estabilidad de las desconexiones. No debe suponerse paridad exacta de decisiones con Doc de escritorio.

## 6. LED y depuración

| Estado | LED integrado |
|---|---|
| Inicialización | Encendido fijo |
| Servidor listo | Ciclo de parpadeo de 1 s |
| Cliente TCP conectado | Ciclo de parpadeo de 3 s |
| Error terminal | Ciclo de parpadeo de 200 ms |

El puerto serie presenta conexiones, desconexiones y líneas `UCI <<` / `UCI >>`. El socket TCP no debe contener texto de depuración ajeno al protocolo.

## 7. Herramientas incluidas

| Herramienta | Ubicación | Uso |
|---|---|---|
| Conversor Grumpy | `tools/convert_grumpy.py` | Convierte el texto `.nnx` a `grumpy.bin` con SHA-256. |
| Generador de configuración | `tools/make_config.py` | Crea `config.bin`, solicitando la contraseña si se omite. |
| Ayuda PowerShell de configuración | `tools/make_config.ps1` | Lanzador auxiliar en Windows. |
| Despliegue por USB | `tools/deploy.py` | Copia los archivos de `device/` a MicroPython mediante `mpremote`. |
| Ayuda PowerShell de despliegue | `tools/deploy.ps1` | Lanzador auxiliar en Windows. |
| Cliente UCI | `tools/uci_client.py` | Prueba básica de conexión con el motor TCP/UCI. |
| Pruebas de reglas | `tests/test_chesscore.py` | Verifica reglas y movimientos de ChessCore en PC. |
| Pruebas de red | `tests/test_grumpy.py` | Verifica formato, conversión y evaluación de Grumpy. |
| Ajustes del proyecto | `.vscode/settings.json` | Configuración de MicroPico para transferir **solo `device/`**, incluyendo `.bin`. |

### Construcción y carga con Visual Studio Code

Abrir la **raíz del proyecto** como carpeta en VS Code. Con Python disponible en la PC:

```powershell
python tools/convert_grumpy.py networks/grumpy.nnx -o device/grumpy.bin
python tools/make_config.py --name "Pico Doc Grumpy" --ssid "TU_WIFI" --port 6110 -o device/config.bin
python -m unittest discover -s tests -v
```

Instalar en la placa el firmware MicroPython correspondiente a **Pico W** o **Pico 2 W**. Luego sincronizar la carpeta `device/` mediante MicroPico o utilizar `mpremote`:

```powershell
python -m pip install mpremote
python tools/deploy.py --port COM6
```

Sustituir `COM6` por el puerto USB serial de la placa. Tras reiniciar, obtener la dirección IP por consola serial y conectar un cliente UCI al puerto definido (por defecto, `6110`).

> **Seguridad:** `config.bin` contiene la contraseña Wi-Fi **sin cifrar**. No debe publicarse ni incluirse en un repositorio accesible a terceros.

## 8. Próximas mediciones

Antes de utilizar el motor en torneos conviene registrar: SRAM libre tras conectar Wi-Fi, uso máximo durante búsqueda, tiempo medio y percentil 95 por jugada, nodos/segundo a distintas profundidades, resultados de pruebas de reglas más amplias y recuperación ante caídas TCP. Estas mediciones decidirán si es necesario optimizar `push/pop`, generación legal o inferencia.
