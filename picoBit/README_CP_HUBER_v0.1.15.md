# picoBit v0.1.15 — aprendizaje directo de evaluaciones Stockfish (cp)

Cambio autorizado: **objetivo de entrenamiento**, sin modificar las particiones ni los datos.

- `train.py` toma CP de Stockfish con perspectiva de blancas, limita las etiquetas a ±1500 cp como antes y aplica una escala **lineal** `cp / 400` para estabilidad numérica; ya no convierte cp a probabilidades.
- La salida final de `bnn_core.create_model()` es `Dense(1, activation='linear')`.
- Entrena con Huber `delta=0.5` en la escala cp/400 (umbral de 200 cp). Los valores de telemetría MSE y MAE se muestran en cp² y cp, respectivamente; el criterio de selección de `best.bnn` y los callbacks es Huber en validación.
- La arquitectura binaria, STE, escalas alfa, calibración BN, estratos, hiperparámetros y el formato `best.bnn` se mantienen.
- `run_genesis.ps1 --mon 1` produce exactamente `picoBit/assets/best.bnn`. **Sobrescribe** el archivo preexistente cuando encuentra una epoch mejor. La referencia anterior debe estar preservada de antemano (según el usuario, ya lo está).
- `Audit.py --bin <checkpoint-historico>` puede comparar una cabeza sigmoid histórica frente a una lineal: cada una es convertida a centipeones mediante su propia fórmula.
- El convertidor offline `src/export_native.py` detecta la activación en el checkpoint. El formato `.bnni` utiliza versión de cabecera 1 para sigmoid y 2 para lineal, con la misma disposición binaria y fórmula de coeficientes de salida apropiada. `src/bnn.py` detecta la versión y genera de nuevo la caché si la activación del checkpoint cambia. No se necesita DLL ni TensorFlow para Nurse.
- `verify_inference.py` admite las dos cabezas, etiquetando el dato de salida previo a la conversión como `keras_output_raw`.

## Entrenamiento y auditoría

Desde la raíz de `akkad` (usar el mismo `--sample`, `--seed` y base que en la corrida anterior):

```powershell
.\picoBit\tools\train\run_genesis.ps1 --mon 1 --sample 100000 --validation 20 --seed 42 --bin picoBit/assets/<anterior-guardado>.bnn
```

El nombre entre `<...>` debe reemplazarse por la ruta **real** del checkpoint anterior; si se omite `--bin`, Audit compara sólo el nuevo contra CLASSIC y Stockfish. También se puede continuar en `--mon 3` para auditar después, con `--bin`.

## Comprobaciones efectuadas

- Sintaxis Python de los módulos modificados.
- Pruebas sintéticas independientes de empaquetado e inferencia: 40 posiciones para cada tipo de salida, máximo 0 cp de diferencia contra referencia NumPy.
- Regresión del evaluador previo: 24 posiciones sintéticas, máximo 0 cp de diferencia.
- **No se ejecutó un entrenamiento real TensorFlow**, porque no está instalado en el entorno de creación. La mejora ajedrecística no se afirma sin datos de una nueva corrida.
