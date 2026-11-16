# Nurse MCTSP + MCTSE — integración v0.1.37

- MCTSP es un **player** MCTS PUCT; MCTSE es su **evaluator** de dos cabezas (política y valor).
- El modelo requerido es un checkpoint `.pt` de picoAlpha, arquitectura **780 entradas, 16 ocultas, policy from_to, value tanh**, no el NNUE INT16 de picoGen.
- `network` es la ubicación del archivo del modelo definida por el usuario en `brains.json`, resuelta respecto de la ubicación de ese archivo (y rutas de compatibilidad). Ninguna ruta a proyectos está fija en el código.
- `arguments.sims` (default 200), `arguments.depth` (default `Depth` o 12), `arguments.cpuct` (default 1.4); `tmax` y `timeout` son milisegundos.
- MCTSE solo se admite con MCTSP, puesto que MCTSP necesita la política y el valor; no es un evaluador genérico en centipeones para Sargon.
- Las herramientas `listen`, `benchmark`, `match`, `rally` y el orquestador UCI comparten `nurse.config.read_brain` y por ello las mismas restricciones.
- `run_match.py` también admite `--a-player mctsp --a-evaluator mctse` y su equivalente para B. La ejecución requiere siempre `--brain`, `--idA`, `--idB` y sus perfiles reales.

Ejemplo en `nurse/etc/brains/mctsp_mctse_example.json`; sustituir `REEMPLAZAR_POR_CHECKPOINT_REAL.pt` por el archivo real.

### Comandos (desde la raíz akkad, con Nurse instalable en Python)

```powershell
python nurse/scripts/run_benchmark.py --brain nurse/etc/brains/brains.json --ids mctsp_mctse --mode positions --positions 24 --rounds 1
python nurse/scripts/run_match.py --brain nurse/etc/brains/brains.json --idA mctsp_mctse --idB genus_classic --pairs 10
python nurse/scripts/run_listen.py --brains nurse/etc/brains/brains.json --id mctsp_mctse --ip 0.0.0.0 --port 6200
```

Rally: agregar el ID `mctsp_mctse` a la lista `brains` de un torneo del archivo de configuración de rally existente; el motor se inicia mediante el mismo Nurse UCI.
