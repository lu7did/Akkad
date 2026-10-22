# picoAlpha firmware v0.2.12 — parche Akkad v0.6.181

Proyecto independiente para Raspberry Pi **Pico W (RP2040)** y **Pico 2 W (RP2350)**. No modifica picoSargon ni picoAlpha Windows. Comparte el motor de tablero y la lógica TinyGyal/PUCT adaptada a firmware, TCP UCI, WiFi, mDNS condicional, consola USB y LED del proyecto picoSargon.

## Requisito obligatorio: TinyGyal-8 original

**No se incluye una red ficticia:** no estaba `tinygyal-8.pb.gz` en los ZIP de líneas de base recibidos. La red correcta debe suministrarla el usuario. El build **falla deliberadamente** si falta `include/generated_tinygyal.hpp`.

Desde PowerShell en esta carpeta:

```powershell
C:\Users\pedro\ufasta\Scripts\python.exe .\tools\convert_tinygyal.py --input "C:\ruta\tinygyal-8.pb.gz"
.\build.ps1 -Board pico_w
.\build.ps1 -Board pico2_w
```

El conversor no necesita dependencias Python externas. Convierte LINEAR16 a INT8 simétrico por canal con escalas y batchnorm fusionado, deja SE/capas densas en FP32 para preservar la semántica de picoAlpha Windows, y genera `include/generated_tinygyal.hpp` (Flash, no archivo en runtime). Los pesos INT8 permanecen en Flash y no se duplican en SRAM; buffers de activación y MCTS se alojan en SRAM. El archivo generado ocupa varios MB de *texto C++*, pero el binario de pesos es notablemente menor. Verificar espacio final de Flash y SRAM en ambas placas; **Pico W podría exceder límites de memoria**.

El script `build.ps1` usa las rutas de herramientas ya configuradas en picoSargon (CMake, Ninja, gcc, Pico SDK, pioasm, picotool). Ajustarlas en el propio script si la instalación cambió. Se produce `build-pico-w/picoAlpha.uf2` o `build-pico2-w/picoAlpha.uf2`. Este paquete no incluye UF2 precompilado.

## Configuración

Editar `include/config.h` y recompilar. Los parámetros se mantienen *fijos en firmware*: SSID, PASSWORD, PORT (6110), TIMEOUT_MS, DEBUG, UCI, WIFI_RETRY_MS, MDNS_ENABLED, MDNS_HOSTNAME, MDNS_SERVICE_NAME, AZ_SIMULATIONS, AZ_CPUCT, TMAX_MS, AZ_MAX_NODES. `TIMEOUT_MS=0` elimina ese límite pero `TMAX_MS` puede seguir vigente. Si los dos tiempos son cero, ninguna duración limita por reloj, aunque sí AZ_SIMULATIONS y AZ_MAX_NODES. `DEBUG=true` espera USB CDC, igual que picoSargon. **No se debe publicar config.h con credenciales reales.**

`uci`, `isready`, `ucinewgame`, `position startpos [moves ...]`, `position fen ... [moves ...]`, `go`, `stop`, `quit` se reciben por TCP. El mDNS es `picoalpha.local` si la red permite anunciarlo. LED: arranque encendido; WiFi sin conexión triple pulso; conectado fijo; búsqueda 2 s ON/2 s OFF, igual que picoSargon. Las preferencias de `go` del cliente no alteran los límites fijados por `config.h`.

## Diferencias deliberadas de arquitectura

- INT8 obligatorio en convoluciones; no hay ruta FP32 ni separación player/evaluador.
- Modelo compilado en Flash y leido sin parsear protobuf ni descomprimir gzip en el dispositivo.
- Historial real para la codificación TinyGyal, igual que el motor Windows.
- PUCT/softmax/Q con respaldo alternando perspectiva; árboles reconstruidos por búsqueda, no persistidos.
- Número máximo de nodos del árbol y profundidad de recursión acotados; una búsqueda puede finalizar por `tree_limit` antes que AZ_SIMULATIONS. `stop` se comprueba entre simulaciones y no interrumpe una inferencia de red ya comenzada.
- Red de valor FP32 grande conservada en Flash para mantener similitud numérica; no todo el modelo está cuantizado. Una cuantización completa de las capas densas cambiaría el evaluador y requiere validación de paridad antes de adoptarse.

## Validaciones pendientes antes de usar en partidas

1. Convertir **la misma red** que usa el motor Windows y verificar el hash de origen.
2. Compilar ambos targets con SDK real, inspeccionar tamaño de UF2 y memoria, en especial RP2040.
3. Probar arranque WiFi, conexión TCP/UCI, LED y búsquedas cortas en placas reales.
4. Comparar logits, Q y `bestmove` con Windows INT8 para posiciones de referencia.
5. Medir latencia de inferencia, presión de heap, watchdog y comportamiento de `stop` bajo carga.

Estado de esta entrega: **fuentes y herramientas preparadas; compilación cruzada, paridad numérica y pruebas sobre hardware no verificadas**. No declarar aptitud para uso competitivo hasta cerrar las pruebas.

## Memoria y destino seguro v0.6.182

El destino predeterminado es **Pico 2 W**. Pico W acepta `-Board pico_w` y emite una advertencia; consulte `MEMORIA_Y_SEGURIDAD_v0.6.182.md`. Se incluye `generated_tinygyal.hpp` construido a partir de la red proporcionada.

## Perfil experimental Pico W (v0.6.183)

Pico 2 W sigue siendo el destino predeterminado: `.\build.ps1`.
Pico W se compila con `.\build.ps1 -Board pico_w` y una advertencia, sin permiso especial.

`include/config.h` fija por compilacion perfiles editables:
Pico 2 W: `AZ_SIMULATIONS=128`, `AZ_MAX_NODES=1600`.
Pico W: `AZ_SIMULATIONS=48`, `AZ_MAX_NODES=320`.
Menos simulaciones reducen trabajo y tiempo; **no** garantizan un menor uso de SRAM.
`AZ_MAX_NODES` limita el tamano del arbol y su reserva de memoria.
Para certificar Pico W se requieren UF2, mediciones de SRAM y pruebas WiFi/UCI/MCTS reales.
No intercambiar los UF2 de Pico W (RP2040) y Pico 2 W (RP2350).
