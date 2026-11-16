# picoAlpha C++ MCTSP + MCTSE — Windows X86 v0.1.41

## Cambios respecto de v0.1.40

- `picoAlpha/tools/train/export.py` genera **tres artefactos desde una única cuantización INT8**: cabecera `.h`/`.hpp`, checkpoint PyTorch INT8 `.pt` y modelo portable `.bin` para C++. Por defecto `.bin` comparte el nombre base de `--int8`; `--bin` permite elegir otro destino. No modifica arquitectura, pesos, escalas ni contrato de entrenamiento.
- El tablero conserva el **mailbox 10×12** (120 celdas, borde centinela) y ahora **Move.from y Move.to también son índices mailbox**. La representación 0–63 se utiliza únicamente al convertir FEN/UCI y las entradas de la NNUE; no es el formato interno de los movimientos. `Board::parse()` y `Board::notation()` son las fronteras UCI.
- Se conservan `--network`, `--depth`, `--timeout`, `--sim`, el protocolo UCI `stdout` y la telemetría `stderr`.

## Exportación INT8 automática

Desde `akkad/picoAlpha`:

```powershell
python .\tools\train\export.py --in .\assets\checkpoints\best.pt --out .\assets\picoalpha_nnue.hpp --int8 .\assets\picoalpha_int8.pt
```

Produce simultáneamente:

- `assets/picoalpha_nnue.hpp`
- `assets/picoalpha_int8.pt`
- `assets/picoalpha_int8.bin`

Opcionalmente `--bin .\assets\otro_nombre.bin` permite indicar un destino explícito.

El formato es idéntico al del conversor de v0.1.40: `PANNI8\r\n` (8 bytes), tres `uint32` little-endian (versión 1, 780 features, 16 hidden), cuatro escalas IEEE 754 float32 little-endian, y matrices INT8 `W_INPUT`, `W_VALUE`, `W_FROM`, `W_TO` en orden row-major. Tamaño fijo **14.580 bytes** = cabecera 36 + 14.544 pesos.

El conversor antiguo `tools/ps/convert_int8.py` permanece como herramienta de compatibilidad y control; ya no es parte obligatoria del pipeline.

## Construcción Windows y ejecución

```powershell
.\tools\ps\build.ps1
.\X86\build\picoAlpha.exe --network .\assets\picoalpha_int8.bin --depth 12 --timeout 15000 --sim 200
```

En Nurse declarar un motor de **tipo `uci`**, con ejecutable `picoAlpha.exe` y argumento `--network` apuntando al archivo `.bin`. Se mantiene el ejemplo en `picoAlpha/etc/brains_uci_example.json`.

## Límites de esta actualización

- No cambia el algoritmo MCTSP/PUCT ni el convenio de valor STM de MCTSE.
- El formato binario `v1` sigue siendo obligatorio para este motor: **no** lee `.pt` directamente durante la ejecución.
- La representación mailbox implica 120 celdas; las matrices NNUE siguen necesitando índices 0–63 y la conversión se hace explícitamente en `nnue.cpp`.
- No se ha comprobado compilación MSVC nativa en esta sesión; las pruebas de compilación se ejecutan con GCC C++17.
