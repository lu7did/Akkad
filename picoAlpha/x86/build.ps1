param(
    [string]$VcpkgRoot = '',
    [string]$Generator = 'Visual Studio 18 2026',
    [string]$Architecture = 'x64'
)
$ErrorActionPreference = 'Stop'
$Source = $PSScriptRoot
$Build = Join-Path $Source 'build'

if (-not (Get-Command cmake -ErrorAction SilentlyContinue)) {
    throw 'CMake no se encuentra en PATH.'
}
if ([string]::IsNullOrWhiteSpace($VcpkgRoot)) {
    if (-not [string]::IsNullOrWhiteSpace($env:VCPKG_ROOT)) {
        $VcpkgRoot = $env:VCPKG_ROOT
    } elseif (Test-Path -LiteralPath (Join-Path $HOME 'vcpkg/scripts/buildsystems/vcpkg.cmake')) {
        $VcpkgRoot = Join-Path $HOME 'vcpkg'
    }
}
if ([string]::IsNullOrWhiteSpace($VcpkgRoot)) {
    throw 'vcpkg no encontrado. Use .\build.ps1 -VcpkgRoot "C:\ruta\vcpkg" o configure VCPKG_ROOT.'
}
$VcpkgRoot = [System.IO.Path]::GetFullPath($VcpkgRoot)
$toolchain = Join-Path $VcpkgRoot 'scripts/buildsystems/vcpkg.cmake'
if (-not (Test-Path -LiteralPath $toolchain -PathType Leaf)) {
    throw "No existe el toolchain de vcpkg: $toolchain"
}
# Una cache de CMake de otra ubicacion o generador no puede reutilizarse.
$cache = Join-Path $Build 'CMakeCache.txt'
if (Test-Path -LiteralPath $cache) {
    $cached = Get-Content -LiteralPath $cache -ErrorAction Stop
    $homeLine = $cached | Where-Object { $_ -like 'CMAKE_HOME_DIRECTORY:INTERNAL=*' } | Select-Object -First 1
    $cachedHome = if ($homeLine) { ($homeLine -split '=', 2)[1] } else { '' }
    if ($cachedHome -and ([System.IO.Path]::GetFullPath($cachedHome).TrimEnd('\','/') -ine $Source.TrimEnd('\','/'))) {
        throw "La carpeta build contiene una cache de otra ubicacion ($cachedHome). Elimine ./build para regenerarla."
    }
}
$triplet = 'x64-windows'
$cmakeArgs = @('-S', $Source, '-B', $Build, '-G', $Generator, '-A', $Architecture,
    "-DCMAKE_TOOLCHAIN_FILE=$toolchain", "-DVCPKG_TARGET_TRIPLET=$triplet",
    "-DPA_X86_FC1_TILED=ON", "-DCMAKE_BUILD_TYPE=Release")
Write-Host "Origen: $Source"
Write-Host "Compilacion: $Build"
Write-Host "Generador: $Generator / $Architecture"
Write-Host "vcpkg: $VcpkgRoot"
Write-Host "Configuracion predeterminada: INT8=ON, FC1_TILED=ON; picoAlpha32=referencia FP32; carga .pb.gz directa"
& cmake @cmakeArgs
if ($LASTEXITCODE -ne 0) { throw 'Fallo la configuracion de CMake. Verifique Visual Studio C++, zlib y vcpkg.' }
& cmake --build $Build --config Release
if ($LASTEXITCODE -ne 0) { throw 'Fallo la compilacion de picoAlpha.' }
foreach ($name in @('picoAlpha.exe', 'picoAlpha32.exe')) {
    $exe = Join-Path $Build $name
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "Falta el ejecutable: $exe" }
    Write-Host "Generado: $exe"
}
