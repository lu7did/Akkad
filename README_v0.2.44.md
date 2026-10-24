# picoAlpha v0.2.44 — herramientas de destilación compatibles con TinyGyal

Reemplaza **solo** los cuatro archivos dentro de `tools/picoDistiller`. No aplicar v0.2.43 antes.

- Entrada: mismos 112 planos y convención de orientación que `src/net.cpp`.
- Política: 73×64 = 4.672 índices de `picoalpha::policy_index`, sin `%1968`.
- Red estudiante: convolución inicial 112→8, un bloque residual con SE, cabeza convolucional espacial 8→8→80, cabeza de valor 8→32→128→1.
- Entrenamiento desde cero: no cargar el viejo checkpoint `.pt` de 13 planos.
- Separación por partidas; pérdidas P+V, barra de progreso y checkpoints por época heredados de v0.2.42.
- Etiquetas aisladas en tabla `pico_distillation` y reemplazables en ejecuciones sucesivas.

## Ejecución

```powershell
python .\tools\picoDistiller\picoPrepare.py --input "RUTA\datos.pb" --weights "RUTA\tinygyal-8.pb.gz"
python .\tools\picoDistiller\picoDistiller.py --input "RUTA\datos.pb" --out "RUTA\runs" --epoch 20 --lr 0.0001 --min-lr 0.000001 --validation 20 --batch-size 64
```

## Limitaciones de verificación

No se ejecutó contra una base `.pb` real del usuario ni contra `lczero-bindings` en Windows. Es necesario verificar el esquema y la API sobre ese entorno. La conversión INT8 y adaptación del evaluador C++ 1×8 corresponden a la etapa posterior, una vez entrenada la red.
