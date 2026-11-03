# picoKeras RP2350: firmware nativo, sin TensorFlow de escritorio.
[CmdletBinding()]
param(
    [string]$Model,
    [string]$PicoSdkPath=$env:PICO_SDK_PATH,
    [string]$TflmInclude=$env:TFLM_INCLUDE,
    [string]$TflmLibrary=$env:TFLM_LIBRARY,
    [string]$WifiSsid='',
    [string]$WifiPassword='',
    [ValidateRange(8192,262144)][int]$ArenaBytes=98304,
    [ValidateRange(1,65535)][int]$Port=6110,
    [switch]$Clean,
    [switch]$Help
)
$ErrorActionPreference='Stop'
if ($Help -or $args -contains '--help') {
@'
picoKeras ARM v0.1.20 — Raspberry Pi Pico 2 W (RP2350)
  .\build.ps1 -Model C:\models\small-int8.tflite [-WifiSsid SSID -WifiPassword CLAVE]
              [-PicoSdkPath RUTA] [-TflmInclude RUTA] [-TflmLibrary ARCHIVO.a]
              [-ArenaBytes 98304] [-Port 6110] [-Clean] [-Help]
  USB serial UCI siempre activo; TCP/UCI 6110 opcional cuando se especifica SSID.
  Si falta libtensorflow-microlite.a se intenta compilar con GNU make y arm-none-eabi.
  No utiliza Visual Studio, TensorFlow C SDK ni .lib de Windows.
  Resultado: build-pico2-w/picoKeras.uf2
'@ | Write-Output
 return
}
if ([string]::IsNullOrWhiteSpace($Model)) { throw 'Obligatorio: -Model <archivo INT8 .tflite>. Ejecute -Help.' }
$root=$PSScriptRoot
$Model=(Resolve-Path -LiteralPath $Model -ErrorAction Stop).Path
if ([string]::IsNullOrWhiteSpace($TflmInclude)) { $TflmInclude=Join-Path $root 'third_party\tflm-tree' }
if (-not (Test-Path (Join-Path $TflmInclude 'tensorflow\lite\micro\micro_interpreter.h'))) {
 throw "Falta el arbol TFLM en $TflmInclude; instale tensorflow/tflite-micro en third_party/tflm-tree."
}
if ([string]::IsNullOrWhiteSpace($PicoSdkPath)) {
  $sdkBase=Join-Path $HOME '.pico-sdk\sdk'
  $sdkCandidates=@(Get-ChildItem -LiteralPath $sdkBase -Filter pico_sdk_import.cmake -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Directory.Name -eq 'external' } | ForEach-Object { $_.Directory.Parent.FullName } | Sort-Object -Descending)
  if($sdkCandidates.Count -gt 0){$PicoSdkPath=$sdkCandidates[0]}
}
if (-not $PicoSdkPath -or -not (Test-Path (Join-Path $PicoSdkPath 'external\pico_sdk_import.cmake'))) {
 throw 'Pico SDK 2.x no encontrado. Indique -PicoSdkPath o variable PICO_SDK_PATH.'
}
function Resolve-Executable([string]$name,[string[]]$paths) {
 foreach($p in $paths){if($p -and (Test-Path -LiteralPath $p -PathType Leaf)){return (Resolve-Path -LiteralPath $p).Path}}
 $cmd=Get-Command $name -ErrorAction SilentlyContinue
 if($cmd){return $cmd.Source}
 throw "No se encuentra $name. Indique su ruta mediante PATH."
}
$cmake=Resolve-Executable 'cmake.exe' @('C:\Program Files\CMake\bin\cmake.exe')
$ninja=Resolve-Executable 'ninja.exe' @((Join-Path $HOME 'ufasta\Scripts\ninja.exe'))
$python=Resolve-Executable 'python.exe' @((Join-Path $HOME 'ufasta\Scripts\python.exe'))
$gcc=Resolve-Executable 'arm-none-eabi-gcc.exe' @('C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\11.2 2022.02\bin\arm-none-eabi-gcc.exe')
$toolchain=Split-Path -Parent $gcc
$gxx=Join-Path $toolchain 'arm-none-eabi-g++.exe'
if(-not (Test-Path $gxx)){throw "No existe $gxx"}
$env:PATH="$toolchain;$env:PATH"
$env:PICO_SDK_PATH=$PicoSdkPath
# Reutilizar herramientas host Pico SDK instaladas; no compilar picotool/pioasm con el cross-compiler.
$hostPicoTools=Join-Path $HOME '.pico-sdk\tools\2.3.1\pioasm'
$hostPicotool=Join-Path $HOME '.pico-sdk\picotool\2.3.1\picotool'
$hostArgs=@()
if(Test-Path (Join-Path $hostPicoTools 'pioasmConfig.cmake')) {$hostArgs += "-Dpioasm_DIR=$hostPicoTools"}
if(Test-Path (Join-Path $hostPicotool 'picotoolConfig.cmake')) {$hostArgs += "-Dpicotool_DIR=$hostPicotool"}
if ([string]::IsNullOrWhiteSpace($TflmLibrary)) {
  $libs=@(Get-ChildItem -LiteralPath (Join-Path $TflmInclude 'tensorflow\lite\micro\tools\make\gen') `
    -Filter libtensorflow-microlite.a -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match 'cortex_m_generic' -and $_.FullName -match 'cortex.m33' })
  if($libs.Count -gt 0){$TflmLibrary=$libs[0].FullName}
}
if (-not $TflmLibrary -or -not (Test-Path -LiteralPath $TflmLibrary -PathType Leaf)) {
  $make=Get-Command make.exe -ErrorAction SilentlyContinue
  if(-not $make){$make=Get-Command make -ErrorAction SilentlyContinue}
  if(-not $make){throw 'Falta libtensorflow-microlite.a y GNU make. Instale GNU make o indique -TflmLibrary con un .a ARM Cortex-M33 compatible.'}
  Write-Host 'Compilando TFLM para Cortex-M33 con GNU make...'
  Push-Location $TflmInclude
  try {
    & $make.Source -f tensorflow/lite/micro/tools/make/Makefile `
       TARGET=cortex_m_generic TARGET_ARCH=cortex-m33 "TARGET_TOOLCHAIN_ROOT=$toolchain" microlite
    if($LASTEXITCODE -ne 0){throw "Fallo la compilacion TFLM ($LASTEXITCODE)"}
  } finally {Pop-Location}
  $libs=@(Get-ChildItem -LiteralPath (Join-Path $TflmInclude 'tensorflow\lite\micro\tools\make\gen') `
     -Filter libtensorflow-microlite.a -Recurse -File -ErrorAction SilentlyContinue |
     Where-Object { $_.FullName -match 'cortex_m_generic' -and $_.FullName -match 'cortex.m33' })
  if($libs.Count -eq 0){throw 'GNU make termino pero no se encontro libtensorflow-microlite.a para cortex-m33'}
  $TflmLibrary=$libs[0].FullName
}
if ([IO.Path]::GetExtension($TflmLibrary) -ne '.a') {throw 'Se requiere una biblioteca ARM .a; no se aceptan .lib de Windows.'}
$build=Join-Path $root 'build-pico2-w'
if($Clean -and (Test-Path $build)){Remove-Item $build -Recurse -Force}
$gen=Join-Path $build 'generated'
New-Item -ItemType Directory -Force -Path $gen | Out-Null
$modelcpp=Join-Path $gen 'embedded_model.cpp'
& $python (Join-Path $root 'tools\embed_tflite.py') --input $Model --output $modelcpp
if($LASTEXITCODE -ne 0){throw 'No se pudo incrustar el modelo TFLite'}
$config=Join-Path $gen 'pico_build_config.h'
# El header contiene credenciales (si se informaron); queda solo en build-pico2-w.
function Quote-C([string]$v) {return '"'+$v.Replace('\','\\').Replace('"','\"')+'"'}
$ssid=Quote-C $WifiSsid; $password=Quote-C $WifiPassword
@"
#pragma once
#define PICOKERAS_WIFI_SSID $ssid
#define PICOKERAS_WIFI_PASSWORD $password
#define PICOKERAS_UCI_PORT $Port
"@ | Set-Content -LiteralPath $config -Encoding ascii
Write-Host 'BUILD picoKeras ARM v0.1.20 - Pico 2 W'
Write-Host "MODEL: $Model"
Write-Host "SDK: $PicoSdkPath"
Write-Host "TFLM: $TflmInclude"
Write-Host "TFLM LIB: $TflmLibrary"
Write-Host "ARENA: $ArenaBytes bytes / TCP: $([bool]$WifiSsid)"
& $cmake -S $root -B $build -G Ninja `
  '-DPICO_BOARD=pico2_w' "-DPICO_SDK_PATH=$PicoSdkPath" "-DTFLM_INCLUDE=$TflmInclude" `
  "-DTFLM_LIBRARY=$TflmLibrary" "-DPICOKERAS_MODEL_CPP=$modelcpp" `
  "-DPICOKERAS_CONFIG_HEADER=$config" "-DPICOKERAS_ARENA_BYTES=$ArenaBytes" `
  "-DCMAKE_MAKE_PROGRAM=$ninja" @hostArgs "-DCMAKE_C_COMPILER=$gcc" `
  "-DCMAKE_CXX_COMPILER=$gxx" "-DCMAKE_ASM_COMPILER=$gcc" '-DCMAKE_BUILD_TYPE=Release'
if($LASTEXITCODE -ne 0){throw 'CMake configure fallo'}
& $cmake --build $build --parallel 4
if($LASTEXITCODE -ne 0){throw 'Compilacion ARM fallo'}
$uf2=Join-Path $build 'picoKeras.uf2'
if(-not (Test-Path $uf2)){throw "Build no genero el UF2: $uf2"}
Write-Host "UF2: $uf2" -ForegroundColor Green
