# Sargon-NNUE v0.6.153 — encabezados Python

Parche incremental para aplicar sobre v0.6.152.

Se incluyen 121 archivos fuente `.py` del proyecto, incluidos `src`, `scripts`, scripts historicos y `tests` (los existentes en la linea de base adjunta y los incorporados por los parches v0.6.144–v0.6.152).

A cada archivo se agrego el encabezado textual solicitado, con nombre, descripcion individual y `v0.6.153`. Se conserva shebang / declaracion de codificacion donde corresponde. Unico cambio no comentado: `__version__` del paquete pasa a `0.6.153`.

Se verifico compilacion sintactica de los nuevos archivos con Python de escritorio, sin ejecutar pruebas de integracion. No se modificaron `.ps1`, archivos binarios ni datos.

Aplicar el ZIP preservando rutas sobre el proyecto v0.6.152.
