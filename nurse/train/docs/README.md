# Nurse: suite de entrenamiento NPZ (v0.1.47)

Se instala en `akkad/nurse/train/`. Todo checkpoint y exportación queda en `akkad/nurse/assets/`.

## Modelo que **no cambia**

Contrato del evaluador histórico `Sargon-NNUE/src/sargon_nnue/evaluators/npz.py` y
`nurse/src/nurse/_legacy/evaluators/npz.py`:

- 781 entradas (12×64 piezas + 4 enroques + 8 archivos EP + 1 turno).
- 64 ocultas ReLU; una salida, junto con coeficiente `hm_w`.
- `w_ih` (781,64), `b_h` (64,), `w_ho` (64,1), `b_o` escalar y `hm_w` escalar.
- `raw = ReLU(sum(w_ih[features])+b_h) @ w_ho + b_o + hm_w*halfmove/50`.
- `evaluate = int(400*raw)` (cp, perspectiva blanca).

Solo se usa el etiquetado de Stockfish de picoAlpha: `teacher_value` (con
`teacher_cp` para precisión cuando está presente, y `teacher_mate` para mates).
La etiqueta de picoAlpha es `tanh(cp_stm/400)`, desde el turno actual; se convierte
al POV **blancas**, y el entrenamiento compara `sigmoid(raw)` contra
`sigmoid(cp_white/400)`. Para mates (teacher_value = +/-1) se usa un tope
`abs(teacher_value)=.999` para evitar `atanh(1)`.

**Advertencia:** la base de picoAlpha guarda `fen` *anterior* a `played_uci` y
el teacher evalúa ese FEN. Se entrena/audita ese estado **etiquetado**, no una
posición artificialmente posterior con una etiqueta de la anterior.

## Ejecución

```powershell
cd akkad\nurse\train
.\run_train.ps1 -In ..\..\picoAlpha\data\sample_history.pb -Epoch 20 -Validation 20 -Fraction 10
.\run_audit.ps1 -Npz ..\assets\best.npz -In ..\..\picoAlpha\data\sample_history.pb -Out ..\assets\audit.json
.\run_export.ps1 -In ..\assets\best.npz
.\run_genesis.ps1 -Mon 0 -In ..\..\picoAlpha\data\sample_history.pb -Epoch 20 -Validation 20
```

`--sample N`: cantidad de **partidas** sin reemplazo; `--fraction P`: porcentaje
alternativo de partidas; de forma predeterminada 100%. `--validation` 1..100%:
se rechaza cualquier configuración que deje train o validation vacío.
Semilla 42 por defecto y partición a nivel partida; `split_manifest.json`
registra el subconjunto, particiones y cantidades de posiciones.

Cada epoch hace actualización con PyTorch y calcula dos MSE con red congelada:
TRAIN y VALIDATION. Crea `epoch_0001.npz`, etc. mediante escritura temporal,
`fsync` y `os.replace`; actualiza `best.npz` únicamente si baja la MSE de validación.
Interrupción durante un epoch: se retienen checkpoints de épocas completadas.

### Auditoría

`audit.py --npz best.npz --in history.pb --out audit.json`: compara cada
`fen` etiquetado con el score del algoritmo NPZ histórico, **en centipeones
blancos**, registra errores cuadrados individuales y diferencias.

`audit.py --npz best.npz --epd positions.epd --stockfish stockfish.exe
--out audit.json`: toma una jugada `bm` del EPD, la aplica **antes** de
comparar, y reetiqueta la posición posterior con Stockfish. No usa `ce` del
EPD anterior como si correspondiera a la posición posterior. Para EPD sin `bm`
registra una omisión explícita.

Con un solo método de referencia (teacher), su propio MSE respecto de sí mismo
es **0 por definición**. El JSON lo distingue expresamente del error NPZ–teacher;
no se inventa un segundo error independiente.

### Exportación INT8

`export.py --in best.npz --int8 best_int8.npz --hpp best_int8.hpp`.
Cuantización simétrica individual por tensor: `scale=max(abs(W))/127`,
`q=clip(round(W/scale),-127,127)`. Se incluyen sesgos y `hm_w`.
El NPZ cuantizado contiene pesos `int8` y campos `<tensor>_scale`.
El `.hpp` ofrece exactamente los mismos enteros y escalas mediante
`static const int8_t` para el enlazador XIP/Flash.

**Importante:** el evaluador NPZ original solo carga FP64/float.
No cargar `best_int8.npz` con ese evaluador: su inferencia precisa requiere
usar las escalas de esta variante. `best.npz` sigue siendo 100% compatible.

## MON reentrante

`run_genesis.ps1 -Mon 0` ejecuta train, audit y export.
`-Mon 1` inicia en audit (necesita `assets/best.npz`).
`-Mon 2` inicia solo exportación. Cada fase solo avanza si finaliza correctamente.
La fase train conserva checkpoints por época aun bajo interrupción.

## Estado de validación

Verificado sintácticamente y exportador comprobado en Python host; sin
validación de lectura EPD/PGN ni integración end-to-end real por ausencia de
`python-chess` en este entorno. Se requiere ejecutar en el entorno de Akkad
con `numpy`, `torch` y `python-chess` instalados. La fidelidad exacta al código
original de `sargon_train.py` se basa en la versión consultada del repositorio.
