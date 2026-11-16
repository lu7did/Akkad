# picoGenus – Progress telemetry v0.1.11

Esta corrección modifica solamente la representación visual de las barras en `gen_progress.py`:

- Antes: `#` (completado), `-` (pendiente).
- Ahora: `█` (completado), `░` (pendiente).

Se preservan los cálculos de porcentaje, posición, generación, individuo, ETA, ajuste al ancho de la consola y retorno de carro (`\r`), así como el único salto de línea al finalizar. No modifica algoritmos ni `run_genesis.ps1`.

El archivo Python se guarda en UTF-8. Para que Windows PowerShell represente los caracteres, ejecutar en una terminal con soporte Unicode. Si se observan símbolos incorrectos, configurar `$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()` antes de ejecutar Genesis.
