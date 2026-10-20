# Sargon-NNUE v0.6.33 — backend PyTorch experimental

Este parche modifica **únicamente** `src/sargon_nnue/sargon_train.py` y agrega `src/sargon_nnue/torch_train.py`. Es un parche sobre v0.6.32, no un proyecto completo. El modo NumPy permanece sin cambios funcionales cuando no se especifica `--pytorch`.

## Uso

```powershell
C:\Users\pedro\ufasta\Scripts\python.exe -m sargon_nnue.sargon_train `
  --pytorch --device xpu --torch-dtype float32 `
  --input "..\data\pb\boot.pb" --nnuedir "..\data\nnue\torch1" `
  --epoch 10 --validation 5 --seed 42 `
  --optimizer adamw --lr 0.0001 --weight-decay 0.0001 `
  --batch-size 512 --grad-clip 1 --save-best
```

Para comparación numérica precisa, usar `--device cpu --torch-dtype float64 --batch-size 64`, y una semilla y partición iguales. `--device auto` prioriza XPU, luego CUDA, luego CPU.

## Optimizadores disponibles con `--pytorch`

`sgd`, `adam`, `adamw`, `rmsprop`, `adagrad`, `adadelta`, `adamax`, `nadam`, `radam`, `asgd`, `rprop` (sujeto a la versión instalada de PyTorch).

Ajustes de optimizador: `--weight-decay`, `--momentum`, `--dampening`, `--nesterov`, `--beta1`, `--beta2`, `--eps`, `--alpha`, `--centered`, `--rho`, `--lr-decay`; se aplican **solo si el optimizador soporta el argumento**. El optimizador Rprop no admite weight decay. No se habilita LBFGS, ya que necesita closures y un ciclo de entrenamiento distinto.

Otros parámetros: `--torch-dtype {float32,float64}`, `--device {auto,cpu,cuda,xpu}`, `--grad-clip` (norma máxima, 0 desactiva), `--scheduler {none,step,cosine,plateau}`, `--step-size`, `--gamma`, `--min-lr`, `--patience`, `--early-stopping` (0 desactiva), `--min-delta`, `--save-best`, `--save-optimizer-state`.

## Contratos preservados

- Consume el mismo `.pb` SQLite, preservando división *por partida*, semilla y permutación diferente cada epoch.
- Reproduce la arquitectura NNUE **781→64 ReLU→1** con la contribución adicional `hm_w * halfmove/50` y salida sigmoide recortada al intervalo [-15,15].
- Utiliza `target = (1-z2)*(resultado/2) + z2*(W+D/2)/1000`; con `z2=0`, no requiere WDL de Stockfish.
- Exporta checkpoints `.npz` con `w_ih`, `b_h`, `w_ho`, `b_o`, `hm_w` en `float64` compatibles con el evaluador existente. Se incluyen metadatos opcionales.
- Calcula MSE online, MSE fijo y MSE de validación sin gradientes. No altera la función de evaluación del player.
- El peso inicial sin checkpoint usa la misma inicialización NumPy semilla 42 del evaluador. Los resultados tras una actualización **no tienen por qué ser idénticos** entre NumPy y PyTorch, pues los algoritmos y órdenes de cómputo pueden diferir.

## Limitaciones explícitas

- El modo PyTorch utiliza matrices de entrada densas `[batch,781]`. No emplea `EmbeddingBag` ni sparse Adam. La velocidad real en XPU aún debe medirse.
- `--save-optimizer-state` guarda archivos `.pt` adicionales para diagnóstico; todavía **no implementa reanudación** del estado de optimizador. No interpretar `--network` como una reanudación exacta.
- La primera carga del dataset sigue construyendo índices en memoria y consulta SQLite por minibatch; es funcional, pero puede limitar la aceleración de la GPU.
- La ruta de checkpoints es independiente: usar directorios distintos para CPU/NumPy/XPU.
- No se ha comprobado la ejecución XPU aquí. Se probó PyTorch CPU en dataset sintético, el exportador `.npz` y los errores de dataset inexistente.
