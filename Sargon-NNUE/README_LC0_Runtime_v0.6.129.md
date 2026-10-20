# Sargon-NNUE — Activación operativa LC0 CPU/GPU v0.6.129

## Corrección puntual
Se corrigió el defecto reproducible de PowerShell del instalador v0.6.128, línea 24:
`NameError: name 'platlib' is not defined` al ejecutar `sysconfig.get_paths()["platlib"]` mediante `python -c`.

Ahora la consulta a `sysconfig` se envía a Python por **STDIN**, sin que PowerShell altere las comillas del índice `"platlib"`.

## Ejecución
Descomprimir este ZIP sobre la raíz de Sargon-NNUE. Desde la carpeta `scripts`:

```powershell
.\sargon_lc0_gpu_activate_v0.6.129.ps1
```

Si los pesos neuronales se encuentran en otra ruta:

```powershell
.\sargon_lc0_gpu_activate_v0.6.129.ps1 -Weights 'C:\ruta\modelo.pb.gz'
```

## Requisitos y alcance
El script utiliza el **wheel GPU previamente construido y comprobado**:
`%TEMP%\sargon-lc0-onnx-dml\dist-v126\lczero_bindings-0.1.0-cp314-cp314-win_amd64.whl`.
También requiere los directorios temporales de ONNX Runtime y DirectML creados anteriormente.

**La intervención sobre ufasta comienza solamente después de validar Python, site-packages, wheel y DLL.**
Antes de instalar conserva una copia de la instalación anterior en:
`%TEMP%\sargon-lc0-onnx-dml\backup-ufasta-before-v0.6.129`.
Luego instala el wheel, copia las DLL necesarias y prueba ambas inferencias (Eigen + ONNX-DML) desde el mismo Python operativo.

El script no modifica el código fuente de Sargon-NNUE, `brains.json` ni el algoritmo AlphaZero.

## Validación
El script fue comprobado mediante inspección de los cambios y compilación sintáctica de ambos fragmentos Python incrustados. **No se pudo ejecutar PowerShell ni probar la instalación Windows en este entorno**.
No ejecutes MATCH hasta ver:
`OK: Eigen y ONNX-DML funcionan en el mismo Python operativo.`

Posteriormente, desde `scripts`:

```powershell
.\sargon_match.ps1 --brain ../data/brains/brains.json --pairs 2 --idA alphie --idB sophie
```
