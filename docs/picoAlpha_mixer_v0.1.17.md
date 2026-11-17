# picoAlpha — Mixer de bases etiquetadas (v0.1.17)

## Objetivo

`picoAlpha/tools/train/mixer.py` crea una base SQLite `.pb` de salida con **todas las partidas y posiciones de `--in`**. Si una FEN exacta tiene una etiqueta Stockfish completa en `--mix`, copia exclusivamente los seis campos `teacher_*` de `--mix`; si no, escribe los seis campos `teacher_*` como `NULL`, incluso si `--in` tenía etiquetas anteriores.

La procedencia, encabezados, IDs, FEN, jugada jugada (`played_uci`) y orden de posiciones siempre se conservan desde `--in`. No se agregan partidas que solo existan en `--mix` y no se invoca Stockfish.

### Condiciones de coincidencia

* Identidad de posición: cadena **FEN idéntica**, sin normalización de relojes/castling/EP. Dos FEN con mismos trebejos y diferencias de contadores se consideran diferentes.
* Etiqueta reutilizable: `teacher_at IS NOT NULL AND teacher_value IS NOT NULL`. `teacher_cp` puede ser nulo en mates.
* Duplicados en `--mix`: seleccionar mayor `teacher_depth` y, en igualdad, mayor `positions.id`. No se mezclan evaluaciones ni se promedian.
* Input/etiquetas de salida no se modifican in situ. `--out` debe ser inexistente y diferente de ambas entradas.

## Uso

```powershell
cd C:\Users\pedro\github\bobby\akkad\picoAlpha\tools\train
python .\mixer.py --in "C:\ruta\original.pb" --mix "C:\ruta\etiquetadas.pb" --out "C:\ruta\mixed.pb"
# O wrapper con valores editables
.\run_mixer.ps1 --in "C:\ruta\original.pb" --mix "C:\ruta\etiquetadas.pb" --out "C:\ruta\mixed.pb"
```

Opcional: `--batch 10000`. `--help` disponible en ambos.

**Siguiente paso imprescindible**:

```powershell
python .\teacher.py --in "C:\ruta\mixed.pb" --engine "C:\ruta\stockfish.exe" --depth 10 --resume
```

`--resume` evita volver a analizar las FEN ya etiquetadas. Sin este parámetro, `teacher.py` vuelve a procesar todas las filas.

## Telemetría

* Cabecera de tres rutas y sus tamaños.
* Barra `INDEX MIX`: filas escaneadas, pendientes, tasa y ETA; índice temporal por FEN y duplicados.
* Barra `PARTIDAS`: partidas importadas y pendientes.
* Barra `MEZCLA`: posiciones copiadas, etiquetas reutilizadas, pendientes del teacher, tasa y ETA.
* Verificación `PRAGMA integrity_check` y `foreign_key_check`; resumen final y duración.
* Terminal interactiva: una línea actualizada mediante retorno de carro. Archivo o tubería: instantáneas espaciadas evitando millones de renglones.

## Limitaciones y precauciones

1. El índice temporal por FEN consume espacio en disco, especialmente con bases de millones de posiciones.
2. Un FEN puede figurar varias veces en la base de mezcla y tener etiquetas incompatibles (distintas versiones/profundidades de Stockfish). La política de desempate es determinista pero no certifica equivalencia de etiquetas. Conviene mantener la misma versión/configuración de teacher.
3. La exactitud textual del FEN impide reutilizar algunas posiciones equivalentes con distintos contadores. Es deliberado para evitar una equivalencia dudosa durante la primera versión.
4. La generación se realiza en `nombre.pb.mixer.tmp` y se publica mediante reemplazo atómico únicamente tras completar integridad. No se sobrescriben bases existentes.
5. El archivo .pb es SQLite y no protobuf.

## Pruebas

`python -m unittest discover -s picoAlpha/tools/train/tests -p test_mixer.py -v`

Prueban reutilización, duplicados, limpieza de no coincidentes, integridad, conservación de partidas y rechazo de sobrescritura.
