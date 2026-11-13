# picoAlpha Training v0.1.7 — corrección de barras en PowerShell

**Defecto:** `common.py` reservaba 55 caracteres de relleno para `tail` aun cuando el parámetro era vacío. La línea producida por `teacher.py` tenía más de 100 columnas y provocaba *wrap* en terminales de 80 columnas, mostrando una barra por renglón aunque se emitiera `\r`.

**Corrección:** `progress()` calcula el ancho disponible del terminal con `shutil.get_terminal_size()`, deja siempre una columna libre para evitar el auto-wrap de Windows, ajusta el ancho de la barra y no reserva columnas para un `tail` vacío. Se mantiene el retorno de carro y el salto de línea sólo al concluir el paso. Los logs redirigidos sólo reciben el estado final. Afecta a los clientes de la función común, entre ellos `teacher.py`, `sampler.py` y `train.py`. `loader.py` conserva su presentación específica de dos líneas.

**Pruebas:** `python -m unittest discover -s picoAlpha/tools/train/tests -p test_progress_no_wrap.py -v`. No se alteró el algoritmo de enseñanza ni la base de datos.

**Aplicación:** descomprimir en raíz de Akkad sobre v0.1.6. No es necesario repetir los pasos de Genesis completados. Reanudar con `run_genesis.ps1 -Mon 3` si la enseñanza debe iniciarse de nuevo.
