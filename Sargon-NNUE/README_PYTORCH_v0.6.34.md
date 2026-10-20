# Prueba XPU v0.6.34

Ejemplo:

```powershell
python -m sargon_nnue.sargon_train --pytorch --device xpu --torch-dtype float32 --torch-foreach off --input "..\data\pb\boot.pb" --nnuedir "..\data\nnue\torch034" --epoch 2 --validation 5 --optimizer adamw --lr 0.0001 --weight-decay 0.0001 --batch-size 64 --seed 42
```

Si persiste error de memoria, probar `--device cpu` manteniendo el optimizador y los datos. No inferir que la arquitectura requiere más VRAM: 781x64 tiene pocos pesos; XPU también usa memoria temporal del runtime. `--torch-foreach off` puede disminuir memoria de temporales, pero no corrige otras causas de falta de memoria.
