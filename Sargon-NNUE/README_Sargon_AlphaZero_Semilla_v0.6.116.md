# Sargon-NNUE / AlphaZero — preparación y entrenamiento de semilla v0.6.116

## Qué cambió respecto de v0.6.115

El orden **obligatorio** es ahora: **(0) reservar partidas de validación de la base original**, **(1) muestrear partidas completas SOLO del remanente**, **(2–4) etiquetar SOLO esas partidas de entrenamiento**, **(5) reunificar con la validación reservada conservando su origen**, **(6) construir políticas históricas separadas**, **(7) seleccionar una proporción de movimientos de entrenamiento**, **(8) entrenar**. No hay orquestador y **cada script PowerShell recibe únicamente sus propios argumentos**.

- La base `.pb` original y los programas históricos `sargon_prepare.py`, `sargon_train.py`, `pb_data.py`, `torch_train.py` y evaluadores originales **no se cambian**.
- **P** se calcula exclusivamente como frecuencia de la jugada elegida desde cada estado: `C(s,a)/sum_a C(s,a)`. No está ponderada por Stockfish ni Sargon. Se registran también las jugadas legales con frecuencia cero.
- **V** se obtiene de los campos históricos `positions` y `games`: Stockfish (`stockfish_value` o WDL Stockfish), Sargon clásico (`classic_cp`) y resultado (`result_value` suavizado si se solicita, o resultado final). No se duplican etiquetas de V en las tablas AZ.
- El **20 %** se aplica UNA sola vez sobre el conjunto de **transiciones elegibles** de entrenamiento. Cada transición elegida aporta a P y V. La validación usa todas las transiciones recuperables de las partidas reservadas, sin volver a muestrearlas.
- Cada ejecución nueva del entrenador parte de pesos aleatorios (semilla inicial, no refino). Para conservar variantes, use un `--outdir` diferente; para reemplazar el **mismo** modelo experimental tras un entrenamiento completo y correcto, use `--replace`.
- Se guarda `az_epoch_001.pt`, `az_epoch_002.pt`, etc. y `az_best.pt`, elegido por pérdida conjunta de validación, junto con `az_metrics.csv` y `az_config.json`. El número efectivo de epochs puede reducirse solo si se activa `--early-stop`.

## Requisito de etiquetas en validación

**Importante:** las partidas de validación se separan ANTES de los nuevos etiquetados de entrenamiento. Por ello, la base original debe contener ya las etiquetas de valor de la(s) fuente(s) elegida(s) en esas partidas, *o se deben etiquetar expresamente en el archivo `validation.pb` sin usarlo para entrenar*. Esto **no representa fuga de información**: el evaluador solamente construye la referencia de validación, no se utiliza ningún gradiente ni estadística de esa partición al ajustar pesos.

Si se pide `--weight-classic 1`, deben existir las etiquetas `classic_cp` en validación; si se pide Stockfish, `stockfish_value` o WDL Stockfish; si se pide `--weight-result 1 --result-smoothed`, `result_value` debe estar poblado también en validación. Si falta, el entrenador falla explícitamente en lugar de presentar un MSE engañoso.

Los scripts de etiquetado `02`, `03` y `04` pueden ejecutarse también de forma **independiente** con `--input data\az\validation.pb` para generar las etiquetas de validación faltantes; esa base sigue separada y nunca se muestrea para entrenar. Las evaluaciones nuevas de entrenamiento se calculan exclusivamente sobre `training_selected.pb`.

## Instalación

Descomprimir el ZIP en la raíz de Sargon-NNUE (sobre v0.6.115 o sobre la base limpia de Sargon-NNUE). Se sobrescriben **únicamente módulos experimentales `az_*`** y se agregan scripts experimentales `sargon_az_XX_*.ps1`. Se usan `python-chess`, PyTorch y NumPy del entorno `ufasta`. Los comandos se ejecutan desde **la raíz del repositorio**.

No utilizar los scripts numerados antiguos v0.6.115 para esta nueva secuencia; usar exclusivamente los nombres detallados aquí. Los datos intermedios deben utilizar rutas distintas y el programa rechaza sobrescribir bases `.pb` existentes para prevenir errores.

### Paso 0 — Separar validación antes de cualquier otro muestreo

```powershell
.\scripts\sargon_az_00_reservar_validacion.ps1 `
  --input "data\historical_14000.pb" `
  --train-out "data\az\training_pool.pb" `
  --validation-out "data\az\validation.pb" `
  --validation-pct 10 --seed 42
```

Resultados: `training_pool.pb` contiene las partidas no reservadas; `validation.pb` contiene **únicamente** las partidas completas reservadas. Ambos llevan un identificador de procedencia común y preservan sus identificadores originales. **No son porcentajes de movimientos.**

### Paso 1 — Seleccionar partidas completas para entrenamiento

```powershell
.\scripts\sargon_az_01_muestrear_partidas.ps1 `
  --input "data\az\training_pool.pb" `
  --out "data\az\training_selected.pb" `
  --games-pct 30 --seed 43
```

`--games-pct` es **30 % solo a modo de ejemplo**. Se puede poner `100` para utilizar todas las partidas disponibles tras reservar validación. No toca `validation.pb`.

### Paso 2 — Etiquetado Stockfish (opcional según valor elegido)

```powershell
.\scripts\sargon_az_02_valor_stockfish.ps1 `
  --input "data\az\training_selected.pb" `
  --stockfish-path "C:\ruta\stockfish.exe" `
  --stockfish-depth 12 --stockfish-threads 1
```

### Paso 3 — Etiquetado Sargon clásico (opcional según valor elegido)

```powershell
.\scripts\sargon_az_03_valor_sargon_clasico.ps1 `
  --input "data\az\training_selected.pb"
```

Utiliza exactamente el evaluador clásico heredado mediante `sargon_prepare --update classic`. **No es el evaluador NNUE.**

### Paso 4 — Etiquetado por resultado suavizado (opcional según valor elegido)

```powershell
.\scripts\sargon_az_04_valor_resultado_suavizado.ps1 `
  --input "data\az\training_selected.pb" `
  --result-smoothing 0.15
```

Se pueden realizar los tres etiquetados en corridas separadas sobre la MISMA `training_selected.pb`. Cada uno actualiza su campo de valor y no modifica los demás.

### Paso 5 — Reunir las dos particiones en una copia experimental

```powershell
.\scripts\sargon_az_05_reunir_validacion.ps1 `
  --input "data\az\training_selected.pb" `
  --validation-input "data\az\validation.pb" `
  --out "data\az\training_and_validation.pb"
```

Se comprueba que ambas particiones proceden del **mismo** paso 0 y que no comparten identificadores de partida ni posición. Se añade una tabla experimental `az_holdout_games` con la partición explícita. No se mezclan observaciones; las etiquetas originales de `V` siguen en `positions`.

### Paso 6 — Agregar políticas históricas sin tocar V

```powershell
.\scripts\sargon_az_06_construir_politicas.ps1 `
  --input "data\az\training_and_validation.pb" `
  --out "data\az\training_policies.pb"
```

Se respetan las **particiones predefinidas** del paso 0; no se crea otra validación. Se agregan `az_policy_games`, `az_policy_positions`, `az_policy_moves` y `az_policy_observations`. Las acciones se reconstruyen entre posiciones consecutivas, sin inventar la jugada previa a la primera ni una siguiente a la última posición.

### Paso 7 — Elegir una muestra exacta de los movimientos de entrenamiento

```powershell
.\scripts\sargon_az_07_muestrear_movimientos.ps1 `
  --input "data\az\training_policies.pb" `
  --out "data\az\training_20pct.pb" `
  --moves-pct 20 --seed 44
```

La tabla `az_training_moves` recoge la **única muestra común** de transiciones históricas (no de posiciones únicas). La política efectiva se recalcula utilizando exclusivamente las acciones de los movimientos elegidos. La validación se mantiene completa e independiente.

### Paso 8 — Entrenar la primera semilla AlphaZero

```powershell
.\scripts\sargon_az_08_entrenar_semilla.ps1 `
  --input "data\az\training_20pct.pb" `
  --outdir "data\az\semilla_experimento_001" `
  --weight-stockfish 1 --weight-classic 0 --weight-result 0 `
  --sample-pct 100 `
  --epochs 20 --batch-size 64 --device xpu `
  --max-samples 500000 --max-policy-samples 500000 --max-validation 250000 `
  --seed 45
```

**Nota:** `--sample-pct 100` es correcto porque ya se seleccionó exactamente el 20 % de movimientos en el paso 7; intentar realizar otro muestreo se rechaza. La selección de valor es libre: para mezclar, usar por ejemplo `--weight-stockfish 0.7 --weight-classic 0.3 --weight-result 0`. Para resultado suavizado añadir `--result-smoothed` y verificar las etiquetas de validación. El entrenamiento inicial no reutiliza pesos NNUE.

## Repetir entrenamientos sin perder datos

Sin tocar los pasos 0–7, se puede ejecutar nuevamente solo el **paso 8** con otros `--epochs`, `--lr`, pesos de V, coeficientes de pérdidas, batch, scheduler o semilla. No cambia el `.pb`:

- **Conservar dos redes:** `--outdir "data\az\semilla_experimento_002"` (sin `--replace`). Cada directorio contiene sus epochs y su mejor checkpoint.
- **Reemplazar una red experimental existente:** reutilizar `--outdir "data\az\semilla_experimento_001"` y añadir `--replace`. La red anterior permanece hasta que haya terminado completamente el nuevo entrenamiento; si falla, se conserva.
- **Continuar el entrenamiento desde pesos anteriores** es una operación diferente de **volver a entrenar la semilla desde cero**; corresponde a la modalidad de refinamiento, no a este script.

## Validación: qué se calcula y sobre qué datos

1. Primero, una proporción configurable de **partidas completas** se reserva del total original y nunca es candidata al muestreo de partidas ni movimientos de entrenamiento.
2. **V:** sobre las posiciones de validación, compara la predicción neuronal con la fuente de valor seleccionada, leída de `positions`/`games`, y calcula **MSE**.
3. **P:** las jugadas históricas de validación forman distribuciones de frecuencia propias (distintas de las de entrenamiento) y calculan **entropía cruzada y coincidencia top-1**.
4. Selección de checkpoint: mínimo de `value_weight * MSE(V) + policy_weight * CE(P)` sobre validación. Cada epoch queda guardado aun si no es el mejor.
5. Una misma posición puede aparecer en ambos conjuntos (aperturas), pero **no se comparte ningún registro de partida o conteo**. Por ello, se mide generalización a partidas reservadas, no exclusivamente a posiciones inéditas.

## Compatibilidad, verificaciones y límites

- Se conservan intocados los programas heredados y el formato de sus tablas.
- Las bases intermedias `.pb` son copias independientes que evitan alterar la base de 14.000+ partidas.
- Los pasos 0, 1, 5 y 7 están probados con SQLite sintético; el paso 6 fue probado con un sustituto determinista de reglas ajedrecísticas y **requiere prueba real con `python-chess` y `.pb` real**.
- No se ha verificado aún la ejecución del entrenamiento en GPU Intel XPU, ni el etiquetado externo de Stockfish en el equipo del usuario.
- Cuidado con el tamaño del conjunto de validación: `--max-validation` es un límite de ejemplos y puede reducir los observados si es demasiado bajo. Para estudiar el MSE y la política en todas las partidas reservadas hay que establecer un límite mayor que las muestras disponibles.

Para probar sintaxis y las comprobaciones SQLite locales:

```powershell
& 'C:\Users\pedro\ufasta\Scripts\python.exe' -m pytest -q tests\test_az_workflow_v06116.py
```

**Se recomienda iniciar con una base de prueba que contenga suficientes partidas etiquetadas**, `--validation-pct 10`, `--games-pct 1`, `--moves-pct 20`, `--epochs 2` y un dispositivo validado. De esa manera puede auditarse el recuento y la separación antes de una corrida prolongada.
