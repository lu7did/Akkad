param(
  [ValidateSet('Release','Debug')][string]$Configuration = 'Release',
  [string]$Generator = '',
  [switch]$Clean,
  [switch]$Help
)
$ErrorActionPreference = 'Stop'
if ($Help) {
  Write-Host 'picoAlpha X86 C++ build.ps1 [-Configuration Release|Debug] [-Generator "Visual Studio 17 2022"|"Ninja"] [-Clean] [-Help]'
  Write-Host 'Requiere CMake y un compilador C++17 disponible. Produce X86/build/picoAlpha.exe en Windows.'
  exit 0
}
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$build = Join-Path $root 'X86\build'
if (!(Get-Command cmake -ErrorAction SilentlyContinue)) { throw 'CMake no disponible en PATH' }
if ($Clean -and (Test-Path $build)) { Remove-Item $build -Recurse -Force }
New-Item -ItemType Directory -Force -Path $build | Out-Null
$configure = @('-S', $root, '-B', $build)
if ($Generator) { $configure += @('-G', $Generator) }
Write-Host "⚙️ picoAlpha C++ v0.1.42 root=$root config=$Configuration"
& cmake @configure
if ($LASTEXITCODE -ne 0) { throw "CMake configure failed ($LASTEXITCODE)" }
& cmake --build $build --config $Configuration --parallel
if ($LASTEXITCODE -ne 0) { throw "CMake build failed ($LASTEXITCODE)" }
$exe = Join-Path $build 'picoAlpha.exe'
if (!(Test-Path $exe)) { $exe = Join-Path $build 'picoAlpha' }
if (!(Test-Path $exe)) { throw "Missing executable in $build" }
Write-Host "✅ Executable: $exe"
