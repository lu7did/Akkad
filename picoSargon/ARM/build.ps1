# picoSargon - compilacion local Windows. Sin cambios permanentes al sistema.
# Uso: .\build.ps1                   (Pico 2 W, STEROIDS=ON, TWINS=ON)
#      .\build.ps1 -Board pico_w      (Pico W)
#      .\build.ps1 -help / --help     (ayuda sin compilar)
param(
    [ValidateSet('pico_w','pico2_w')]
    [string]$Board = 'pico2_w',
    [bool]$steroids = $true,
    [bool]$twins = $true,
    [Alias('h','-help')]
    [switch]$help
)

# Reconocer -help y --help antes de verificar herramientas o modificar archivos.
# En PowerShell, --help se procesa como una forma de switch de ayuda.
if ($help -or ($args -contains '--help')) {
    @'
Compilacion picoSargon ARM v0.2.39

Sintaxis:
  .\build.ps1 [-Board pico2_w|pico_w] [-steroids:$true|$false] [-twins:$true|$false]
  .\build.ps1 -help
  .\build.ps1 --help

Argumentos:
  -Board       Placa destino: pico2_w (predeterminado) o pico_w.
  -steroids    Activa o desactiva STEROIDS (predeterminado: true).
  -twins       Activa o desactiva TWINS (predeterminado: true).
  -help        Muestra esta ayuda y termina sin compilar.
  --help       Equivalente a -help.

Ejemplos:
  .\build.ps1
  .\build.ps1 -Board pico_w
  .\build.ps1 -Board pico2_w -twins:$false
  .\build.ps1 -steroids:$false -twins:$false

Artefactos:
  ARM/build-pico2-w-twins/picoSargon.uf2  (configuracion por defecto)
  ARM/build-twins/picoSargon.uf2         (Pico W con TWINS)
'@ | Write-Output
    return
}
$ErrorActionPreference = 'Stop'
$Project = $PSScriptRoot
$CMake = 'C:\Program Files\CMake\bin\cmake.exe'
$Ninja = 'C:\Users\pedro\ufasta\Scripts\ninja.exe'
$Toolchain = 'C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\11.2 2022.02\bin'
$Gcc = Join-Path $Toolchain 'arm-none-eabi-gcc.exe'
$Gxx = Join-Path $Toolchain 'arm-none-eabi-g++.exe'
$Asm = $Gcc
$SdkRoot = 'C:\Users\pedro\.pico-sdk'
$Python = 'C:\Users\pedro\ufasta\Scripts\python.exe'
# Un directorio separado por placa y configuracion, sin sufijos de versiones antiguas.
# Para Pico W con TWINS activo se conserva el nombre solicitado: build-twins.
$BuildName = if ($twins) {
    if ($Board -eq 'pico_w') { 'build-twins' } else { 'build-' + $Board.Replace('_','-') + '-twins' }
} else {
    'build-' + $Board.Replace('_','-') + '-single'
}
$Build = Join-Path $Project $BuildName
$Tools = Join-Path (Split-Path -Parent $Project) 'tools'
$Embed = Join-Path $Tools 'ARM\embed_grumpy.py'
$Weights = Join-Path $Project 'assets\grumpy.bin'
$Header = Join-Path $Project 'include\generated_grumpy.hpp'

foreach ($File in @($CMake,$Ninja,$Gcc,$Gxx,$Python)) {
    if (-not (Test-Path -LiteralPath $File -PathType Leaf)) { throw "No existe: $File" }
}
# La extension Pico puede instalar versiones en .pico-sdk\sdk\X.Y.Z.
$Sdk = $null
if (Test-Path (Join-Path $SdkRoot 'external\pico_sdk_import.cmake')) {
    $Sdk = $SdkRoot
} else {
    $SdkCandidates = @(Get-ChildItem -LiteralPath $SdkRoot -Filter pico_sdk_import.cmake -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.Directory.Name -eq 'external' } |
        ForEach-Object { $_.Directory.Parent.FullName } | Sort-Object -Unique)
    if ($SdkCandidates.Count -eq 1) { $Sdk = $SdkCandidates[0] }
    elseif ($SdkCandidates.Count -gt 1) {
        $Sdk = @($SdkCandidates | Sort-Object { try { [version]([regex]::Match($_,'\d+\.\d+\.\d+').Value) } catch { [version]'0.0.0' } } -Descending)[0]
        Write-Host "Varios SDK disponibles; seleccionado: $Sdk"
    }
}
if (-not $Sdk) { throw "No encontre pico_sdk_import.cmake bajo $SdkRoot. Revisar instalacion de Pico SDK." }
if (-not (Test-Path (Join-Path $Sdk 'CMakeLists.txt'))) { throw "SDK incompleto: $Sdk" }
if (-not (Test-Path (Join-Path $Project 'include\config.h'))) {
    throw 'Falta include\config.h; edita la configuracion antes de compilar.'
}

# Variables locales del proceso: necesarias para que los subprocesos CMake encuentren
# la cadena de herramientas y el SDK. No se edita el PATH del usuario ni del sistema.
$env:PICO_SDK_PATH = $Sdk
$env:PATH = "$Toolchain;$($env:PATH)"

# Herramientas host confirmadas en esta instalacion de Windows.
# No construir pioasm/picotool desde fuentes: eso requeriria C/C++ nativo Windows.
$PioasmDir = 'C:\Users\pedro\.pico-sdk\tools\2.3.1\pioasm'
$PicotoolDir = 'C:\Users\pedro\.pico-sdk\picotool\2.3.1\picotool'
foreach ($Tool in @(@($PioasmDir, 'pioasm.exe'), @($PicotoolDir, 'picotool.exe'))) {
    $Exe = Join-Path $Tool[0] $Tool[1]
    if (-not (Test-Path -LiteralPath $Exe -PathType Leaf)) { throw "Falta herramienta host: $Exe" }
}
# El archivo real es pioasmConfig.cmake (no pioasm-config.cmake).
if (-not (Test-Path -LiteralPath (Join-Path $PioasmDir 'pioasmConfig.cmake'))) {
    throw "Falta pioasmConfig.cmake en: $PioasmDir"
}
# La ubicacion confirmada de picotool contiene picotool.exe; comprobar
# configuracion CMake para evitar una compilacion host accidental.
if (-not (@(Get-ChildItem -LiteralPath $PicotoolDir -Filter '*config.cmake' -File -ErrorAction SilentlyContinue).Count -gt 0 -or
          @(Get-ChildItem -LiteralPath $PicotoolDir -Filter '*Config.cmake' -File -ErrorAction SilentlyContinue).Count -gt 0)) {
    throw "Falta archivo *Config.cmake para picotool en: $PicotoolDir; listar el directorio antes de continuar."
}
Set-Location -LiteralPath $Project
Write-Host "BOARD: $Board / STEROIDS=$steroids / TWINS=$twins"
Write-Host "BUILD DIRECTORY: $Build"
Write-Host "SDK:   $Sdk"
Write-Host "CMAKE: $CMake"
Write-Host "NINJA: $Ninja"
Write-Host "GCC:   $Gcc"
Write-Host "PIOASM: $PioasmDir"
Write-Host "PICOTOOL: $PicotoolDir"

if (-not (Test-Path -LiteralPath $Embed -PathType Leaf)) { throw "Falta utilitario: $Embed" }
if (-not (Test-Path -LiteralPath $Weights -PathType Leaf)) { throw "Faltan pesos: $Weights" }
& $Python $Embed --input $Weights --output $Header
if ($LASTEXITCODE -ne 0) { throw 'Error generando pesos Grumpy' }
if (Test-Path -LiteralPath $Build) {
    Write-Host "Descartando cache y artefactos obsoletos: $Build"
    Remove-Item -LiteralPath $Build -Recurse -Force
}
& $CMake -S $Project -B $Build -G Ninja `
    "-DPICOSARGON_PICO=ON" `
    "-DSTEROIDS=$($steroids.ToString().ToUpperInvariant())" `
    "-DTWINS=$($twins.ToString().ToUpperInvariant())" `
    "-DPICO_BOARD=$Board" `
    "-DPICO_SDK_PATH=$Sdk" `
    "-DCMAKE_MAKE_PROGRAM=$Ninja" `
    "-Dpioasm_DIR=$PioasmDir" `
    "-Dpicotool_DIR=$PicotoolDir" `
    "-DCMAKE_C_COMPILER=$Gcc" `
    "-DCMAKE_CXX_COMPILER=$Gxx" `
    "-DCMAKE_ASM_COMPILER=$Asm" `
    '-DCMAKE_BUILD_TYPE=Release'
if ($LASTEXITCODE -ne 0) { throw 'Fallo la configuracion de CMake' }
# Confirmar los valores efectivos, no solo los argumentos enviados.
$Cache = Join-Path $Build 'CMakeCache.txt'
if (-not (Test-Path -LiteralPath $Cache -PathType Leaf)) { throw "Falta cache CMake: $Cache" }
$CacheText = Get-Content -LiteralPath $Cache
foreach ($Check in @(@('STEROIDS', $steroids), @('TWINS', $twins))) {
    $Name = [string]$Check[0]
    $Expected = if ([bool]$Check[1]) { 'ON' } else { 'OFF' }
    $Match = @($CacheText | Where-Object { $_ -match "^${Name}:BOOL=(ON|OFF|TRUE|FALSE|1|0)$" })
    if ($Match.Count -ne 1) { throw "No se pudo verificar $Name en CMakeCache.txt" }
    $Actual = ($Match[0] -split '=', 2)[1]
    $IsOn = $Actual -in @('ON','TRUE','1')
    if ($IsOn -ne [bool]$Check[1]) { throw "CMake: $Name=$Actual, esperado $Expected" }
    Write-Host "CONFIGURACION VERIFICADA: $Name=$Expected"
}
# Comprobar la placa en la cache para evitar generar un UF2 del dispositivo equivocado.
$BoardMatch = @($CacheText | Where-Object { $_ -match '^PICO_BOARD:STRING=' })
if ($BoardMatch.Count -ne 1 -or ($BoardMatch[0] -split '=', 2)[1] -ne $Board) {
    throw "La placa configurada en CMake no coincide con -Board $Board"
}
Write-Host "PLACA VERIFICADA: $Board"
& $CMake --build $Build --parallel 4
if ($LASTEXITCODE -ne 0) { throw 'Fallo la compilacion' }
$Uf2 = Join-Path $Build 'picoSargon.uf2'
if (-not (Test-Path -LiteralPath $Uf2)) { throw "Compilacion termino pero falta: $Uf2" }
$Uf2Info = Get-Item -LiteralPath $Uf2
if ($Uf2Info.Length -lt 512) { throw "UF2 sospechosamente pequeno: $($Uf2Info.Length) bytes" }
Write-Host "UF2 generado: $Uf2 ($($Uf2Info.Length) bytes)"
Write-Host "IMPORTANTE: cargar este UF2 solamente en una placa $Board. El arrastre de archivos no garantiza la validacion del firmware."
