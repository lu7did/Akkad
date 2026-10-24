# Sargon-NNUE / picoAlpha.exe — migración Windows v0.6.181

## Alcance verificado

Esta entrega modifica **únicamente** `Sargon-NNUE/native/picoAlpha/`. No modifica firmware Pico, `data/`, `docs/`, entrenadores ni integración Python de Sargon.

* TinyGyal continúa siendo la selección predeterminada y se carga desde `--network path/tinygyal-8.pb.gz`.
* picoGyal se selecciona con `--model picogyal` **solamente si** ambos archivos de exportación `picoGyal.hpp` y `picoGyal_fc_int8.hpp` estaban disponibles al configurar CMake. Se enlazan en el EXE, no se cargan en tiempo de ejecución.
* MCTS: nodos con índices estables, expansión inicial de hasta 4 alternativas por prior, ampliación progresiva 1 alternativa por 8 visitas, sin reevaluar la red al ampliar; reuso verificado de subárbol tras dos jugadas UCI con compactación de índices; presupuesto 8576 nodos; motivos `complete`, `timeout` y `tree_full`; comprobación de timeout también durante la recursión; selección PUCT por visitas.
* TinyGyal: convoluciones INT8 ya disponibles en la base; nueva FC1 INT8 portable con cuantización simétrica por fila, acumuladores INT32 de cuatro vías y reutilización de buffer de activaciones; modo FP32 permanece en `picoAlpha32` o con `--precision fp32`.
* Caché neuronal LRU de 8 entradas con hash de los 112 planos y estado de tablero, igual para ambas redes.
* picoGyal: misma fuente matemática no-ARM de `net_1x8.cpp`, con workspace reutilizable, convoluciones INT8 y FC1 INT8 de cuatro acumuladores, política evaluada solo para jugadas legales, sin código `SMLAD`/`PICO_ON_DEVICE`.

## Exportaciones picoGyal

En picoAlpha (Raspberry) generar usando `picoExport.py`:

```
python picoExport.py --input ..\data\runs\epoch_best.pt --name picoGyal
```

Copiar **los dos** headers exportados a `Sargon-NNUE/native/picoAlpha/include/` o indicar otra carpeta en la configuración con:

```
-DPICOALPHA_PICOGYAL_INCLUDE_DIR=C:/ruta/headers
```

La selección de picoGyal solo se habilita si existen ambos archivos; CMake muestra un mensaje explícito. No se incluyen pesos sintéticos en este parche.

## Compilar (Windows CMake/MSVC + zlib)

En `Sargon-NNUE/native/picoAlpha`:

```
cmake -S . -B build_windows -DCMAKE_BUILD_TYPE=Release
cmake --build build_windows --config Release
```

TinyGyal — predeterminada:

```
picoAlpha.exe --network C:\ruta\tinygyal-8.pb.gz --simulations 1200
```

picoGyal — cuando haya headers y se haya vuelto a configurar CMake:

```
picoAlpha.exe --model picogyal --simulations 1200
```

Ambos aceptan `--cpuct`; UCI admite `go nodes N movetime MS`, `eval`, `position`, `ucinewgame`, `isready`.

## Pruebas en este entorno

* `cmake --build` Linux GCC/C++17: **OK** ruta TinyGyal; `picoAlpha32` modo FP32: **OK**, recompilado después de la incorporación de FC1 INT8.
* C++17 GCC: **OK** ruta picoGyal con un **checkpoint sintético de exportación**, no con el `.pt` del usuario.
* UCI TinyGyal: `position startpos`, `go nodes 50 movetime 4000` -> 50 simulaciones, jugada legal `e2e4`. Reutilización: segundo `go` tras `e2e4 e7e5` recuperó 25 nodos.
* UCI picoGyal (exportación sintética): `go nodes 12 movetime 5000` -> 12 simulaciones, jugada legal `h2h3`.
* Comparación startpos: TinyGyal INT8 `Q=0.1136834249`, FP32 `Q=0.1154972911`; resultados próximos, no idénticos.
* No se verificó MSVC/Windows ni red entrenada real; no hay pruebas de equivalencia numérica exhaustivas, ni benchmark homologado entre Windows y Pico.

## Auditoría: diferencias aún pendientes

**No se declara paridad completa con todo el firmware 0.2.53**. El ejecutable Windows incluye reutilización parcial de árbol entre búsquedas y un caché neuronal, pero **no** el formato de arena estática SRAM ni toda la instrumentación MEM/NN del firmware RP2350. El parser UCI Windows conserva búsqueda sincrónica (`stop` no interrumpe desde stdin durante `go`). Los límites de SRAM, Wi-Fi, LED, watchdog, multicore y DSP ARM no deben portarse tal cual. La fuente de pesos de TinyGyal en Windows sigue siendo `.pb.gz` externo, no el header ROM embebido de Raspberry.

La conversión FC1 INT8 en TinyGyal introduce error de cuantización: **no promete equivalencia bit a bit** con el modo FP32, aunque la arquitectura y sus pesos originales siguen intactos.
