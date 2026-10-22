# Parche incremental v0.6.189 — segunda fuente LC0 y arquitectura compacta experimental

## Compatibilidad
- `sargon_prepare --update lc0-secondary --lc0-secondary-weights <red.pb.gz>` añade WDL, `network_id` e historial independientes de LC0 existente y LC0 UCI. Usa bindings, nunca `lc0.exe`.
- Una segunda red sustituye las etiquetas secundarias sólo si se utiliza otra `.pb`: se rechaza mezcla de identidades de red en el mismo dataset.
- `sargon_train --weight-lc0-secondary` añade la sexta ponderación (0..1, suma total 1). La orientación WDL es blanca y expectativa `w + d/2`.
- `--architecture npz` sigue siendo predeterminado; `--architecture grumpy-small` entrena dos perspectivas de ocho canales y produce `grumpy_small_best.npz`, un **checkpoint de investigación** distinto de NNUE y del binario `GRMP0001`.

## Limitaciones importantes
El formato Grumpy usado actualmente por picoSargon (`GRMP0001`) contiene una representación muy específica de características y pesos cuantizados. La arquitectura `grumpy-small` incorporada es compacta y distinta de 781-64-1, pero **aún no genera un `grumpy.bin` compatible**. Faltan el ajuste topológico exacto, la conversión/compresión y la paridad con el evaluador firmware; no instalar el .npz experimental en la Pico.

Tampoco se agrega todavía una etiqueta del evaluador Grumpy existente (GRMP0001): esta entrega incorpora exclusivamente la segunda red LC0 bindings pedida en el paso de preparación.

## Validaciones
Sintaxis Python comprobada. No se pudo ejecutar entrenamiento completo ni LC0 bindings en el contenedor debido a que no está disponible `python-chess` ni el runtime LC0. Los scripts PowerShell sirven como ejemplos y requieren ajustar las rutas locales.

No se modifican los algoritmos de evaluación existentes, ficheros de datos ni proyectos Raspberry.
