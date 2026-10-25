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
#* sargon_lc0_gpu_verify_v0.6.126.ps1
#* Verifies the LC0 GPU setup for version 0.6.126
#=================================================================================================================*
# Sargon-NNUE LC0 GPU v0.6.126 -- verifies GPU wheel in TEMP venv only.
# No changes to ufasta or the Sargon-NNUE project.
param(
    [string]$BasePython = 'C:\Users\pedro\ufasta\Scripts\python.exe',
    [string]$Workspace = (Join-Path $env:TEMP 'sargon-lc0-onnx-dml'),
    [string]$TestVenv = (Join-Path $env:TEMP 'lc0-gpu-test')
)
$ErrorActionPreference = 'Stop'
$py = Join-Path $TestVenv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $py -PathType Leaf)) {
    if (-not (Test-Path -LiteralPath $BasePython -PathType Leaf)) { throw "No existe Python base: $BasePython" }
    & $BasePython -m venv $TestVenv
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $py -PathType Leaf)) { throw 'No se pudo crear el venv temporal.' }
}
$dist = Join-Path $Workspace 'dist-v126'
$wheel = Get-ChildItem -LiteralPath $dist -Filter '*.whl' -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $wheel) { throw "No hay wheel en $dist" }
Write-Host "Instalando SOLO en entorno temporal: $py"
& $py -m pip install --no-deps --force-reinstall $wheel.FullName
if ($LASTEXITCODE -ne 0) { throw 'Fallo pip en entorno temporal.' }

# Pass workspace path as an environment variable to the child process only.
$env:SARGON_LC0_GPU_TMP = $Workspace
@'
import os, sys
from pathlib import Path
base = Path(os.environ['SARGON_LC0_GPU_TMP'])
paths = [
    Path(sys.prefix) / 'Lib' / 'site-packages' / '.lczero_bindings.mesonpy.libs',
    base / 'ort-1.24.4' / 'runtimes' / 'win-x64' / 'native',
    base / 'directml-1.15.4' / 'bin' / 'x64-win',
]
handles = []
for p in paths:
    if not p.is_dir():
        raise SystemExit(f'ERROR: No existe directorio DLL: {p}')
    handles.append(os.add_dll_directory(str(p)))
from lczero.backends import Backend
backends = Backend.available_backends()
print('BACKENDS LC0:', backends)
if 'onnx-dml' not in backends:
    raise SystemExit('ERROR: onnx-dml sigue sin registrarse en el modulo Python.')
print('OK: onnx-dml registrado en bindings Python temporales.')
print('PENDIENTE: realizar inferencia real y comprobar dispositivo GPU.')
'@ | & $py -
if ($LASTEXITCODE -ne 0) { throw 'Fallo la verificacion GPU.' }
