param(
    [string]$VcpkgRoot = $env:VCPKG_ROOT,
    [string]$Generator = 'Visual Studio 18 2026',
    [string]$Architecture = 'x64'
)
$ErrorActionPreference = 'Stop'
$Source = Split-Path -Parent $MyInvocation.MyCommand.Path
$Build = Join-Path $Source 'build_windows'

if (-not (Get-Command cmake -ErrorAction SilentlyContinue)) {
    throw 'CMake no se encuentra en PATH. Instale CMake y abra una terminal nueva.'
}

$cmakeArgs = @('-S', $Source, '-B', $Build, '-G', $Generator, '-A', $Architecture)
if (-not [string]::IsNullOrWhiteSpace($VcpkgRoot)) {
    $toolchain = Join-Path $VcpkgRoot 'scripts/buildsystems/vcpkg.cmake'
    if (-not (Test-Path -LiteralPath $toolchain)) {
        throw "No existe el toolchain vcpkg: $toolchain"
    }
    $cmakeArgs += "-DCMAKE_TOOLCHAIN_FILE=$toolchain"
    $cmakeArgs += '-DVCPKG_TARGET_TRIPLET=x64-windows'
}

Write-Host "CMake generator: $Generator / $Architecture"
Write-Host "vcpkg: $(if ($VcpkgRoot) { $VcpkgRoot } else { 'no configurado' })"
& cmake @cmakeArgs
if ($LASTEXITCODE -ne 0) {
    throw @'
CMake configure fallo. Revise el primer error real mostrado arriba.
- Si aparece "Could NOT find ZLIB": instale zlib:x64-windows mediante vcpkg y pase -VcpkgRoot.
- Si aparece "Could not create named generator": revise la version de Visual Studio instalada.
- Si aparece un error de compilador: compruebe que Visual Studio tiene el workload Desktop development with C++.
No es necesario Ninja con el generador Visual Studio.
'@
}
& cmake --build $Build --config Release
if ($LASTEXITCODE -ne 0) { throw 'Fallo de compilacion C++ (revise los errores anteriores).' }
$exe = Join-Path $Build 'Release/tinyAlpha.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw "Compilacion finalizada pero no se encontro: $exe" }
$int8 = Join-Path $Build 'Release/tinyAlphaInt8.exe'
if (-not (Test-Path -LiteralPath $int8)) { throw "Compilacion finalizada pero no se encontro: $int8" }
Write-Host "Executable INT8: $int8"
Write-Host "Executable: $exe"
