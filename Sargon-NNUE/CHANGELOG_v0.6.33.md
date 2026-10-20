# v0.6.33 — Backend PyTorch independiente

- Incorpora `--pytorch`, que deriva el entrenamiento a `torch_train.py`; modo NumPy conservado por defecto.
- Optimización independiente con autograd y optimizadores nativos PyTorch.
- Selección de dispositivo `auto/cpu/cuda/xpu`, tipos `float32/float64`, parámetros de optimizadores, clipping, schedulers, early stopping y selección de mejor checkpoint opcional.
- Entrenamiento y validación por partida, scrambling por epoch y cálculo de MSE online/fijo/validación.
- Exportación a `.npz` compatible con la red 781-64-1 sin alterar el evaluador.
- Probado con dataset SQLite pequeño en CPU: AdamW, SGD, lectura `.npz`, archivo faltante; compilación sintáctica correcta.
- **Sin cambios** en `sargon-prepare.py`, formato PB, evaluador ni método NumPy existente.
