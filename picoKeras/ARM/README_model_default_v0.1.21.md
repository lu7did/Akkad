# picoKeras ARM v0.1.21 — selección de modelo predeterminado

Este parche incremental se aplica en la raíz de Akkad, **después** del parche
`Akkad_picoKeras_ARM_RP2350_v0.1.20_incremental.zip`, del que parte.
La única línea de base de fuentes es `akkad(10).zip`.

## Uso

- `./build.ps1` usa `picoKeras/ARM/assets/model.tflite` cuando existe.
- Si ese archivo no existe pero hay exactamente un `.tflite` directamente en `assets`, lo elige.
- Si hay varios modelos y ninguno se llama `model.tflite`, detiene la compilación y pide `-Model`.
- Si no existe ningún modelo, detiene la compilación con una explicación.
- `./build.ps1 -Model "C:\modelos\red.tflite"` conserva la selección explícita.
- `./build.ps1 -Help` muestra la ayuda.

El proyecto original **no incluye** un modelo bajo `picoKeras/ARM/assets`.
Este parche no agrega modelos ni modifica X86, Debian ni el código de inferencia.
La extensión `.tflite` no prueba que el modelo sea INT8 ni que sus operadores sean compatibles con TFLM; ambas condiciones deberán comprobarse por separado.

Versión de build script: 0.1.21; versión funcional de firmware sin cambios.
