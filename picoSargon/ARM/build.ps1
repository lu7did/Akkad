
# picoSargon ARM - Windows PowerShell
# Salida unica: picoSargon/ARM/build/picoSargon.uf2

[CmdletBinding()]
param(
    [ValidateSet('pico2_w', 'pico_w')]
    [string]$Board = 'pico2_w',

    [bool]$Steroids = $true,
    [bool]$Twins = $true,

    [ValidateRange(1,128)]
    [int]$Jobs = 4,

    [switch]$Clean,
    [switch]$Help
)

$ErrorActionPreference = 'Stop'

if ($Help) {
    @'
picoSargon ARM - Build para Windows

Uso:
  .\build.ps1
  .\build.ps1 -Board pico_w
  .\build.ps1 -Steroids:$false
  .\build.ps1 -Twins:$false
  .\build.ps1 -Clean
  .\build.ps1 -Jobs 8

Defaults:
  BOARD=pico2_w
  STEROIDS=ON
  TWINS=ON
  JOBS=4
  BUILD=ARM/build
  OUTPUT=ARM/build/picoSargon.uf2
'@
    return
}

$Arm = $PSScriptRoot
$Root = Split-Path -Parent $Arm
$Build = Join-Path $Arm 'build'

$Embed = Join-Path $Root 'tools\ARM\embed_grumpy.py'
$Weights = Join-Path $Arm 'assets\grumpy.bin'
$Header = Join-Path $Arm 'include\generated_grumpy.hpp'
$Config = Join-Path $Arm 'include\config.h'

foreach ($file in @(
    (Join-Path $Arm 'CMakeLists.txt'),
    $Embed, $Weights, $Config
)) {
    if (!(Test-Path $file -PathType Leaf)) {
        throw "Falta archivo requerido: $file"
    }
}

function Find-Executable {
    param(
        [string]$Name,
        [string[]]$Candidates = @()
    )

    $cmd = Get-Command $Name -ErrorAction SilentlyContinue |
           Select-Object -First 1

    if ($cmd -and $cmd.Source -and
        (Test-Path $cmd.Source -PathType Leaf)) {
        return $cmd.Source
    }

    foreach ($path in $Candidates) {
        if ($path -and (Test-Path $path -PathType Leaf)) {
            return $path
        }
    }

    return $null
}

# --------------------------------------------------
# 1. Herramientas de compilacion
# --------------------------------------------------

$CMake = Find-Executable 'cmake.exe' @(
    'C:\Program Files\CMake\bin\cmake.exe'
)

$Python = Find-Executable 'python.exe' @(
    (Join-Path $env:USERPROFILE 'ufasta\Scripts\python.exe')
)

$Ninja = Find-Executable 'ninja.exe' @(
    (Join-Path $env:USERPROFILE 'ufasta\Scripts\ninja.exe')
)

if (!$CMake) {
    throw 'Falta CMake. Instalar: winget install Kitware.CMake'
}

if (!$Python) {
    throw 'Falta Python 3. Instalarlo y agregarlo al PATH.'
}

if (!$Ninja) {
    Write-Host 'Instalando Ninja...' -ForegroundColor Yellow

    & $Python -m pip install ninja

    if ($LASTEXITCODE -ne 0) {
        throw 'No se pudo instalar Ninja.'
    }

    $Ninja = & $Python -c @'
import ninja
from pathlib import Path
print(Path(ninja.__file__).parent / "data" / "bin" / "ninja.exe")
'@

    $Ninja = ($Ninja | Select-Object -First 1)

    if (!(Test-Path $Ninja -PathType Leaf)) {
        throw 'No se encontro ninja.exe despues de instalarlo.'
    }
}

# --------------------------------------------------
# 2. Raspberry Pi Pico SDK
# --------------------------------------------------

$SdkRoot = Join-Path $env:USERPROFILE '.pico-sdk'

$Candidates = @()

if ($env:PICO_SDK_PATH) {
    $Candidates += $env:PICO_SDK_PATH
}

$SdkFolder = Join-Path $SdkRoot 'sdk'

if (Test-Path $SdkFolder) {
    $Candidates += @(
        Get-ChildItem $SdkFolder -Directory |
        Sort-Object {
            try { [version]$_.Name }
            catch { [version]'0.0.0' }
        } -Descending |
        ForEach-Object { $_.FullName }
    )
}

$Candidates += @(
    $SdkRoot,
    (Join-Path $env:USERPROFILE 'pico\pico-sdk')
)

$Sdk = $null

foreach ($candidate in $Candidates) {
    if (
        (Test-Path (Join-Path $candidate 'CMakeLists.txt')) -and
        (Test-Path (Join-Path $candidate 'external\pico_sdk_import.cmake'))
    ) {
        $Sdk = $candidate
        break
    }
}

if (!$Sdk) {
    $Git = Find-Executable 'git.exe' @(
        'C:\Program Files\Git\cmd\git.exe'
    )

    if (!$Git) {
        throw 'Falta Git para descargar Pico SDK.'
    }

    $Sdk = Join-Path $SdkFolder '2.3.1'

    if (!(Test-Path $Sdk)) {
        New-Item -ItemType Directory -Force `
            -Path $SdkFolder | Out-Null

        & $Git clone --depth 1 --branch 2.3.1 `
            --recurse-submodules `
            https://github.com/raspberrypi/pico-sdk.git `
            $Sdk

        if ($LASTEXITCODE -ne 0) {
            throw 'Fallo la descarga de Pico SDK 2.3.1.'
        }
    }

    if (!(Test-Path (Join-Path $Sdk 'CMakeLists.txt'))) {
        throw "SDK incompleto: $Sdk"
    }
}

$env:PICO_SDK_PATH = $Sdk

# --------------------------------------------------
# 3. ARM GNU Toolchain
# --------------------------------------------------

$GccCandidates = @(
    'C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\11.2 2022.02\bin\arm-none-eabi-gcc.exe'
)

if ($env:PICO_TOOLCHAIN_PATH) {
    $GccCandidates = @(
        (Join-Path $env:PICO_TOOLCHAIN_PATH 'bin\arm-none-eabi-gcc.exe')
    ) + $GccCandidates
}

$Gcc = Find-Executable 'arm-none-eabi-gcc.exe' $GccCandidates

if (!$Gcc) {
    foreach ($folder in @(
        'C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi',
        'C:\Program Files\Arm GNU Toolchain arm-none-eabi',
        (Join-Path $SdkRoot 'toolchain')
    )) {
        if (Test-Path $folder) {
            $found = Get-ChildItem $folder -Recurse `
                -Filter arm-none-eabi-gcc.exe `
                -File -ErrorAction SilentlyContinue |
                Select-Object -First 1

            if ($found) {
                $Gcc = $found.FullName
                break
            }
        }
    }
}

if (!$Gcc) {
    throw 'Falta ARM GNU Toolchain: arm-none-eabi-gcc.'
}

$ToolchainBin = Split-Path -Parent $Gcc
$Gxx = Join-Path $ToolchainBin 'arm-none-eabi-g++.exe'

if (!(Test-Path $Gxx)) {
    throw "Falta compilador ARM C++: $Gxx"
}

$env:PATH = "$ToolchainBin;$env:PATH"
$env:PICO_TOOLCHAIN_PATH = Split-Path -Parent $ToolchainBin

# --------------------------------------------------
# 4. Herramientas host Pico SDK
# --------------------------------------------------

$PioasmDir = $null
$PicotoolDir = $null

foreach ($folder in @(
    (Join-Path $SdkRoot 'tools'),
    (Join-Path $SdkRoot 'picotool')
)) {
    if (!(Test-Path $folder)) {
        continue
    }

    if (!$PioasmDir) {
        $item = Get-ChildItem $folder -Recurse `
            -Filter pioasmConfig.cmake `
            -File -ErrorAction SilentlyContinue |
            Select-Object -First 1

        if ($item) {
            $PioasmDir = $item.Directory.FullName
        }
    }

    if (!$PicotoolDir) {
        $item = Get-ChildItem $folder -Recurse `
            -Filter picotoolConfig.cmake `
            -File -ErrorAction SilentlyContinue |
            Select-Object -First 1

        if ($item) {
            $PicotoolDir = $item.Directory.FullName
        }
    }
}

# --------------------------------------------------
# 5. Generacion de la red Grumpy en FLASH
# --------------------------------------------------

Write-Host '⚙️ picoSargon ARM' -ForegroundColor Cyan
Write-Host "BOARD=$Board STEROIDS=$Steroids TWINS=$Twins"
Write-Host "SDK=$Sdk"
Write-Host "GCC=$Gcc"
Write-Host "BUILD=$Build"

& $Python $Embed --input $Weights --output $Header

if ($LASTEXITCODE -ne 0) {
    throw 'Fallo la generacion de generated_grumpy.hpp.'
}

# --------------------------------------------------
# 6. Construccion CMake
# --------------------------------------------------

if ($Clean -and (Test-Path $Build)) {
    Remove-Item $Build -Recurse -Force
}

if (!(Test-Path $Build)) {
    New-Item -ItemType Directory -Path $Build | Out-Null
}

$SteroidsFlag = if ($Steroids) { 'ON' } else { 'OFF' }
$TwinsFlag = if ($Twins) { 'ON' } else { 'OFF' }

$CMakeArgs = @(
    '-S', $Arm,
    '-B', $Build,
    '-G', 'Ninja',
    '-DPICOSARGON_PICO=ON',
    "-DPICO_BOARD=$Board",
    "-DSTEROIDS=$SteroidsFlag",
    "-DTWINS=$TwinsFlag",
    "-DPICO_SDK_PATH=$Sdk",
    "-DCMAKE_MAKE_PROGRAM=$Ninja",
    "-DCMAKE_C_COMPILER=$Gcc",
    "-DCMAKE_CXX_COMPILER=$Gxx",
    "-DCMAKE_ASM_COMPILER=$Gcc",
    '-DCMAKE_BUILD_TYPE=Release'
)

if ($PioasmDir) {
    $CMakeArgs += "-Dpioasm_DIR=$PioasmDir"
}

if ($PicotoolDir) {
    $CMakeArgs += "-Dpicotool_DIR=$PicotoolDir"
}

& $CMake @CMakeArgs

if ($LASTEXITCODE -ne 0) {
    throw 'Fallo la configuracion CMake.'
}

& $CMake --build $Build --parallel $Jobs

if ($LASTEXITCODE -ne 0) {
    throw 'Fallo la compilacion ARM.'
}

# --------------------------------------------------
# 7. Verificacion del firmware producido
# --------------------------------------------------

$UF2 = Join-Path $Build 'picoSargon.uf2'

if (!(Test-Path $UF2 -PathType Leaf)) {
    throw "No se genero el firmware esperado: $UF2"
}

$Size = (Get-Item $UF2).Length

if ($Size -lt 512) {
    throw "Archivo UF2 sospechosamente pequeno: $Size bytes"
}

Write-Host ''
Write-Host '✅ Compilacion finalizada' -ForegroundColor Green
Write-Host "BOARD=$Board STEROIDS=$SteroidsFlag TWINS=$TwinsFlag"
Write-Host "UF2=$UF2"
Write-Host "SIZE=$Size bytes"

