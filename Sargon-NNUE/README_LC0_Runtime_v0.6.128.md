# Sargon-NNUE — Activación operativa LC0 CPU/GPU v0.6.128

## Problema confirmado
El motor B de `sargon_match.py` termina antes de responder `uciok` con `EvaluatorError: Lc0 backend initialization failed (onnx-dml): Unknown backend: onnx-dml`. Los bindings GPU v0.6.126 fueron construidos y probados exitosamente en `%TEMP%\lc0-gpu-test`, no en el Python operativo `ufasta`.

## Alcance
El script `scripts/sargon_lc0_gpu_activate_v0.6.128.ps1` modifica *solamente* la instalación `lczero-bindings` y sus DLL nativas en el Python indicado (`C:\Users\pedro\ufasta\Scripts\python.exe` por defecto). No modifica código fuente de Sargon-NNUE, sus brains, ni las búsquedas AlphaZero/LC0.

1. Comprueba el wheel validado de `%TEMP%\sargon-lc0-onnx-dml\dist-v126\lczero_bindings-0.1.0-cp314-cp314-win_amd64.whl`.
2. Respalda una vez el módulo, directorio de DLL y metadatos previos en `%TEMP%\sargon-lc0-onnx-dml\backup-ufasta-before-v0.6.128`.
3. Instala el wheel GPU en el Python seleccionado.
4. Copia las DLL nativas de ONNX Runtime 1.24.4 y DirectML 1.15.4 al directorio `.lczero_bindings.mesonpy.libs`, que `evaluators/lc0.py` ya registra explícitamente con `os.add_dll_directory`.
5. Ejecuta una inferencia inicial Eigen y ONNX-DML en el mismo intérprete y compara WDL y política.

## Ejecución
Desde la raíz del proyecto:

```powershell
.\scripts\sargon_lc0_gpu_activate_v0.6.128.ps1
```

Desde `scripts`:

```powershell
.\sargon_lc0_gpu_activate_v0.6.128.ps1
```

Si la red tiene una ubicación distinta:

```powershell
.\sargon_lc0_gpu_activate_v0.6.128.ps1 -Weights 'C:\ruta\modelo.pb.gz'
```

No ejecutes MATCH hasta obtener `OK: Eigen y ONNX-DML funcionan en el mismo Python operativo.`. Luego repetir:

```powershell
.\sargon_match.ps1 --brain ../data/brains/brains.json --pairs 2 --idA alphie --idB sophie
```

## Advertencias y reversión
- Es una intervención en el entorno Python, **no** un cambio del código fuente. El archivo de respaldo se guarda antes de sustituir el paquete, pero su restauración aún es manual; no lo elimines.
- Las DLL copiadas a `site-packages` pertenecen a la instalación específica de `ufasta`. Si reinstalás `lczero-bindings` nuevamente con pip, quizás debas repetir la copia.
- Si falla cualquiera de las pruebas, no asumir aceleración GPU ni ejecutar el MATCH hasta investigar el mensaje original.
- Los nombres `alphie` y `sophie` se resuelven del archivo `brains.json`; el script no modifica esa configuración.
