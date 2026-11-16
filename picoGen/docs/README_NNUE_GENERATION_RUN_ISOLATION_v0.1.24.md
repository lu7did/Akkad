# picoGenus NNUE v0.1.24 — checkpoints aislados por corrida

## Defecto reproducido

v0.1.23 guardaba `genus_nnue.gen00002.npy` para toda corrida con el mismo `--out`. Una segunda corrida con resultados diferentes encontraba ese archivo, detectaba contenido distinto y abortaba con `Generation model already exists with different content`. Esto podía ocurrir en la generación 2 aunque la corrida nueva fuese válida.

## Corrección

Se genera un UUID nuevo por invocación. Cada checkpoint por generación se guarda como:

- `genus_nnue.run-<32 caracteres hex>.gen00001.json`: población entera, errores, estado RNG, configuración y `run_id`.
- `genus_nnue.run-<32 caracteres hex>.gen00001.npy`: mejor red de esa generación, 12.321 INT8.

El JSON registra `generation_model_file`, que identifica el `.npy` correspondiente, además de `parent_checkpoint` en las reanudaciones. Primero se guarda y verifica el `.npy`; luego se publica el JSON. Los archivos de generaciones anteriores (`genus_nnue.gen*.json/.npy`) no se sobrescriben ni se eliminan.

Al invocar `--resume <checkpoint.json>`, se usa exactamente la población y estado RNG del checkpoint de origen, pero se crea un nuevo identificador de corrida para evitar pisar las generaciones que ya pudieran existir. Esto constituye una rama de continuación y queda identificado con `parent_checkpoint`.

**No cambia:** el genoma 768×16×1, los 12.321 pesos INT8, mutación, selección, cruzamiento, separación de validación, fitness, cálculo de MSE, `.active.json` y el cargador de Nurse.

La publicación del mejor modelo global usa los nombres inmutables y el manifiesto de v0.1.23. Los nombres clásicos `genus_nnue.npy` y `genus_nnue.best.npy` son copias de compatibilidad y pueden quedar antiguos si están bloqueados por Windows. Nurse consulta `.active.json` para cargar el modelo vigente.

## Ejecución

Desde `picoGenus/tools/train`:

```powershell
.\run_genesis.ps1 --mon 3
```

Los valores de `--in`, `--out` y el resto siguen tomándose de tu script habitual; el parche no toca `run_genesis.ps1`.

Para reanudar desde una generación completada, pasar la ruta del JSON al `--resume` de `genNNUE.py`, manteniendo los mismos datos de entrada, semilla, población y porcentaje de validación.

## Pruebas

- Dos ejecuciones con el mismo `--out` y una red `genus_nnue.gen00002.npy` antigua incompatible: ambas completan y preservan el archivo antiguo.
- Dos reanudaciones a partir de un mismo checkpoint con el mismo `--out`: generan ramas independientes sin sobrescribir checkpoint original.
- Validación, bloqueo simulado de Windows y carga Nurse de la red activa (suite v0.1.23 ajustada al nuevo nombre).

El conjunto de 7 pruebas pasó en Linux/Python. No se ha reproducido el bloqueo nativo de Windows ni ejecutado una corrida de 5.000 posiciones aquí.
