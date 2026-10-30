picoKeras v0.1.40 - correccion inmediata de script PowerShell

Parche incremental sobre v0.1.39; no sustituye ninguna otra version previa.

Corrige el uso de $home, que PowerShell trata como $HOME (variable automatica de solo lectura).
Las tres apariciones se reemplazan por $tflmSourceRoot.
Mantiene verificaciones y reconstruccion TFLM/picoKeras del script v0.1.39.

Aplicar en raiz Akkad y ejecutar desde x86/picoKeras:
  ..\..\scripts\unblock.ps1 .\scripts\rebuild_tflm_and_try.ps1
  .\scripts\rebuild_tflm_and_try.ps1 -Network .\small.mul.int8.tflite

VALIDACION: analisis textual de las 3 sustituciones, secuencia de compilacion y ZIP.
NO VALIDADO: ejecucion PowerShell/compilacion MSVC en Windows.
