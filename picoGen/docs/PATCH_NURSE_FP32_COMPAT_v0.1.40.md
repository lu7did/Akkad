# Akkad picoGen / Nurse v0.1.40 — inferencia FP32

Base de GitHub consultada: `lu7did/Akkad`, commit `85a4cc36e55ebb884002224ec36b6bcedaf8efbf`.
Aplicar sobre v0.1.39. ZIP incremental con rutas relativas a la raíz de Akkad.

## Estado ya implementado en picoGen

`picoGen/tools/train/gen_fp32_core.py`, `genPST.py` y `genNNUE.py` (v0.1.38)
ya entrenan y exportan FP32. Los cromosomas son vectores float32, mutación
Bernoulli(0.03) más Gauss(0, sigma), y no requieren modificación adicional.
No se alteran las rutinas archivadas int16/Gray: preservan experimentos anteriores.

## Compatibilidad nueva Nurse

- `genus-pst`: acepta `picogen-binpack-genetic-fp32-v1` (model=PST, dtype=float32)
  y los coeficientes en punto flotante, con el peón fijo 100 y límites del
  evaluador heurístico original. Conserva formatos anteriores.
- `genus-nnue`: acepta `best.npy` de 12321 float32 con manifiesto
  `picogen-nnue-active-fp32-v1`, incluyendo carga y validación seguras.
- Núcleo NNUE Nurse calcula sumas y productos en FP32, mismo orden que
  `picoGen/tools/train/gen_fp32_core.py:nnue_forward`. Conserva int16 sin escala
  e int8 con división entre 256. No hay conversión ni cuantización de pesos FP32.
- No se altera MCTSE de picoAlpha: su PANNI8 de 780 entradas y dos cabezas
  es una arquitectura distinta e incompatible con esta TinyNNUE 768x16x1.

## Configuración del modelo entrenado

No se reemplazan los perfiles antiguos del archivo `nurse/etc/brains/brains.json`.
Para usar los modelos FP32 se debe configurar en `evaluator.network`:

- PST: `.../picoGen/assets/binpack-fp32-001/pst/best.json`
- NNUE: `.../picoGen/assets/binpack-fp32-001/nnue/best.npy`

Los tests nuevos están en `nurse/tests/test_genus_fp32_v0140.py`.
Ejecutar desde raíz del repositorio con `PYTHONPATH=nurse/src` o el entorno
instalado de Nurse: `python -m unittest discover -s nurse/tests -p test_genus_fp32_v0140.py`.
Requiere NumPy; evaluación real de posiciones requiere además python-chess.
