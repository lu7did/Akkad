# picoSargon v0.2.7 — espera de consola USB serie

Parche **provisorio y deliberadamente bloqueante**. Modifica exclusivamente `src/pico_main.cpp` respecto de v0.2.6.

Después de `stdio_init_all()`, espera que `stdio_usb_connected()` confirme la apertura del terminal CDC USB. Recién después imprime el mensaje BOOT y comienza la carga de Grumpy y la conexión Wi-Fi. Así, el monitor serie verá la IP TCP en el mensaje `UCI ready TCP port ... IP ...`.

## Instalación y compilación
1. Reemplazar `src/pico_main.cpp` en el proyecto picoSargon. Mantener todos los demás archivos y configuraciones.
2. Ejecutar `./build.ps1 -Board pico_w` en PowerShell.
3. Instalar el `.uf2` resultante usando BOOTSEL.
4. Abrir el puerto COM de la Pico W en el monitor serie de VS Code (115200 baudios). El firmware **no continúa el arranque ni conecta al Wi-Fi hasta abrir el terminal**.

## Limitación
Esta espera no tiene timeout, por pedido experimental; una Pico sin un terminal USB conectado no pondrá en marcha el servidor TCP. La conexión del cable USB sola puede no bastar; es necesario abrir el puerto COM. No debe usarse como comportamiento definitivo para un dispositivo autónomo.

Solo se comprobó la presencia de las modificaciones en el fuente. La compilación cruzada ARM y el comportamiento físico deben verificarse en Windows y la Pico W.
