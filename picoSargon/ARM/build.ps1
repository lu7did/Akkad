# picoSargon - compilacion local Windows. Sin cambios permanentes al sistema.
# Uso: .\build.ps1                   (Pico W)
#      .\build.ps1 -Board pico2_w    (Pico 2 W)
param([ValidateSet('pico_w','pico2_w')][string]$Board = 'pico_w', [bool]$steroids = $true)
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
$Build = Join-Path $Project ('build-' + $Board.Replace('_','-') + '-v025')
$Tools = Join-Path (Split-Path -Parent $Project) 'tools'
$Embed = Join-Path $Tools 'embed_grumpy.py'
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
Write-Host "BOARD: $Board / STEROIDS=$steroids"
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
& $CMake --build $Build --parallel 4
if ($LASTEXITCODE -ne 0) { throw 'Fallo la compilacion' }
$Uf2 = Join-Path $Build 'picoSargon.uf2'
if (-not (Test-Path -LiteralPath $Uf2)) { throw "Compilacion termino pero falta: $Uf2" }
Write-Host "UF2 generado: $Uf2"
