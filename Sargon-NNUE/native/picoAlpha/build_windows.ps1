param(
    [string]$VcpkgRoot = '',
    [string]$Generator = 'Visual Studio 18 2026',
    [string]$Architecture = 'x64'
)
$ErrorActionPreference = 'Stop'
$Source = $PSScriptRoot
$Build = Join-Path $Source 'build_windows'

if (-not (Get-Command cmake -ErrorAction SilentlyContinue)) {
    throw 'CMake no se encuentra en PATH. Instale CMake y reinicie la terminal integrada de VS Code.'
}

# Prioridad: argumento explicito, variable de entorno, instalacion local habitual.
# Nunca depender del directorio actual desde el cual VS Code lance el script.
if ([string]::IsNullOrWhiteSpace($VcpkgRoot)) {
    if (-not [string]::IsNullOrWhiteSpace($env:VCPKG_ROOT)) {
        $VcpkgRoot = $env:VCPKG_ROOT
    } elseif (Test-Path -LiteralPath (Join-Path $HOME 'vcpkg/scripts/buildsystems/vcpkg.cmake')) {
        $VcpkgRoot = Join-Path $HOME 'vcpkg'
    }
}
if ([string]::IsNullOrWhiteSpace($VcpkgRoot)) {
    throw 'vcpkg no encontrado. Use .\build_windows.ps1 -VcpkgRoot "C:\Users\pedro\vcpkg" o configure VCPKG_ROOT.'
}
$VcpkgRoot = [System.IO.Path]::GetFullPath($VcpkgRoot)
$toolchain = Join-Path $VcpkgRoot 'scripts/buildsystems/vcpkg.cmake'
if (-not (Test-Path -LiteralPath $toolchain -PathType Leaf)) {
    throw "No existe el toolchain de vcpkg: $toolchain"
}
$cmakeArgs = @('-S', $Source, '-B', $Build, '-G', $Generator, '-A', $Architecture,
    "-DCMAKE_TOOLCHAIN_FILE=$toolchain", '-DVCPKG_TARGET_TRIPLET=x64-windows')
Write-Host "Origen: $Source"
Write-Host "Generador: $Generator / $Architecture"
Write-Host "vcpkg: $VcpkgRoot"
& cmake @cmakeArgs
if ($LASTEXITCODE -ne 0) {
    throw 'Fallo al configurar CMake. Compruebe generador de Visual Studio, componentes C++ y zlib:x64-windows en vcpkg.'
}
& cmake --build $Build --config Release
if ($LASTEXITCODE -ne 0) { throw 'Fallo la compilacion C++ (vea el primer error anterior).' }
$exe = Join-Path $Build 'Release/picoAlpha.exe'
$fp32 = Join-Path $Build 'Release/picoAlpha32.exe'
$legacy = @(
    (Join-Path $Build 'Release/picoAlphaFP32.exe'),
    (Join-Path $Build 'Release/picoAlphaInt8.exe')
)
foreach ($path in @($exe, $fp32)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Compilacion terminada, pero falta el ejecutable: $path"
    }
}
Write-Host "Ejecutable INT8 (predeterminado): $exe"
Write-Host "Ejecutable FP32 (referencia): $fp32"

foreach ($old in $legacy) {
    if (Test-Path -LiteralPath $old -PathType Leaf) {
        Remove-Item -LiteralPath $old -Force
        Write-Host "Eliminado binario legado: $old"
    }
}
