# Integración picoKeras v0.6.183 — instalación obligatoria

La versión 0.6.182 empaquetaba un **aplicador** y no archivos del núcleo premodificados. Copiar el ZIP sin ejecutar el aplicador deja `brains.py` intacto: por eso Benchmark sigue dando `player inválido: picoKeras`.

1. Extraiga este ZIP en **Akkad/** (el primer directorio es `sargon-NNUE/`).
2. Desde **sargon-NNUE/**, ejecute `python .\scripts\install_picokeras_v0.6.183.py`. Este comando aplica los cambios de 0.6.182 y comprueba que `brains.validate` acepte el identificador.
3. Reejecute `run_benchmark.ps1` desde `scripts/`.

**Nota importante:** si su árbol local difiere de las anclas de 0.6.182, el aplicador abortará y no se debe asumir que la integración está instalada. La verificación importará los módulos del proyecto y requiere que estén disponibles sus dependencias (por ejemplo python-chess). No se ha probado contra su checkout particular de Windows. Tampoco hay aquí una extensión para entrenar nuevos parámetros en `sargon_train.py`.

Perfil `penelope`:
```
"penelope": {
  "player": "picoKeras",
  "evaluator": "null",
  "engine-path": "../x86/picoKeras/build/Release/picoKeras.exe",
  "network": "../data/runs/keras/small.int8.tflite",
  "nodes": 1,
  "timeout": 30000,
  "rating_elo": 400
}
```
