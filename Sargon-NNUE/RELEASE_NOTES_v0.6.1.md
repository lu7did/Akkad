# Sargon-NNUE v0.6.1

## Cambio principal

Se incorpora soporte nativo para **Cerebrum 1.1** con su arquitectura default oficial:

`2x(768 -> 128) -> 32 -> 2`

El nuevo evaluator `CEREBRUM-1.1` acepta directamente los archivos producidos por el entrenamiento oficial:

- `epoch-XX.txt`: red estándar/full precision.
- `epoch-XX-q.txt`: red cuantizada.

No requiere conversión a `.nn`.

## Semántica de evaluación

Cerebrum 1.1 produce dos salidas, `wr` y `mt`. El evaluator lee de la cabecera del archivo los factores `wr=` y `mt=` y reproduce la fórmula oficial:

`evaluation = wr * wr_factor + mt * mt_factor`

El valor es escalado de la misma forma que el engine de demostración oficial (`int(1000 * evaluation)`) y luego normalizado a la perspectiva de blancas requerida por Sargon-NNUE.

## Compatibilidad

- `cerebrum-1.1`: nuevo evaluator.
- `cerebrum-2`: evaluator V2.0 existente.
- `cerebrum`: se conserva como alias de V2.0 para no romper scripts v0.6.0.
- `classic` y `npz`: sin cambios.

Las redes Cerebrum 1.1 con arquitectura distinta del default son rechazadas explícitamente en v0.6.1 para evitar interpretar pesos con un layout incorrecto.
