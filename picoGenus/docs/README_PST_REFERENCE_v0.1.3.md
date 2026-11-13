# picoGenus PST v0.1.3 — restauración de la referencia

## Alcance

Corrección de `gen_pst_core.py`, `genPST.py` y prueba de regresión. El evaluador
`nurse.genus_eval.GenusEvaluator` ya llama al núcleo compartido `gen_pst_core.evaluate`,
por lo que adopta automáticamente la semántica corregida. No se alteró NNUE.

## Compromisos de fidelidad

- `evaluar_posicion_david`, `elegir_jugada_1ply`, `gray_a_binario` y
  `decodificar_cromosoma` se copiaron literalmente del archivo adjunto
  `entrenar_david_ga.py`.
- El fitness vuelve a ser exactamente `aciertos ** 2`. Acierto equivale a
  coincidencia exacta con `teacher_uci` tras búsqueda 1-ply.
- Se mantienen inicialización uniforme, ruleta, elitismo de 1, cruce uniforme
  0.75, mutación de bits 0.005 tal como indica el ejemplo.
- Las únicas adaptaciones son CLI, SQLite `.pb`, validación de FEN/movimientos,
  telemetría periódica, control de semilla y serialización JSON.
- `error_min` y `error_mean` miden **jugadas incorrectas**, no error en
  centipeones: esto evita añadir una función objetivo distinta.

## Ambigüedades detectadas, sin completar silenciosamente

El ejemplo declara 34 genes (35 parámetros incluido peón) pero su función
`evaluar_posicion_david()` no utiliza todos los genes. No se añadieron reglas
faltantes ni aproximaciones. Las variables no utilizadas **no tienen presión
selectiva** y sus valores evolucionados no aportan información causal.

La fidelidad aquí es con **el programa de ejemplo suministrado**, no supone
que este represente íntegramente la función publicada en el artículo.

## Advertencia para modelos existentes

Los archivos `genus_pst.json` generados con v0.1.1 reflejan otra función
objetivo y otra heurística; **deben reentrenarse**. El contrato JSON permanece
`picogenus-pst-v1` por compatibilidad estructural, pero se incluye
`reference=entrenar_david_ga.py` para identificar el origen de nuevos modelos.

## Comando

```powershell
python genPST.py --in "C:\Data\genus.pb" --out "..\..\assets\genus_pst.json" --poblacion 100 --generaciones 500
```
