# picoKeras ARM v0.1.24 — GNU Make / MSYS2

Base de modificaciones: `akkad(10).zip` más parche ARM de compilación v0.1.22.
El parche v0.1.23 proporciona el modelo en `assets/model.tflite` y no se altera.

- Busca MSYS2 en rutas habituales y en `MSYS2_ROOT`.
- Si no existe, intenta instalar `MSYS2.MSYS2` con winget (requiere Internet).
- Instala `make` con `pacman` si falta.
- Emplea el shell POSIX de MSYS2, indispensable para scripts de TFLM.
- No instala ni sustituye una biblioteca de Windows como biblioteca ARM.
- Respeta `-NoDownload`.

Aplicar el ZIP desde la raíz de Akkad y ejecutar `picoKeras/ARM/build.ps1`.

**Sin compilación cruzada o verificación física:** no se garantiza que la construcción TFLM o el modelo complejo sean compatibles con RP2350. Si falla la siguiente etapa, conservar el error concreto.
