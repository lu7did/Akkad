# AlphaZero v0.2.16 — build and launcher identity verification

## Defecto reproducido

El build de Windows genera `AlphaZero.exe` correctamente, pero `tools/ps/build.ps1` contiene la validación fija `AlphaZero v0.2.12 build=`. Al compilar v0.2.15, el ejecutable responde `AlphaZero v0.2.15 build=...` y el script aborta con `AlphaZero build identity mismatch`.

## Corrección

- `AlphaZero/src/config.h` pasa a v0.2.16.
- `tools/ps/build.ps1` lee `kVersion` del mismo `config.h` usado por la compilación, y verifica exactamente `AlphaZero <versión> build=`. No se elimina la comprobación de identidad.
- `tools/ps/run_listen.ps1`, `tools/bash/run_listen.sh` y `tools/macOS/run_listen.sh` verifican la identidad frente a la versión del código fuente. Se eliminan los límites fijos v0.2.12.

No altera MCTS ni `go searchmoves`. Requiere aplicar primero AlphaZero v0.2.15.

## Pruebas

Verificación estática de sustituciones, `bash -n` en ambos lanzadores, y comprobaciones de lectura de versión. Prueba nativa PowerShell y compilación MSVC pendientes en el entorno del usuario.
