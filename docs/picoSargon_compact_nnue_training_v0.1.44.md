# picoSargon — entrenamiento NNUE compacto 6-bit (v0.1.44)

## Hipótesis verificadas en la línea base 2026-11-13

- El evaluador `nurse/src/nurse/_legacy/evaluators/grumpy.py` y el de `picoSargon/x86/src/grumpy.cpp` usan `GRMP0001`, 1304 bytes, con 1680 coeficientes de 6 bits (`bytecode-31`, rango −31..32). No es INT8 convencional ni una NNUE de tamaño genérico.
- El empaquetado es 44 bytes de cabecera (`GRMP0001`, `uint32 little-endian=105`, SHA256 del payload) y 1260 bytes de coeficientes, 16 coeficientes por bloque de 12 bytes.
- La función consta de dos perspectivas, acumuladores de 8 unidades, tablas aditivas fila/columna, 8 buckets, ReLU limitada a [0,32], salida entera, conversión 400/1024 y un **término de material no entrenable**.
- El valor público del evaluador es **centipeones respecto de blancas**. La base de `picoAlpha/tools/train/teacher.py`, en cambio, registra `teacher_cp` y `teacher_value=tanh(cp/400)` **respecto del jugador que mueve**; para entrenamiento hay que invertir el signo de `teacher_cp` cuando el FEN indique negras al turno.
- Se excluyen `teacher_mate != NULL` y `teacher_cp IS NULL` para no tratar mate como cp. Los ejemplos con conteo de piezas no soportado o etiquetas inconsistentes también se excluyen y se registran.

## Diseño de la cadena

1. `train.py`: toma una muestra aleatoria de posiciones etiquetadas (sin reposición), persiste **IDs de entrenamiento y validación** en `picoSargon/data/<name>_split.json`, verifica etiquetas, optimiza coeficientes de 6 bits con cuantización simulada STE y guarda `picoSargon/assets/<name>_epoch_NNNN.pt` más `<name>_best.pt`. `best` se selecciona por el MSE en validación; si validación=0, por el MSE de entrenamiento reproducido al final del epoch. Genera `data/<name>_history.json`.
2. `export.py`: convierte una sola vez los valores cuantizados a `<name>.bin` en formato `GRMP0001` y `<name>.h`; verifica relectura. Nunca altera `grumpy.bin`.
3. `Audit.py`: usa solo los IDs de validación persistidos y evalúa con la **misma aritmética entera** del evaluador de producción. Compara opcionalmente con `--bin` de referencia. Escribe `data/<name>_audit.json` (por defecto `data/audit.json`).
4. `run_genesis.ps1`: `-mon 1` entrenamiento, `-mon 2` exportación, `-mon 3` auditoría. Se incrementa `MON` solamente después de éxito.

### Ejemplo

Desde `picoSargon/tools/train`:

```powershell
.\run_genesis.ps1 -mon 1 -database "C:\ruta\history.pb" -network pitty `
  -sample 100000 -validation 20 -lr 0.03 -lrmin 0.001 -epoch 50
```

Reanudar a partir del mejor checkpoint generado:

```powershell
.\run_genesis.ps1 -mon 2 -database "C:\ruta\history.pb" -network pitty
```

La primera ejecución necesita `picoSargon/assets/grumpy.bin` **solo como pesos iniciales y referencia**; no se sobreescribe. Para entrenamiento sin esa inicialización, se puede llamar a `train.py` directamente sin `--init`.

**Limitaciones declaradas:** `--validation 100` no es entrenable porque deja cero ejemplos para actualizar los pesos (error explícito). `--validation 0` permite entrenar, pero no ejecutar auditoría hold-out. El muestreo SQLite `ORDER BY RANDOM()` no se puede reproducir mediante `--seed`; la partición **efectiva** se guarda y audita por IDs. La división por posiciones puede contener posiciones de la misma partida en ambos conjuntos; no es una validación estricta por partidas independientes. El modelo entrenado es compatible con el formato GRMP, pero la mejora de MSE contra la referencia debe **demostrarse** con `Audit.py` y datos reales: no está garantizada.

## Dependencias

`python` con `numpy` y `torch` para entrenar/exportar. `Audit.py` utiliza `numpy` y librería estándar. No requiere `python-chess` porque el parser de FEN es específico de las características del evaluador.
