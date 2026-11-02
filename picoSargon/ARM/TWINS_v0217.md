# picoSargon ARM TWINS v0.2.17 — parche experimental

Aplicar este ZIP desde la **raíz Akkad**. Todos los archivos incluidos están debajo de `picoSargon/ARM/`.

## Compilación

Desde `akkad/picoSargon/ARM` (adaptar la ubicación del Pico SDK):

```powershell
cmake -S . -B build-twins -DPICOSARGON_PICO=ON -DPICO_BOARD=pico_w -DTWINS=ON -DSTEROIDS=OFF -G Ninja
cmake --build build-twins
```

O `-DPICO_BOARD=pico2_w` para Pico 2 W. La versión original se compila con `-DTWINS=OFF` (valor por defecto). **Usar un directorio de build separado**; `build.ps1` anterior no recibe necesariamente `TWINS`.

La cadena UCI reporta `picoSargon v0.2.17`; el handshake comunica `info string TWINS compiled ON/OFF`. El log USB en el arranque también informa TWINS, si `DEBUG=true`.

## Modelo de trabajo

- Core 0 atiende el transporte Wi-Fi, servicio y watchdog, además de su partición de movimientos raíz.
- Core 1 realiza la otra partición, con un `Engine` persistente, TT, heurísticas, memoria de estado y stack **independientes**.
- Dos imágenes estáticas separadas de `grumpy.bin` están en `twins_grumpy.hpp` (1.304 bytes cada una); cada `Grumpy` carga su copia.
- Ambas particiones utilizan exactamente `negamax` original, junto con qdepth, TT, PVS, LMR, SEE, razoring y shortcuts según `STEROIDS`.
- La raíz mantiene una cota alfa global `std::atomic<int>`. Solo se publica un valor tras **verificación a ventana completa**. Un scout con resultado por debajo de la cota actual descarta la alternativa; no se publica como puntuación exacta.
- Una profundidad se acepta únicamente cuando **ambos** núcleos la completaron. El core que termina primero espera. Las cotas se reinician a cada profundidad.
- Core 1 dispone de una pila reservada de 16 KiB; `Engine` se reserva en almacenamiento estático en ambos núcleos. No se comparten tablas TT, buffers de jugadas ni punteros mutables NNUE.
- La búsqueda temporal es global y los fallos de tiempo/stop conservan la última profundidad terminada. La red continua siendo Flash->copia de pesos en RAM por instancia: **la duplicación de Flash no implica inferencia sobre la Flash**.

## Validación disponible

- `g++ -std=c++17 -DPICOSARGON_TWINS -fsyntax-only src/engine.cpp` OK.
- Prueba local de particiones contra `Engine::search` convencional en posición inicial a profundidades 1,2,3: puntuaciones iguales. La prueba se ejecutó secuencialmente, no con microcontrolador multicore.
- **No se compiló ni ejecutó un firmware UF2 real**: el contenedor no incluye Pico SDK ni compilador ARM. Validar build, RAM, stacks, `bestmove`, temporización y estabilidad sobre la Pico antes de usarlo en Lichess. **No reemplazar la versión competitiva sin estas pruebas.**

## Limitaciones deliberadas

- Partición fija por paridad de índice de movimiento, sin balance dinámico de trabajo.
- Publicación de alfa solo después de una búsqueda raíz completa/verificada; no comunica cotas intermedias desde los nodos internos.
- El scout de cada movimiento usa la cota global del instante en que empieza. Las actualizaciones posteriores no modifican ventanas recursivas ya iniciadas.
- Se utiliza en la raíz un scout y, si hace falta, búsqueda completa, lo que puede aumentar el número de nodos en algunos casos; el aumento de ELO/velocidad **no está demostrado**.
- El control de memoria y de los tiempos de ambos núcleos debe verificarse en placa con las dos variantes, pico_w (264 KiB SRAM) y pico2_w (520 KiB SRAM).
