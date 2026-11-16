# Nurse / picoGenus — versión 0.1.34

El parche permite comparar las tres funciones de evaluación estática con el **mismo jugador SARGON**, profundidad, quiescencia y presupuesto. No modifica los algoritmos de búsqueda ni los entrenadores.

## Integración

- `classic`: evaluador CLASSIC existente.
- `genus-pst`: `picoGenus/assets/genus_pst.json` (acepta `picogenus-sargon3-pst-v3` y `PST_best.json`).
- `genus-nnue`: `picoGenus/assets/genus_nnue.npy` (int16, 768→16→1, sin /256; legacy int8 mantiene /256).
- El evaluador NNUE carga el modelo apuntado por `genus_nnue.active.json`, si existe, y mantiene los pesos en memoria en el proceso Nurse.
- Evaluación en cp desde blancas, idéntica a las funciones utilizadas en entrenamiento.

El archivo `nurse/etc/brains/brains_genus_example.json` es **un ejemplo independiente**; copiar sus tres entradas al `brains.json` activo. Las rutas son relativas al archivo `nurse/etc/brains/brains.json` y se resuelven en el inicio. El formato es:

```json
"genus_pst": {"type":"nurse","player":"sargon","evaluator":{"evaluator":"genus-pst","network":"../../../picoGenus/assets/genus_pst.json"},"Depth":3,"QDepth":2,"tmax":15000,"timeout":30000},
"genus_nnue": {"type":"nurse","player":"sargon","evaluator":{"evaluator":"genus-nnue","network":"../../../picoGenus/assets/genus_nnue.npy"},"Depth":3,"QDepth":2,"tmax":15000,"timeout":30000}
```

**Dependencias:** instalar `numpy` y `python-chess` en el mismo Python que ejecuta Nurse. Se necesitan los módulos ya existentes en `picoGenus/tools/train`: `gen_sargon_core.py`, `gen_nnue_core.py`, `gen_nnue_storage.py`, `gen_checkpoints.py`. Deben conservarse los archivos y manifiesto de la corrida; no están incluidos en este ZIP.

**Pruebas de arranque** (desde la raíz de Akkad, con Nurse instalado o `PYTHONPATH=nurse/src`):

```powershell
python -m nurse.uci --help
python -m nurse.players.sargon --serve --config '{"_evaluator":"genus-pst","_network":"C:/.../picoGenus/assets/genus_pst.json","Depth":3,"QDepth":2,"tmax":15000,"timeout":30000}'
```

Para comparar capacidad ajedrecística en `match` o `benchmark`, usar las claves `genus_classic`, `genus_pst`, `genus_nnue` bajo las mismas condiciones. El ELO en `brains.json` es solo metadato inicial y no una medición de fuerza. Emplear aperturas y colores balanceados. El test integrado verifica el registro y la construcción; el smoke real necesita los modelos del usuario.
