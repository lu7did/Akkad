# Sargon-NNUE – picoKeras integración (v0.6.182)

Parche incremental basado en el código de `lu7did/Akkad` (`Sargon-NNUE/src/sargon_nnue`) consultado el 28-10-2026. Contiene un adaptador UCI y un aplicador de cambios con anclas estrictas; no incluye una línea de base completa.

## Instalación
1. Extraer ZIP sobre la raíz **Akkad**, preservando el subdirectorio `sargon-NNUE/` (Windows trata mayúsculas/minúsculas igual).
2. Desde `sargon-NNUE`: `python scripts/apply_picokeras_integration_v0.6.182.py`.
3. `python -m compileall -q src/sargon_nnue`.
4. Con el venv del proyecto y `PYTHONPATH=src`: `python -m unittest discover -s tests -p test_picokeras_integration_v06182.py`.

**Importante:** El aplicador se detiene antes de escribir nada si las anclas esperadas de la versión del repositorio no coinciden. Si falla, no modifiques a mano las validaciones: hay que reconciliar la versión local. El adaptador UCI estático no necesita recompilar picoKeras.exe.

## Ejemplo para incorporar a tu brains.json

```json
"penelope": {
  "player": "picokeras",
  "evaluator": "null",
  "engine-path": "../x86/picoKeras/build/Release/picoKeras.exe",
  "network": "../data/runs/keras/small.int8.tflite",
  "tmax": 15000,
  "timeout": 30000,
  "rating_elo": 400
}
```

Si usas `--brain` más `--id penelope`, la ruta relativa se evalúa igual que los demás motores según el directorio de ejecución de Sargon-NNUE; probar siempre desde `scripts/` como los lanzadores existentes. Corrige `picoKras` en el brain adjunto; el nombre del player es **picokeras** (las mayúsculas de `picoKeras` son admitidas). El fichero `data/brains/picokeras_example.json` no sobrescribe tus perfiles.

## Rutas de ejecución
- **Listen**: `sargon_listen` + perfil `penelope`, expone UCI TCP y administra `picoKeras.exe --stdio` mediante adaptador Python.
- **Match/Rally/Benchmark**: usan `brains.validate`, `factory.build_engine` y los mismos argumentos del listener. No se agregan validadores nuevos en esos tres módulos; se corrige el único validador explícito adicional observado en `sargon_match.py`.
- **Train**: `sargon_train.py` no acepta perfiles de motores UCI; entrena pesos de redes propias. No se añade un modo falso de entrenamiento picokeras. Las herramientas que consumen UCI usan el mismo listener.
- **TCP directo**: `picoKeras.exe --network MODEL --host 0.0.0.0 --port 6110`; para conectarse se puede usar `player=external`, `url=127.0.0.1:6110`, sin `engine-path`.

El motor actual es **searchless 1ply**. Informa `info ... string eval_rival`, no `score cp`. El adaptador devuelve `score_cp=0` en vez de falsificar un valor que la red no ofrece en centipeones. La opción `nodes` de un brain no limita la búsqueda de picoKeras, que actualmente ignora `go nodes`; `tmax` funciona como timeout de la integración, no como garantía de límite duro de evaluación de C++.

## Estado de comprobación
Se comprobó sintaxis Python de los archivos nuevos. No se ejecutaron pruebas de extremo a extremo en Windows ni se aplicaron los cambios sobre la línea de base local del usuario. El aplicador contiene protecciones contra reemplazos silenciosos incorrectos.
