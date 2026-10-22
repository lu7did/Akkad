# picoAlpha — análisis de memoria y protección de placas (v0.6.182)

## Datos medidos

Entrada: `tinygyal-8.pb(2).gz`, 430.158 bytes comprimidos, 609.431 bytes como protobuf sin comprimir.
SHA256 del protobuf: `e55a27d8c06d0c53dea8e10a8e6ae8a03c7d594ed6413f0d7dd431543314f6c4`.
Conversor v0.6.181: salida de modelo embebido **1.097.572 bytes** = 1.071,85 KiB = 1,047 MiB, en Flash.
El `.hpp` generado mide aprox. 5,4 MB como texto fuente, pero **no** se copia a SRAM; el arreglo de bytes ocupa 1.097.572 bytes de Flash (más posibles efectos de alineación/linker).

La capa densa `32*64*128 = 262.144` pesos FP32 utiliza **1.048.576 bytes** de Flash. Por ello el modelo NO es íntegramente INT8; solo las convoluciones usan pesos INT8, SE y densas siguen FP32.

## Estimación de SRAM (no es medición sobre firmware UF2)

| Componente | Aproximación |
|---|---:|
| Array local `encode()` 112×64×4 | 28.672 B |
| Copia inicial `std::vector<float>` 112×64×4 | 28.672 B |
| Buffer INT8 de entrada de primera convolución | 7.168 B |
| Salida de política 80×64×4 | 20.480 B |
| Activaciones 16×64×4 cada una | 4.096 B |
| Activación valor 32×64×4 | 8.192 B |
| Árbol MCTS: 1.600 nodos, ~24 B cada uno (depende de ABI) | ~38.400 B |
| Stack, WiFi/lwIP, USB, heap, estado tablero/historial, estructuras SDK | Pendiente medir en ELF/placa |

Los buffers no están todos vivos simultáneamente. **No sumar los valores de esta tabla como máximo de SRAM.** Los picos precisos dependen del compilador, alcance de los vectores, decisiones del heap y flujo de búsqueda; usar ELF/map y marcas de agua de heap/stack para medir.

Capacidad nominal: Pico 2 W (RP2350): **520 KiB SRAM y 4 MiB Flash**; Pico W (RP2040): **264 KiB SRAM y 2 MiB Flash**. Además del modelo, el binario y librerías ocupan Flash: no se puede asegurar cabida en Pico W sin un ELF/UF2 real.

## Protección contra placa equivocada

- `build.ps1` compila **Pico 2 W por defecto**.
- `-Board pico_w` está bloqueado sin `-AllowPicoW`.
- CMake también bloquea `pico_w` salvo `-DPICOALPHA_ALLOW_PICO_W=ON`, incluso si se omite PowerShell.
- SDK produce un UF2 correspondiente a la placa/arquitectura seleccionada; **no** se afirma que cualquier cargador de terceros impida una imagen cruzada.
- Si se autoriza Pico W experimental, el UF2 tendrá ese destino; no garantiza memoria suficiente ni correcto funcionamiento.
- Se recomienda conservar nombres distintivos de los UF2 por placa y verificar la familia UF2 antes de flashear.

## Validación pendiente

No se ha compilado UF2 para ARM ni probado arranque, WiFi, TCP, paridad de inferencia, SRAM disponible o rendimiento MCTS en hardware. No considerar firmware validado hasta medir el tamaño de `picoAlpha.elf` y su mapa, ocupación de heap y stack y pruebas en Pico 2 W.
