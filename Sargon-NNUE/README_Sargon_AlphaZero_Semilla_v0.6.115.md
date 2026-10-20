# Sargon-NNUE — AlphaZero semilla v0.6.115

## Finalidad y alcance

Parche **experimental y aditivo** para la primera red de política y valor `f(P,V)` a partir de una base `.pb` histórica (SQLite). **No se modifica** ningún archivo del motor o los programas originales `sargon_prepare.py`, `sargon_train.py`, `pb_data.py`, `torch_train.py` ni sus evaluadores. Cada script realiza una sola operación; no hay un orquestador PowerShell.

Se parte de un `.pb` existente con, por ejemplo, más de 14.000 partidas. Los etiquetados `stockfish`, `classic` (Sargon clásico) y `result` son **exactamente los preexistentes**. El etiquetado Sargon clásico lo calcula su propio evaluador (`--update classic`). Se incluye por separado un etiquetado **opcional** `sargon-nnue` si se dispone de un checkpoint `.npz`; **no** sustituye al clásico.

**Contrato de la muestra:** primero se selecciona una proporción configurable de *partidas completas*. Después se reserva un porcentaje de esas partidas para validación. De las **transiciones históricas elegibles pertenecientes solo a las partidas de entrenamiento**, se selecciona una única muestra aleatoria exacta de movimientos, por defecto el 20 %. Los **mismos movimientos seleccionados** aportan `V` desde los campos de `positions` y aportan `P` mediante conteos agrupados por estado y acción. La política no usa ni pondera evaluaciones de Stockfish. La validación se calcula con sus propias partidas, sin participación en ningún gradiente ni conteo de entrenamiento.

## Instalación

1. Descomprimir el ZIP en la **raíz del repositorio Sargon-NNUE**: se agregan/reemplazan únicamente archivos experimentales (`az_*`) y scripts nuevos (`sargon_az_*`).
2. Usar el entorno Python `ufasta`, que debe contener PyTorch, NumPy y `python-chess`, además de las dependencias existentes de Sargon.
3. Ejecutar los comandos siguientes individualmente **desde la raíz del proyecto**. Ajustar las rutas según la instalación. Los archivos `.pb` intermedios son copias nuevas: no sobrescriben la base de origen.

## Scripts individuales: ejecución en orden

**0 — Copia de trabajo de la base completa:**

```powershell
.\scripts\sargon_az_00_copiar_pb.ps1 --input "data\historical_14000.pb" --out "data\az\historical_work.pb"
```

**1 — Etiquetado Stockfish** (si ya existen etiquetas válidas, este paso puede omitirse):

```powershell
.\scripts\sargon_az_01_valor_stockfish.ps1 --input "data\az\historical_work.pb" --stockfish-path "C:\ruta\stockfish.exe" --stockfish-depth 12 --stockfish-threads 1
```

**2 — Etiquetado Sargon clásico** usando el evaluador heredado sin modificaciones:

```powershell
.\scripts\sargon_az_02_valor_sargon_clasico.ps1 --input "data\az\historical_work.pb"
```

**2b — Opcional y diferente: etiquetado Sargon-NNUE con checkpoint `.npz`**. Solo si se desea agregar este maestro experimental:

```powershell
.\scripts\sargon_az_02b_valor_sargon_nnue.ps1 --input "data\az\historical_work.pb" --network "data\red_sargon.npz"
```

`az_nnue_cp` se agrega solo a la *copia experimental*; `classic_cp` y los programas históricos quedan intactos. **No es necesario usar este paso para la ruta básica.**

**3 — Resultado de partida suavizado:**

```powershell
.\scripts\sargon_az_03_valor_resultado_suavizado.ps1 --input "data\az\historical_work.pb" --result-smoothing 0.15
```

**4 — Muestreo de partidas completas:**

```powershell
.\scripts\sargon_az_04_muestrear_partidas.ps1 --input "data\az\historical_work.pb" --out "data\az\historical_games.pb" --games-pct 100 --seed 42
```

Modifique `--games-pct`, por ejemplo a `30` para conservar 30 % de las partidas originales. Con `100` se conservan todas. La fuente de 14.000 partidas y la copia etiquetada no se modifican.

**5 — División train/validación y construcción de políticas históricas:**

```powershell
.\scripts\sargon_az_05_construir_politicas.ps1 --input "data\az\historical_games.pb" --out "data\az\historical_policy.pb" --validation 10 --seed 42
```

El programa reserva **partidas completas** antes de agregar frecuencias y crea exclusivamente tablas experimentales: `az_policy_games`, `az_policy_positions`, `az_policy_moves` y `az_policy_observations`. Esta última almacena cada transición con su jugada elegida, para permitir el muestreo consistente posterior.

**6 — Muestreo exacto de movimientos (20 % por defecto):**

```powershell
.\scripts\sargon_az_06_muestrear_movimientos.ps1 --input "data\az\historical_policy.pb" --out "data\az\historical_20pct.pb" --moves-pct 20 --seed 42
```

El script toma una única selección uniforme de las transiciones *solo de entrenamiento* y la almacena como `az_training_moves` con `position_id`, `policy_position_id` y `action`. La distribución de política que verá el entrenador se **recalcula a partir de los movimientos efectivamente seleccionados**, no de todas las apariciones del corpus. Cada registro elegido provee a la vez el objetivo `V` desde `positions` y una observación de la acción para `P`. Las alternativas legales no observadas conservan frecuencia cero. El 10 % de partidas reservadas se usa íntegramente para métricas de validación (sujeto a los límites configurados).

**7 — Entrenamiento inicial aislado:**

```powershell
.\scripts\sargon_az_07_entrenar_semilla.ps1 --input "data\az\historical_20pct.pb" --outdir "data\az\seed_actual" --weight-stockfish 1 --weight-classic 0 --weight-result 0 --weight-nnue 0 --validation 10 --sample-pct 100 --epochs 10 --batch-size 64 --device xpu --max-samples 500000 --max-policy-samples 500000 --max-validation 250000 --seed 42
```

Cambiar mezcla de `V`, por ejemplo `--weight-stockfish 0.7 --weight-classic 0.3 --weight-result 0` (los pesos deben sumar uno); para usar el resultado suavizado, pasar `--weight-result` y **además** `--result-smoothed`. Para el maestro NNUE opcional, asignar `--weight-nnue` después de ejecutar 2b. **Ninguna de estas opciones influye en el conteo de P.**

La opción `--sample-pct` se deja explícitamente en **100** en el paso de entrenamiento, porque la muestra exacta del **20 % ya fue realizada** en el paso 6. El entrenador rechaza aplicar dos muestreos sobre esa misma base.

### Repetir el entrenamiento desde cero sobrescribiendo la red experimental

Repetir el **paso 7** con las mismas rutas y agregar `--replace` al final. El sistema entrena en un directorio temporal; **solo si termina satisfactoriamente y genera checkpoints válidos** reemplaza `data\az\seed_actual`. Si falla, preserva la red previa. Este es un **nuevo entrenamiento desde pesos aleatorios**, no continuación de los pesos previos (eso corresponderá a la modalidad posterior `refine`). El `.pb` no se borra ni se modifica en la repetición.

Los archivos `az_epoch_###.pt`, `az_best.pt`, `az_metrics.csv` y `az_config.json` se producen en el directorio de salida. Las métricas independientes son MSE de valor, entropía cruzada de política y top-1 de política, además de pérdida conjunta de validación.

## Criterio de validación

Con 14.000 partidas, 100 % de muestreo de partidas y 10 % de validación: se reservan aproximadamente 1.400 partidas completas de validación y quedan 12.600 para entrenamiento. En una base que tuviese, por ejemplo, 600.000 transiciones elegibles de entrenamiento, `--moves-pct 20` seleccionaría exactamente 120.000 transiciones. Esas 120.000 observaciones se usan **tanto para V como para P**, aunque P se consolida por posición y puede tener menos filas finales. La validación utiliza solo los registros de las 1.400 partidas reservadas; nunca hay transferencia de sus conteos a la política de entrenamiento.

Una posición idéntica podría aparecer legítimamente tanto en la partición de entrenamiento como en la de validación (por ejemplo, una apertura habitual); sus observaciones se mantienen estrictamente separadas. Se registra el número de posiciones compartidas a efectos de interpretación.

## Protecciones y limitaciones

- La base fuente y los archivos históricos de código no se modifican.
- Los pasos de copia/muestreo `.pb` crean destinos nuevos y rechazan sobrescribir bases existentes.
- Los pasos heredados de etiquetado actualizan **solo la copia de trabajo**, como ya implementaba Sargon-NNUE.
- Los datos históricos guardan posiciones después de cada movimiento; no es posible reconstruir las jugadas posteriores a la última posición almacenada sin una transición siguiente. Solo se cuentan **transiciones comprobables** (típicamente `npositions - 1` por partida), no se inventan acciones.
- La validación por MSE mide reproducción de las etiquetas escogidas, no fuerza ajedrecística; top-1 mide coincidencia con acciones históricas, no mejor jugada objetiva.
- Las políticas provienen de frecuencias históricas, **no** de visitas MCTS. MCTS reemplazará esa fuente durante el refinamiento posterior.
- Este entorno de preparación del parche dispone de PyTorch pero no de `python-chess`; se verificó sintaxis y pruebas de integración SQLite con datos sintéticos. Debe realizarse una prueba de punta a punta en `ufasta` con un `.pb` real antes de un entrenamiento prolongado.
- La colección de scripts no lanza procesos en segundo plano ni encadena etapas. Cada acción debe invocarse explícitamente.

## Pruebas sugeridas

```powershell
& 'C:\Users\pedro\ufasta\Scripts\python.exe' -m pytest -q tests\test_az_workflow_v06115.py
```

Y antes del entrenamiento completo, hacer un piloto con `--games-pct 1`, `--moves-pct 20`, `--epochs 2`, `--device cpu`, conservando una muestra de validación de al menos varias partidas.
