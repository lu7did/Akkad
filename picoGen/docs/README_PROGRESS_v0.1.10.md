# picoGenus v0.1.10 — Telemetría de entrenamiento

Parche incremental relativo a la raíz `akkad/`. Cambia exclusivamente la visualización del progreso de `genPST.py` y `genNNUE.py`, más el módulo `gen_progress.py`.

## Convenciones

Se distingue entre **posiciones** (filas FEN del conjunto de entrenamiento) y **partidas** (grupos `game_id` de origen). Los entrenadores consumen posiciones, no partidas completas. Por tanto el contador dice `pos`, no `games`.

La proporción de progreso durante entrenamiento se calcula sobre **operaciones de evaluación de individuos contra posiciones**:

`total_trabajo = generaciones * población * posiciones`

`completado = generaciones_terminadas * población * posiciones + individuos_terminados_en_generación * posiciones + posiciones_terminadas_del_individuo_actual`

La barra presenta porcentaje global, posiciones procesadas por el individuo actual, generación, individuo y ETA estimado a partir del promedio de trabajo completado. En el preprocesamiento se muestra otra barra con progreso por fila de entrada. La ETA es una estimación, no una predicción garantizada; las generaciones pueden tener costes diferentes.

Ejemplo ilustrativo en terminal suficientemente ancha:

`PST trai [#####-------]  42.31% pos=  300/ 1000 g=212/ 500 i= 31/100 ETA=01:34:20`

La barra se actualiza con `\r`, sin secuencias ANSI de borrado, y se limita al ancho detectado de la consola dejando dos columnas libres para evitar el ajuste automático de PowerShell. Los números mantienen ancho fijo. En pantallas estrechas, se ocultan las columnas menos esenciales para mantener la línea única. La escritura se limita a una actualización cada 250 ms, pero los contadores avanzan con el trabajo efectivo. En salida redirigida solo se escribe el estado final.

## Alcance y compatibilidad

El algoritmo PST mantiene el fitness `aciertos**2`, codificación Gray, ruleta, cruce, mutación y elitismo de la versión de referencia v0.1.3. La NNUE conserva su función MSE, dimensiones, operadores y tipo de datos. No cambian los formatos de salida JSON/NPY ni los parámetros CLI, ni `run_genesis.ps1`.

El presente parche no completa los términos PST pendientes de especificación respecto al artículo. No introduce cambios metodológicos.

## Pruebas

Incluye pruebas de presentación en terminales simuladas de 80 y 60 columnas, ausencia de líneas múltiples en TTY, comportamiento redirigido y mini-entrenamiento NNUE. La prueba genética PST requiere `python-chess`; en un entorno sin esa dependencia se marca como omitida.
