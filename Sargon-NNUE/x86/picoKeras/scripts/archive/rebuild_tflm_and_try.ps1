param(
  [string]$Network = '.\small.mul.int8.tflite',
  [ValidateSet('Release','Debug')][string]$Configuration = 'Release',
  [switch]$NoRun
)
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$libBuild = Join-Path $project 'third_party/tflm-build'
$libTree = Join-Path $project 'third_party/tflm-tree'
$appBuild = Join-Path $project 'build'
$patched = Join-Path $libTree 'tensorflow/lite/micro/kernels/gather.cc'
if (!(Test-Path $patched)) { throw "Falta gather.cc: $patched" }
$gatherText = [IO.File]::ReadAllText($patched)
if ($gatherText -notmatch 'case kTfLiteInt32:\s*return Gather<int32_t, int32_t>') {
  throw 'El gather.cc de TFLM no contiene el soporte INT32 del parche v0.1.38. Aplicar ese parche primero.'
}
if (!(Test-Path (Join-Path $libBuild 'CMakeCache.txt'))) {
  throw "No existe configuracion CMake de la biblioteca TFLM: $libBuild"
}
if (!(Test-Path (Join-Path $appBuild 'CMakeCache.txt'))) {
  throw "No existe configuracion CMake del ejecutable: $appBuild"
}
$cache = [IO.File]::ReadAllText((Join-Path $libBuild 'CMakeCache.txt'))
$homeMatch = [regex]::Match($cache, '(?m)^CMAKE_HOME_DIRECTORY:INTERNAL=(.+)\r?$')
if (-not $homeMatch.Success) { throw 'No se pudo verificar el proyecto de origen de TFLM en CMakeCache.txt' }
$tflmSourceRoot = $homeMatch.Groups[1].Value.Trim().Replace('/','\').TrimEnd('\')
$expectedHome = (Resolve-Path $libTree).Path.TrimEnd('\')
if ($tflmSourceRoot -ine $expectedHome) {
  throw "TFLM CMake cache apunta a $tflmSourceRoot; se esperaba $expectedHome. Reconfigurar TFLM antes de continuar."
}
Write-Host '[picoKeras v0.1.40] Reconstruyendo biblioteca TFLM para incorporar GATHER INT32...' -ForegroundColor Cyan
& cmake --build $libBuild --config $Configuration --target tflm --parallel
if ($LASTEXITCODE -ne 0) { throw "Fallo compilacion de tflm.lib (exit $LASTEXITCODE)" }
$libs = @(Get-ChildItem $libBuild -Recurse -File -Filter 'tflm.lib' | Where-Object { $_.FullName -match ('[\\/]'+$Configuration+'[\\/]') } | Sort-Object LastWriteTimeUtc -Descending)
if ($libs.Count -eq 0) { throw 'Compilacion terminada, pero no se encontro tflm.lib de la configuracion elegida.' }
$lib = $libs[0]
$after = Get-Item $lib.FullName
Write-Host "TFLM reconstruida: $($after.FullName) ($($after.LastWriteTime))"
# Comprobar que picoKeras enlaza la biblioteca que acaba de compilarse.
$appCache = [IO.File]::ReadAllText((Join-Path $appBuild 'CMakeCache.txt'))
$linked = [regex]::Match($appCache, '(?m)^TFLM_LIBRARY:FILEPATH=(.+)\r?$')
if (-not $linked.Success) { throw 'No se encontro TFLM_LIBRARY en el cache del ejecutable.' }
$linkedPath = $linked.Groups[1].Value.Trim().Replace('/','\')
if ([IO.Path]::GetFullPath($linkedPath) -ine [IO.Path]::GetFullPath($after.FullName)) {
  throw "picoKeras enlaza otra biblioteca: $linkedPath. Biblioteca reconstruida: $($after.FullName)"
}
Write-Host '[picoKeras v0.1.40] Enlazando picoKeras.exe con la biblioteca actualizada...' -ForegroundColor Cyan
& cmake --build $appBuild --config $Configuration --target picoKeras --parallel
if ($LASTEXITCODE -ne 0) { throw "Fallo compilacion de picoKeras.exe (exit $LASTEXITCODE)" }
$exe = Join-Path $appBuild "$Configuration/picoKeras.exe"
if (!(Test-Path $exe)) { throw "No se genero el ejecutable: $exe" }
if ($NoRun) { Write-Host "Compilacion OK: $exe"; exit 0 }
$networkFile = (Resolve-Path $Network -ErrorAction Stop).Path
Write-Host '[picoKeras v0.1.40] Probando inicializacion real de TFLM...' -ForegroundColor Cyan
# No redirigir stderr a stdout en PowerShell: evita transformar banners en NativeCommandError.
@('uci','isready','position startpos','go depth 1') | & $exe --network $networkFile --stdio
if ($LASTEXITCODE -ne 0) { throw "picoKeras termino con error (exit $LASTEXITCODE)" }
