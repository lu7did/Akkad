#*================================================================================================================*
#* Proyecto sargon-nnue
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* sargon_lc0_gpu_activate_v0.6.129.ps1
#* Activates the LC0 GPU setup for version 0.6.129
#=================================================================================================================*
# Sargon-NNUE GPU runtime activation v0.6.129
# Only changes Python venv installed lczero-bindings + its native DLL directory.
# Does not modify Sargon-NNUE source, brains.json or GPU drivers.
param(
    [string]$Python = 'C:\Users\pedro\ufasta\Scripts\python.exe',
    [string]$Workspace = (Join-Path $env:TEMP 'sargon-lc0-onnx-dml'),
    [string]$Weights = ''
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw "Python no encontrado: $Python" }
$wheel = Join-Path $Workspace 'dist-v126\lczero_bindings-0.1.0-cp314-cp314-win_amd64.whl'
$ortDir = Join-Path $Workspace 'ort-1.24.4\runtimes\win-x64\native'
$dmlDir = Join-Path $Workspace 'directml-1.15.4\bin\x64-win'
foreach ($dir in @($ortDir, $dmlDir)) {
    if (-not (Test-Path -LiteralPath $dir -PathType Container)) { throw "Falta directorio requerido: $dir" }
}
if (-not (Test-Path -LiteralPath $wheel -PathType Leaf)) { throw "Falta el wheel validado v0.6.126: $wheel" }
if (-not (Test-Path -LiteralPath (Join-Path $ortDir 'onnxruntime.dll') -PathType Leaf)) { throw 'Falta onnxruntime.dll' }
if (-not (Test-Path -LiteralPath (Join-Path $dmlDir 'DirectML.dll') -PathType Leaf)) { throw 'Falta DirectML.dll' }

# Confirm that the wheel matches the selected interpreter.
& $Python -c 'import sys; assert sys.version_info[:2] == (3,14) and sys.maxsize > 2**32, "Wheel requires Python 3.14 x64"; print("Interpreter:", sys.executable)'
if ($LASTEXITCODE -ne 0) { throw 'El wheel no coincide con el Python seleccionado.' }
# Send Python source through STDIN: PowerShell may strip nested quotes from -c arguments.
$siteOutput = @'
import sysconfig
print(sysconfig.get_paths()["platlib"])
'@ | & $Python -
if ($LASTEXITCODE -ne 0) { throw 'No se pudo obtener el directorio site-packages del interprete seleccionado.' }
$site = [string]($siteOutput | Select-Object -Last 1)
$site = $site.Trim()
if (-not $site -or -not (Test-Path -LiteralPath $site -PathType Container)) { throw "site-packages no encontrado: $site" }

# Backup the original bindings once, without overwriting a previous backup.
$backup = Join-Path $Workspace 'backup-ufasta-before-v0.6.129'
if (-not (Test-Path -LiteralPath $backup)) {
    New-Item -ItemType Directory -Path $backup -Force | Out-Null
    $items = @()
    $pkg = Join-Path $site 'lczero'
    $libs = Join-Path $site '.lczero_bindings.mesonpy.libs'
    if (Test-Path -LiteralPath $pkg) { $items += Get-Item -LiteralPath $pkg }
    if (Test-Path -LiteralPath $libs) { $items += Get-Item -LiteralPath $libs }
    $items += @(Get-ChildItem -LiteralPath $site -Directory -Filter 'lczero_bindings*.dist-info')
    foreach ($item in $items) {
        Copy-Item -LiteralPath $item.FullName -Destination $backup -Recurse -Force
    }
    Write-Host "Respaldo de bindings anteriores en: $backup"
} else {
    Write-Host "Se conserva el respaldo existente: $backup"
}

Write-Host 'Instalando wheel GPU v0.6.126 en el Python operativo...'
& $Python -m pip install --no-deps --force-reinstall $wheel
if ($LASTEXITCODE -ne 0) { throw 'Fallo la instalacion del wheel GPU.' }

# The existing lc0.py already adds this directory to DLL search paths.
# Place the exact native runtime binaries tested in the disposable venv there.
$nativeDir = Join-Path $site '.lczero_bindings.mesonpy.libs'
if (-not (Test-Path -LiteralPath $nativeDir -PathType Container)) { throw "No existe directorio de DLL de bindings: $nativeDir" }
$nativeDlls = @(Get-ChildItem -LiteralPath $ortDir -File -Filter '*.dll') + @(Get-ChildItem -LiteralPath $dmlDir -File -Filter '*.dll')
if ($nativeDlls.Count -lt 2) { throw 'No se encontraron las DLL esperadas de ONNX Runtime y DirectML.' }
foreach ($dll in $nativeDlls) {
    Copy-Item -LiteralPath $dll.FullName -Destination (Join-Path $nativeDir $dll.Name) -Force
    Write-Host "DLL instalada: $($dll.Name)"
}

if (-not $Weights) {
    $root = Split-Path -Parent $PSScriptRoot
    $Weights = Join-Path $root 'data\runs\lczero\t1-256x10-distilled-swa-2432500.pb.gz'
}
if (-not (Test-Path -LiteralPath $Weights -PathType Leaf)) { throw "Faltan pesos para test de inferencia: $Weights (usa -Weights con una ruta existente)" }

$oldWeights = [Environment]::GetEnvironmentVariable('SARGON_LC0_TEST_WEIGHTS', 'Process')
try {
    $env:SARGON_LC0_TEST_WEIGHTS = (Resolve-Path -LiteralPath $Weights).Path
    @'
import os, sys, math
from pathlib import Path
native = Path(sys.prefix) / 'Lib' / 'site-packages' / '.lczero_bindings.mesonpy.libs'
handles = [os.add_dll_directory(str(native))]
from lczero.backends import Weights, Backend, GameState
available = Backend.available_backends()
print('BACKENDS EN PYTHON OPERATIVO:', available)
for name in ('eigen', 'onnx-dml'):
    if name not in available:
        raise RuntimeError(f'Backend {name} no registrado')
w = Weights(os.environ['SARGON_LC0_TEST_WEIGHTS'])
gs = GameState(fen='rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1')
wdl = {}
for name in ('eigen', 'onnx-dml'):
    kw = {'weights': w, 'backend': name}
    if name == 'onnx-dml': kw['options'] = 'gpu=0'
    backend = Backend(**kw)
    result = backend.evaluate([gs.as_input(backend)])[0]
    q, d = float(result.q()), float(result.d())
    vals = ((1.0-d+q)/2.0, d, (1.0-d-q)/2.0)
    policy = list(result.p_softmax(list(gs.policy_indices())))
    if not (len(policy) == 20 and abs(sum(policy)-1.0) < 1e-4 and abs(sum(vals)-1.0) < 1e-4 and all(math.isfinite(v) for v in vals)):
        raise RuntimeError(f'Inferencia no valida para {name}')
    wdl[name] = vals
    print(f'{name}: WDL={tuple(round(v,7) for v in vals)}, jugadas={len(policy)}')
if max(abs(a-b) for a,b in zip(wdl['eigen'], wdl['onnx-dml'])) > 0.005:
    raise RuntimeError('Desviacion inesperada de WDL entre CPU y GPU')
print('OK: Eigen y ONNX-DML funcionan en el mismo Python operativo.')
'@ | & $Python -
    if ($LASTEXITCODE -ne 0) { throw 'Fallo la prueba de inferencia mixta en ufasta.' }
} finally {
    if ($null -eq $oldWeights) { Remove-Item Env:\SARGON_LC0_TEST_WEIGHTS -ErrorAction SilentlyContinue }
    else { $env:SARGON_LC0_TEST_WEIGHTS = $oldWeights }
}
Write-Host 'INSTALACION OPERATIVA LC0 CPU/GPU VALIDADA. Ahora puede reintentar MATCH.'
