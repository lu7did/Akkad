# Akkad picoGenus NNUE v0.1.23 — bloqueo Windows y validación

## Fallo corregido

`os.replace(.genus_nnue.<tmp>.npy, genus_nnue.npy)` puede fallar con `WinError 5` cuando un programa lector, sincronizador o antivirus bloquea el destino en Windows. Reintentar la operación no garantiza el éxito. El parche preserva primero el modelo en un archivo inmutable `genus_nnue.best.g00001.<uuid>.npy`, valida su contenido y escribe `genus_nnue.active.json` con el archivo activo. Nurse lee el manifiesto y carga ese `.npy` inmutable, incluso cuando el `.npy` tradicional esté bloqueado. Las rutas heredadas `genus_nnue.npy` y `genus_nnue.best.npy` se actualizan cuando el sistema lo permite, con reintentos; si no, se advierte explícitamente que pueden estar desactualizadas. **No debe asumirse que el archivo convencional es el más reciente cuando existe `genus_nnue.active.json`.**

No se intentan quitar bloqueos del sistema operativo ni cambiar permisos del usuario; un directorio no escribible o un manifiesto imposible de publicar se consideran errores reales.

## Validación independiente

`--validation_sample NN` especifica el porcentaje de posiciones etiquetadas y válidas destinado a validación (por defecto 20, intervalo estricto 0 < NN < 100). El conjunto se separa una única vez antes de inicializar la población mediante una permutación determinista de NumPy con `--seed`; no se cruzan ejemplos de entrenamiento y validación. Se conserva el orden de las posiciones restantes. Por ejemplo, con 5000 registros válidos se usan 4000 para entrenar y 1000 para validar.

La selección, el elitismo, las mutaciones y el cruzamiento utilizan exclusivamente el MSE del conjunto de entrenamiento, tal como antes. **Cada generación se evalúa sobre el conjunto de validación la mejor red GLOBAL identificada por el MSE de entrenamiento.** Su MSE (cp²) y RMSE (cp) se muestran en la consola y se guardan en el JSON de generación. La validación no participa en la selección del campeón.

La partición es por registros, no por partidas; posiciones de una misma partida pueden aparecer en conjuntos distintos. No se afirma independencia estadística por partida. Un enfoque agrupado por partida requeriría otra decisión metodológica.

## Compatibilidad de checkpoints

El formato de checkpoint completo es `picogenus-nnue-generation-v3`, guarda las 12.321 ponderaciones de cada individuo y sus métricas, el mejor global, el estado del generador aleatorio, la huella de los datos y `validation_sample`. `--resume` requiere el mismo `--in`, `--seed`, `--poblacion`, `--max-positions` y `--validation_sample`; permite aumentar `--generaciones`. Los checkpoints v2 previos al split de validación se rechazan explícitamente: usar aquellos pesos como entrenamiento con un subconjunto ahora reservado para validación produciría contaminación de validación. Los archivos `.npy` antiguos siguen siendo modelos válidos y pueden ser leídos directamente por Nurse cuando no existe manifiesto.

Cada mejora del MSE de entrenamiento se guarda de forma inmediata en un archivo inmutable, también ante Ctrl+C; el JSON de generación completo se emite tras evaluar toda la población.

## Ejecución

Desde `akkad/picoGenus/tools/train`:

```powershell
python .\genNNUE.py `
  --in "C:\Users\pedro\github\bobby\akkad\picoGenus\assets\genus_sample.pb" `
  --out "C:\Users\pedro\github\bobby\akkad\picoGenus\assets\genus_nnue.npy" `
  --poblacion 100 --generaciones 100 --seed 42 --validation_sample 20
```

Reemplazar la ruta de entrada por la base real que utiliza `run_genesis.ps1`. El script de Genesis no se modifica: la validación por defecto es 20%.

Ejemplo de telemetría:

```
G00005: best_train_rmse=250.11cp mean_train_rmse=298.20cp global_train_rmse=248.60cp validation_mse=66522.15cp² validation_rmse=257.92cp val_n=1000
```

Es una línea ilustrativa, no un resultado real.

## Pruebas

Se incluyen tests para bloqueo permanente simulado de `genus_nnue.npy`, uso del modelo activo por Nurse, partición reproducible sin registros solapados, MSE global de validación y reanudación de checkpoint v3. La prueba nativa en PowerShell con archivos abiertos por procesos externos continúa pendiente.
