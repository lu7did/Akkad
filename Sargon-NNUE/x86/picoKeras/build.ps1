param(
  [ValidateSet('Visual Studio 18 2026','Visual Studio 17 2022','Ninja','MinGW Makefiles')]
  [string]$Generator='Visual Studio 18 2026',
  [ValidateSet('Release','Debug')][string]$Configuration='Release',
  [string]$TflmInclude=$env:TFLM_INCLUDE,
  [string]$TflmLibrary=$env:TFLM_LIBRARY,
  [switch]$Clean = $true,
  [switch]$Make
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$build = Join-Path $root 'build'
$tree = Join-Path $root 'third_party/tflm-tree'
$libBuild = Join-Path $root 'third_party/tflm-build'
if ($Clean) {
  Write-Host '[picoKeras] Clean build (default ON)'
  if (Test-Path -LiteralPath $build) { Remove-Item -LiteralPath $build -Recurse -Force }
} else {
  Write-Host '[picoKeras] Incremental build requested (-Clean:$false)'
}
if (-not $TflmInclude -and (Test-Path -LiteralPath (Join-Path $tree 'tensorflow/lite/micro/micro_interpreter.h') -PathType Leaf)) {
  $TflmInclude = $tree
}
if (-not $TflmLibrary -and (Test-Path -LiteralPath $libBuild -PathType Container)) {
  $candidates = @(Get-ChildItem -LiteralPath $libBuild -Recurse -File -ErrorAction Stop | Where-Object { $_.Name -in @('tflm.lib','libtflm.a') })
  if ($Generator -like 'Visual Studio*') { $candidates = @($candidates | Where-Object { $_.Extension -eq '.lib' }) }
  else { $candidates = @($candidates | Where-Object { $_.Extension -eq '.a' }) }
  $preferred = @($candidates | Where-Object { $_.FullName -like "*\$Configuration\*" })
  if ($preferred.Count -gt 0) { $TflmLibrary = $preferred[0].FullName }
  elseif ($candidates.Count -gt 0) { $TflmLibrary = $candidates[0].FullName }
}
if (-not $TflmInclude -or -not (Test-Path -LiteralPath (Join-Path $TflmInclude 'tensorflow/lite/micro/micro_interpreter.h') -PathType Leaf)) {
  throw 'Faltan encabezados TFLM. Ejecute scripts/install_TFLM.ps1 por separado o especifique -TflmInclude.'
}
if (-not $TflmLibrary -or -not (Test-Path -LiteralPath $TflmLibrary -PathType Leaf)) {
  throw 'Falta la biblioteca TFLM. Ejecute scripts/install_TFLM.ps1 por separado o especifique -TflmLibrary.'
}
Write-Host "[picoKeras] Build C++ v0.1.19 | $Generator | $Configuration"
Write-Host "[picoKeras] Include: $TflmInclude"
Write-Host "[picoKeras] Library: $TflmLibrary"
$cmakeArgs = @('-S',$root,'-B',$build,'-G',$Generator,"-DTFLM_INCLUDE=$TflmInclude","-DTFLM_LIBRARY=$TflmLibrary")
if ($Generator -like 'Visual Studio*') { $cmakeArgs += @('-A','x64') }
else { $cmakeArgs += "-DCMAKE_BUILD_TYPE=$Configuration" }
& cmake @cmakeArgs
if ($LASTEXITCODE -ne 0) { throw 'Fallo la configuracion CMake de picoKeras.' }
& cmake --build $build --config $Configuration --parallel
if ($LASTEXITCODE -ne 0) { throw 'Fallo la compilacion C++ de picoKeras.' }
Write-Host '[picoKeras] Compilacion completada.'
