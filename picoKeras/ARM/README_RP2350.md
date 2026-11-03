# picoKeras ARM v0.1.20 — compilación nativa Pico 2 W / RP2350

## Origen y alcance

Parche incremental hecho **solo a partir de `akkad(10).zip`**; reemplaza el sistema de build ARM de escritorio de esa línea de base. No cambia `picoKeras/X86`, ni `src/board.cpp` ni `include/board.hpp`. La antigua entrada de escritorio `src/main.cpp` y `src/model.cpp` se conservan en el proyecto, pero **no se compilan** para Pico 2 W.

La entrada nueva `src/pico_main.cpp` ofrece UCI por USB-CDC y servidor UCI TCP opcional (`-WifiSsid`, `-WifiPassword`) con Pico W CYW43 y lwIP RAW. Mantiene la política de selección a **1 ply**: evalúa todas las jugadas legales con una red escalar desde el punto de vista del rival y selecciona el valor mínimo. El modelo se enlaza en flash; **no** se accede a archivos en ejecución. El motor no soporta cargar dinámicamente `.tflite` por TCP ni `--network` en la placa.

El sistema utiliza Pico SDK 2.x, Ninja, GNU ARM GCC, Python y TFLM **compilado para Cortex-M33**. TensorFlow Desktop, MSVC y `.lib` Windows no sirven para el firmware. La biblioteca de TFLM se obtiene del checkout local `ARM/third_party/tflm-tree` (dependencia externa, no incluida en el parche); si falta la `.a`, `build.ps1` intenta generarla con `GNU make` usando `TARGET=cortex_m_generic TARGET_ARCH=cortex-m33 microlite`.

## Construcción PowerShell

```powershell
cd C:\Users\pedro\github\bobby\akkad\picoKeras\ARM
.\build.ps1 -Help
.\build.ps1 -Model C:\models\small-int8.tflite -WifiSsid "MiSSID" -WifiPassword "MiClave"
# o solo USB, sin credenciales Wi-Fi:
.\build.ps1 -Model C:\models\small-int8.tflite
```

Con herramientas fuera del PATH se pueden indicar `-PicoSdkPath`, `-TflmInclude` y `-TflmLibrary`. La compilación produce `build-pico2-w/picoKeras.uf2` si CMake y enlace terminan satisfactoriamente. Usá `-Clean` para descartar cachés anteriores. Este parche **no incluye UF2 precompilado**.

TFLM incluye dependencias como FlatBuffers y CMSIS; deben estar accesibles en el checkout local y son preparadas por los mecanismos de build de TFLM. Si `make` no está instalado, se exige una biblioteca ARM `.a` compatible en `-TflmLibrary`. No deben utilizarse bibliotecas `x64`.

## Restricciones importantes

- **Modelo**: `.tflite` FlatBuffer TFL3 con entrada de 768 elementos (`[1,8,8,12]` o `[1,768]`) y salida escalar; tipos FP32, INT8 o UINT8. Preferir **INT8**. Las redes de tipo Transformer con operadores no soportados no arrancarán sin más trabajo de kernels. El firmware registra un conjunto de operadores TFLM estándar, **no** promete soporte universal de GELU, REDUCE_PROD o capas Keras personalizadas.
- **Arena**: predeterminada 98.304 bytes (`-ArenaBytes` permite 8.192–262.144). El firmware falla explícitamente si `AllocateTensors()` no puede reservar memoria o el modelo usa un operador no registrado.
- **Wi-Fi**: se genera `build-pico2-w/generated/pico_build_config.h`, con credenciales si se suministran; no lo incluyas en Git ni en ZIP públicos. Sin SSID el motor sigue disponible por USB-CDC.
- **UCI**: comandos básicos `uci`, `isready`, `ucinewgame`, `position`, `go`; `stop` y gestión asíncrona de búsqueda no están implementados (búsqueda sin límite temporal a 1 ply). El control de sesiones TCP es de una conexión a la vez. No cargar en una Pico W RP2040.
- **Validación**: los fuentes y el generador de código se han verificado estáticamente, pero **no se ha podido compilar con el SDK local ni probar la placa desde este entorno**. Una compilación exitosa y una prueba de inferencia con el modelo real son pasos pendientes. No interpretar este parche como firmware ya validado.

## Pruebas mínimas recomendadas

1. Construir y comprobar que `picoKeras.uf2` existe y es para `pico2_w`.
2. Cargarlo con BOOTSEL en Pico 2 W y abrir USB-CDC; verificar `MODEL ready` (no basta `BOOT`).
3. Enviar `uci`, `isready`, `position startpos`, `go` y comprobar que responda un movimiento UCI legal.
4. Si hay Wi-Fi, conectarse por TCP 6110 y repetir la prueba.
5. Comparar salida de evaluación y movimiento con `picoKeras/X86` sobre un conjunto fijo de posiciones, aceptando diferencias de cuantización.

La guía oficial de TFLM para integración de plataformas recomienda generar una biblioteca estática de kernels de referencia y usar los SDK específicos del microcontrolador: https://github.com/tensorflow/tflite-micro .
