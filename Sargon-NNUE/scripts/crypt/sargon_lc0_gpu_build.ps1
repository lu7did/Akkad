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
#* sargon_lc0_gpu_build.ps1
#* Builds the LC0 GPU execution environment
#=================================================================================================================*
# Sargon-NNUE GPU experiment v0.6.125
# Builds a new lczero-bindings wheel with ONNX-DML enabled, WITHOUT installing it.
# Uses the user's patched LC0 checkout. Does not modify Sargon-NNUE or ufasta.
param(
    [string]$Python = 'C:\Users\pedro\ufasta\Scripts\python.exe',
    [string]$Source = (Join-Path $env:TEMP 'lc0-bindings-dab9898'),
    [string]$Workspace = (Join-Path $env:TEMP 'sargon-lc0-onnx-dml'),
    [string]$OrtVersion = '1.24.4',
    [string]$DmlVersion = '1.15.4'
)
$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw "No existe Python: $Python" }
if (-not (Test-Path -LiteralPath "$Source\meson.build" -PathType Leaf)) { throw "No existe el checkout LC0: $Source" }
$chessSource = Join-Path $Source 'src\python\python_chess.cc'
if (-not (Test-Path -LiteralPath $chessSource -PathType Leaf)) { throw "No existe $chessSource" }
if (Select-String -LiteralPath $chessSource -Pattern 'py::object board_copy' -Quiet) {
    throw 'Falta la correccion confirmada py::object -> pybind11::object en python_chess.cc. No se modifica automaticamente.'
}
$project = Join-Path $Source 'pyproject.toml'
if (-not (Select-String -LiteralPath $project -Pattern '^allow-windows-internal-shared-libs\s*=\s*true\s*$' -Quiet)) {
    throw 'Falta allow-windows-internal-shared-libs = true en pyproject.toml. Se conserva el archivo sin editar.'
}
New-Item -ItemType Directory -Path $Workspace -Force | Out-Null
$ortRoot = Join-Path $Workspace "ort-$OrtVersion"
$dmlRoot = Join-Path $Workspace "directml-$DmlVersion"

if (-not (Test-Path -LiteralPath $ortRoot)) {
    $pkg = Join-Path $Workspace "ort-$OrtVersion.nupkg"
    $zip = Join-Path $Workspace "ort-$OrtVersion.zip"
    $uri = "https://www.nuget.org/api/v2/package/Microsoft.ML.OnnxRuntime.DirectML/$OrtVersion"
    Write-Host "Descargando ONNX Runtime DirectML $OrtVersion desde NuGet ..."
    Invoke-WebRequest -Uri $uri -OutFile $pkg
    Copy-Item -LiteralPath $pkg -Destination $zip
    Expand-Archive -LiteralPath $zip -DestinationPath $ortRoot -Force
}
if (-not (Test-Path -LiteralPath $dmlRoot)) {
    $pkg = Join-Path $Workspace "directml-$DmlVersion.nupkg"
    $zip = Join-Path $Workspace "directml-$DmlVersion.zip"
    $uri = "https://www.nuget.org/api/v2/package/Microsoft.AI.DirectML/$DmlVersion"
    Write-Host "Descargando DirectML $DmlVersion desde NuGet ..."
    Invoke-WebRequest -Uri $uri -OutFile $pkg
    Copy-Item -LiteralPath $pkg -Destination $zip
    Expand-Archive -LiteralPath $zip -DestinationPath $dmlRoot -Force
}

$native = Join-Path $ortRoot 'runtimes\win-x64\native'
$include = Join-Path $ortRoot 'build\native\include'
$lib = Join-Path $native 'onnxruntime.lib'
$dll = Join-Path $native 'onnxruntime.dll'
if (-not (Test-Path -LiteralPath $lib -PathType Leaf)) { throw "El paquete no contiene la LIB requerida: $lib" }
if (-not (Test-Path -LiteralPath $dll -PathType Leaf)) { throw "El paquete no contiene la DLL requerida: $dll" }
if (-not (Test-Path -LiteralPath $include -PathType Container)) { throw "No existe la carpeta de encabezados: $include" }
foreach ($header in @('onnxruntime_cxx_api.h','dml_provider_factory.h')) {
    $match = Get-ChildItem -LiteralPath $include -Recurse -File -Filter $header | Select-Object -First 1
    if (-not $match) { throw "El paquete no contiene $header en $include; no es posible habilitar onnx-dml." }
    Write-Host "Header encontrado: $($match.FullName)"
}
$dmlDll = Get-ChildItem -LiteralPath $dmlRoot -Recurse -File -Filter 'DirectML.dll' |
    Where-Object { $_.FullName -match 'win-x64|x64' } | Select-Object -First 1
if (-not $dmlDll) { throw 'No se encontro DirectML.dll para x64. Revisar el paquete NuGet antes de continuar.' }
Write-Host "ONNX Runtime: $dll"
Write-Host "DirectML: $($dmlDll.FullName)"

# Build a wheel ONLY. The installed Eigen bindings are NOT replaced.
$dist = Join-Path $Workspace 'dist'
$build = Join-Path $Workspace 'build-onnx-dml'
New-Item -ItemType Directory -Path $dist -Force | Out-Null
Write-Host 'Construyendo wheel GPU separado (NO se instala en ufasta) ...'
$args = @(
    '-m','pip','wheel','--no-deps','--no-build-isolation','--no-cache-dir',
    '-Csetup-args=-Dgtest=false',
    '-Csetup-args=-Donnx=true',
    "-Csetup-args=-Donnx_libdir=$native",
    "-Csetup-args=-Donnx_include=$include",
    "-Cbuild-dir=$build",
    '--wheel-dir', $dist, $Source
)
& $Python @args
if ($LASTEXITCODE -ne 0) { throw "Falló la compilacion del wheel ONNX-DML (pip exit=$LASTEXITCODE). No se modificó el entorno instalado." }
$wheels = @(Get-ChildItem -LiteralPath $dist -Filter '*.whl' -File)
if ($wheels.Count -eq 0) { throw "pip termino sin crear archivos .whl en $dist" }
$manifest = Join-Path $Workspace 'GPU_BUILD_PATHS.txt'
@(
    'SARGON-NNUE GPU tools v0.6.125 -- SOLO CANDIDATO, NO INSTALADO',
    "Wheel=$($wheels[0].FullName)",
    "ONNX_DLL=$dll",
    "ONNX_LIB=$lib",
    "DIRECTML_DLL=$($dmlDll.FullName)",
    "ORT_VERSION=$OrtVersion",
    "DML_VERSION=$DmlVersion",
    'ATENCION: Al instalar el wheel sera necesario hacer disponibles sus DLL nativas en Windows.',
    'ATENCION: no basta con compilar: hay que verificar Backend.available_backends() y una inferencia ONNX-DML real.'
) | Set-Content -LiteralPath $manifest -Encoding UTF8
Write-Host "Wheel: $($wheels[0].FullName)"
Write-Host "Manifiesto: $manifest"
Write-Host 'EIGEN instalado: NO MODIFICADO. Enviar la salida y el manifiesto antes de instalar.'
