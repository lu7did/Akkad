# picoSargon — compilacion Windows con VS Code

Se conserva el CMakeLists.txt de picoSargon v0.2.0 sin cambios, porque ya soporta PICOSARGON_PICO y PICO_BOARD.

1. Abrir esta carpeta (la que contiene CMakeLists.txt) con File > Open Folder en VS Code.
2. Generar configuracion privada (pedira contrasena):

   `& 'C:\Users\pedro\ufasta\Scripts\python.exe' tools\generate_config.py --ssid bolSPA_EXT --port 6110 --timeout-ms 0 --plies 2`

3. Desde terminal PowerShell: `.\build.ps1` para Pico W o `.\build.ps1 -Board pico2_w` para Pico 2 W.
4. Alternativa VS Code: Terminal > Run Build Task (Ctrl+Shift+B) o Terminal > Run Task > picoSargon: Build Pico 2 W.
5. Resultado: `build-pico-w\picoSargon.uf2` o `build-pico2-w\picoSargon.uf2`.

Rutas fijadas:
- CMake `C:\Program Files\CMake\bin\cmake.exe`
- Ninja `C:\Users\pedro\ufasta\Scripts\ninja.exe`
- ARM GCC `C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\11.2 2022.02\bin`
- SDK buscado bajo `C:\Users\pedro\.pico-sdk` (selecciona la version mayor si hay varias)

**Importante:** GNU Arm 11.2 puede no soportar completamente RP2350 / pico2_w. Para Pico W (RP2040) es adecuado; si Pico 2 W falla por compilador, instalar una version ARM mas nueva y cambiar `$Toolchain` en build.ps1. El SDK debe contener el soporte pico2_w.

**Reconfiguracion:** si CMake informa que el directorio build tiene un compilador anterior, eliminar solo `build-pico-w` o `build-pico2-w` y ejecutar el script nuevamente. No borrar sources ni include.

**Validacion:** estas modificaciones verifican estructura y rutas esperadas, pero no se pudo ejecutar la compilacion Pico SDK dentro del entorno Linux actual.
