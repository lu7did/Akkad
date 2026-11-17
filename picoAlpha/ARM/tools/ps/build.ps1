param([switch]$Help,[switch]$Clean)
$ErrorActionPreference = 'Stop'
if($Help){ Write-Host 'picoAlpha ARM Pico 2W firmware: .\build.ps1 [-Clean] [-Help]'; exit 0 }
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$build = Join-Path $root 'build-pico2_w'
if($Clean -and (Test-Path $build)){Remove-Item -Recurse -Force $build}
if(-not $env:PICO_SDK_PATH){throw 'PICO_SDK_PATH required: point to installed Pico SDK'}
cmake -S $root -B $build -G Ninja -DPICO_BOARD=pico2_w -DCMAKE_BUILD_TYPE=Release
if($LASTEXITCODE -ne 0){throw 'CMake configuration failed'}
cmake --build $build -j 4
if($LASTEXITCODE -ne 0){throw 'CMake build failed'}
Write-Host "Firmware: $build/picoAlphaARM.uf2"
