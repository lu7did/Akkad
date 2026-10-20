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
#* sargon_lc0_gpu_rebuild_v0.6.126.ps1
#* Rebuilds the LC0 GPU setup for version 0.6.126
#=================================================================================================================*
# Sargon-NNUE LC0 GPU v0.6.126
# Minimal confirmed build fix: link the already-built ONNX backend objects into Python bindings.
# Does NOT modify Sargon-NNUE or install anything in ufasta.
param(
    [string]$Python = 'C:\Users\pedro\ufasta\Scripts\python.exe',
    [string]$Source = (Join-Path $env:TEMP 'lc0-bindings-dab9898'),
    [string]$Workspace = (Join-Path $env:TEMP 'sargon-lc0-onnx-dml')
)
$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw "No existe Python: $Python" }
$meson = Join-Path $Source 'meson.build'
if (-not (Test-Path -LiteralPath $meson -PathType Leaf)) { throw "No existe el codigo LC0: $meson" }

$native = Join-Path $Workspace 'ort-1.24.4\runtimes\win-x64\native'
$include = Join-Path $Workspace 'ort-1.24.4\build\native\include'
$dml = Join-Path $Workspace 'directml-1.15.4\bin\x64-win\DirectML.dll'
foreach ($path in @((Join-Path $native 'onnxruntime.lib'), (Join-Path $native 'onnxruntime.dll'), (Join-Path $include 'onnxruntime_cxx_api.h'), (Join-Path $include 'dml_provider_factory.h'), $dml)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Falta componente ONNX/DirectML: $path" }
}

# The revision dab9898 includes 'objects: backend_objects' for lc0.exe,
# but NOT for the Python extension. Insert the same objects there, once only.
$srcText = [System.IO.File]::ReadAllText($meson)
$pattern = "(?m)^(?<indent>[ \t]*)cpp_args: \['-fvisibility=hidden'\],(?<nl>\r?\n)(?<indent2>[ \t]*)subdir: 'lczero',"
if ($srcText.Contains("    objects: backend_objects,") -and $srcText.Contains("    subdir: 'lczero',")) {
    Write-Host 'Parche de enlace para Python ya presente; no se modifica meson.build.'
} else {
    $m = [regex]::Match($srcText, $pattern)
    if (-not $m.Success) { throw "No se encontro la ubicacion esperada de python.extension_module en meson.build. No se aplico el parche." }
    $target = $m.Value
    $nl = $m.Groups['nl'].Value
    $fixed = $m.Groups['indent'].Value + "cpp_args: ['-fvisibility=hidden']," + $nl + $m.Groups['indent2'].Value + 'objects: backend_objects,' + $nl + $m.Groups['indent2'].Value + "subdir: 'lczero',"
    $srcText = $srcText.Replace($target, $fixed)
    [System.IO.File]::WriteAllText($meson, $srcText, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "Meson corregido: $meson"
}

# Always use new build path so stale Meson configuration can't masquerade as a GPU build.
$build = Join-Path $Workspace 'build-onnx-dml-python-v126'
$dist = Join-Path $Workspace 'dist-v126'
New-Item -ItemType Directory -Path $dist -Force | Out-Null
Write-Host 'Construyendo el modulo Python con los objetos ONNX enlazados (NO se modifica ufasta)...'
$args = @(
    '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation', '--no-cache-dir',
    '-Csetup-args=-Dgtest=false',
    '-Csetup-args=-Donnx=true',
    "-Csetup-args=-Donnx_libdir=$native",
    "-Csetup-args=-Donnx_include=$include",
    "-Cbuild-dir=$build",
    '--wheel-dir', $dist, $Source
)
& $Python @args
if ($LASTEXITCODE -ne 0) { throw "Fallo la construccion del wheel (codigo $LASTEXITCODE). ufasta no se modifico." }

$targetsPath = Join-Path $build 'meson-info\intro-targets.json'
if (-not (Test-Path -LiteralPath $targetsPath)) { throw "No se encontro el informe de objetivos Meson: $targetsPath" }
$targets = Get-Content -LiteralPath $targetsPath -Raw | ConvertFrom-Json
$onnxTarget = @($targets | Where-Object { $_.name -eq 'onnx_backend' })
if ($onnxTarget.Count -eq 0) { throw 'ONNX no se compilo: Meson no creo onnx_backend. Revisar onnxruntime en meson-log.txt.' }

$dmlConf = Join-Path $build 'onnx_conf.h'
if (-not (Test-Path -LiteralPath $dmlConf -PathType Leaf)) { throw 'Falta onnx_conf.h: ONNX no se configuro correctamente.' }
if (-not (Select-String -LiteralPath $dmlConf -Pattern '^#define USE_DML(?:\s|$)' -Quiet)) {
    throw 'El backend ONNX se compilo sin USE_DML: el paquete instalado no registrara onnx-dml.'
}

$wheel = Get-ChildItem -LiteralPath $dist -Filter '*.whl' -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $wheel) { throw 'No se creo el wheel.' }
Write-Host 'VERIFICACION ESTATICA OK: onnx_backend existe y USE_DML esta habilitado.'
Write-Host "Wheel v0.6.126: $($wheel.FullName)"
Write-Host 'Aun NO instalado. Utilizar sargon_lc0_gpu_verify_v0.6.126.ps1 para verificarlo de forma aislada.'
