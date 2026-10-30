# Sargon-NNUE v0.6.186 — keras-TF sobrescritura

Parche incremental sobre v0.6.185.

`keras-TF.py` sustituye por defecto el SavedModel existente en `--out`, ya sea un directorio `.tf` o un archivo antiguo con ese nombre. Exporta primero a un directorio temporal hermano, comprueba `saved_model.pb` y registra la procedencia del `.keras`; solo entonces reemplaza la salida previa. Ante fallo de exportación se conserva la salida anterior. Mantiene `--in`, `--out`, `--verbose` y `--help`. No cambia otras herramientas ni el player/evaluador.

Instalación: extraer el ZIP en la raíz de `Akkad/`.
