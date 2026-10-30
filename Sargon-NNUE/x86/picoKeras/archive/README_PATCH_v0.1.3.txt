picoKeras v0.1.3 - Hotfix de codificacion PowerShell

Extraer en Akkad/. Sobrescribe:
- sargon-NNUE/x86/picoKeras/build.ps1
- sargon-NNUE/x86/picoKeras/scripts/install_TFLM.ps1

Se eliminaron los caracteres Unicode de los mensajes PowerShell.
Estos scripts usan exclusivamente ASCII para ser compatibles con Windows PowerShell 5.1 independientemente de la pagina de codigos.

Ejecutar: .\build.ps1

La compilacion real de TFLM sobre Visual Studio permanece sin validar en este entorno.
