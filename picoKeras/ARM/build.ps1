# picoKeras RP2350: firmware nativo, sin TensorFlow de escritorio.
[CmdletBinding()]
param(
    [string]$Model,
    [string]$ModelUrl=$env:PICOKERAS_MODEL_URL,
    [string]$ModelSha256=$env:PICOKERAS_MODEL_SHA256,
    [string]$PicoSdkPath=$env:PICO_SDK_PATH,
    [string]$TflmInclude=$env:TFLM_INCLUDE,
    [string]$TflmLibrary=$env:TFLM_LIBRARY,
    [string]$WifiSsid='',
    [string]$WifiPassword='',
    [ValidateRange(8192,262144)][int]$ArenaBytes=98304,
    [ValidateRange(1,65535)][int]$Port=6110,
    [switch]$Clean,
    [switch]$NoDownload,
    [switch]$Help
)
$ErrorActionPreference='Stop'
if ($Help -or $args -contains '--help') {
@'
picoKeras ARM v0.1.28 - Raspberry Pi Pico 2 W (RP2350)
  .\build.ps1 [-Model archivo.tflite] [-ModelUrl https://.../modelo.tflite]
              [-ModelSha256 SHA256] [-PicoSdkPath RUTA]
              [-TflmInclude RUTA] [-TflmLibrary ARCHIVO.a]
              [-WifiSsid SSID -WifiPassword CLAVE] [-ArenaBytes 98304]
              [-Port 6110] [-Clean] [-NoDownload] [-Help]
  Sin -Model: se utiliza assets/model.tflite o el unico .tflite en assets.
  Si no existe un modelo y se configura -ModelUrl o PICOKERAS_MODEL_URL,
  se descarga a assets/model.tflite. No se inventa ni descarga un modelo arbitrario.
  ModelSha256/PICOKERAS_MODEL_SHA256 verifica los bytes descargados.
  TFLM se compila directamente con CMake/Ninja para RP2350; no requiere MSYS2.
  -TflmLibrary permite usar una biblioteca ARM .a precompilada.
  -NoDownload impide descargas. El SDK y toolchain ARM deben estar instalados.
  Resultado: build-pico2-w/picoKeras.uf2
'@ | Write-Output
 return
}
$root=$PSScriptRoot
$assets=Join-Path $root 'assets'
function Get-FileHashChecked([string]$file,[string]$expected) {
    if (-not [string]::IsNullOrWhiteSpace($expected)) {
        if ($expected -notmatch '^[0-9a-fA-F]{64}$') { throw 'ModelSha256 debe contener exactamente 64 caracteres hexadecimales.' }
        $actual=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash
        if ($actual -ine $expected) { throw "SHA-256 del modelo incorrecto (actual=$actual)" }
    }
}
function Download-Model([string]$url,[string]$destination,[string]$sha256) {
    $uri=$null
    if (-not [Uri]::TryCreate($url,[UriKind]::Absolute,[ref]$uri) -or $uri.Scheme -ne 'https') {
        throw 'ModelUrl debe ser una URL HTTPS directa a un archivo .tflite.'
    }
    if ($NoDownload) { throw 'Falta el modelo y -NoDownload impide descargarlo.' }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
    $temp="$destination.download"
    try {
        Write-Host "[picoKeras] Descargando modelo: $url"
        Invoke-WebRequest -Uri $uri.AbsoluteUri -OutFile $temp -ErrorAction Stop
        $stream=[IO.File]::OpenRead($temp)
        try {
            $header=New-Object byte[] 8
            if ($stream.Read($header,0,8) -ne 8 -or
                [Text.Encoding]::ASCII.GetString($header,4,4) -ne 'TFL3') {
                throw 'El archivo descargado no tiene el identificador FlatBuffer TFL3 de TFLite.'
            }
        } finally { $stream.Dispose() }
        Get-FileHashChecked $temp $sha256
        Move-Item -LiteralPath $temp -Destination $destination -Force
    } finally { if(Test-Path -LiteralPath $temp){Remove-Item -LiteralPath $temp -Force} }
}
if ([string]::IsNullOrWhiteSpace($Model)) {
    $preferred=Join-Path $assets 'model.tflite'
    if (Test-Path -LiteralPath $preferred -PathType Leaf) {
        $Model=$preferred
    } else {
        $candidates=@(Get-ChildItem -LiteralPath $assets -File -Filter '*.tflite' -ErrorAction SilentlyContinue |
            Sort-Object -Property Name)
        if ($candidates.Count -eq 1) { $Model=$candidates[0].FullName }
        elseif ($candidates.Count -gt 1) {
            $names=($candidates | ForEach-Object { $_.Name }) -join ', '
            throw "Hay varios modelos en '$assets' ($names). Seleccione uno con -Model."
        } elseif (-not [string]::IsNullOrWhiteSpace($ModelUrl)) {
            Download-Model $ModelUrl $preferred $ModelSha256
            $Model=$preferred
        } else {
            throw "No hay modelo .tflite en '$assets'. El modelo entrenado NO forma parte de las dependencias: indique -Model, coloque assets/model.tflite, o configure -ModelUrl (PICOKERAS_MODEL_URL)."
        }
    }
} elseif (-not (Test-Path -LiteralPath $Model -PathType Leaf) -and -not [string]::IsNullOrWhiteSpace($ModelUrl)) {
    $Model=$ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Model)
    Download-Model $ModelUrl $Model $ModelSha256
}
if (-not (Test-Path -LiteralPath $Model -PathType Leaf)) { throw "No existe el modelo: $Model" }
if ([IO.Path]::GetExtension($Model) -ine '.tflite') { throw "El modelo debe tener extension .tflite: $Model" }
$Model=(Resolve-Path -LiteralPath $Model -ErrorAction Stop).Path
Get-FileHashChecked $Model $ModelSha256
if ([string]::IsNullOrWhiteSpace($TflmInclude)) { $TflmInclude=Join-Path $root 'third_party\tflm-tree' }
if (-not (Test-Path (Join-Path $TflmInclude 'tensorflow\lite\micro\micro_interpreter.h'))) {
  if ($NoDownload) { throw "No se encontro TFLM en $TflmInclude y -NoDownload impide descargarlo." }
  $git=Get-Command git.exe -ErrorAction SilentlyContinue
  if(-not $git){$git=Get-Command git -ErrorAction SilentlyContinue}
  if(-not $git){throw 'Falta TFLM y no se encontro git. Instale Git o indique -TflmInclude.'}
  if (Test-Path -LiteralPath $TflmInclude) {
    $entries=@(Get-ChildItem -LiteralPath $TflmInclude -Force -ErrorAction SilentlyContinue)
    if($entries.Count -gt 0){throw "TFLM no esta completo y el directorio no esta vacio: $TflmInclude"}
  }
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $TflmInclude) | Out-Null
  Write-Host '[picoKeras] Descargando fuentes TFLM (dependencia externa)...'
  & $git.Source clone --depth 1 https://github.com/tensorflow/tflite-micro.git $TflmInclude
  if($LASTEXITCODE -ne 0){throw "git clone TFLM fallo: $LASTEXITCODE"}
  # Evita advertencia de gitlink en el indice del repositorio exterior.
  # No modifica el indice de Git; el usuario debe ignorar la dependencia local.
}
if (-not (Test-Path (Join-Path $TflmInclude 'tensorflow\lite\micro\micro_interpreter.h'))) {
 throw "Faltan encabezados TFLM en $TflmInclude incluso despues de la descarga."
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
# v0.1.28: TFLM is built by CMake/Ninja using the existing source tree.
# -TflmLibrary remains an optional precompiled ARM .a override.
if (-not [string]::IsNullOrWhiteSpace($TflmLibrary)) {
  if (-not (Test-Path -LiteralPath $TflmLibrary -PathType Leaf)) {
    throw "TflmLibrary no existe: $TflmLibrary"
  }
  if ([IO.Path]::GetExtension($TflmLibrary) -ine '.a') {
    throw 'TflmLibrary debe ser una biblioteca ARM .a (no .lib de Windows).'
  }
  $TflmLibrary=(Resolve-Path -LiteralPath $TflmLibrary).Path
  Write-Host '[picoKeras] Usando biblioteca ARM TFLM externa.'
} else {
  Write-Host '[picoKeras] TFLM sera compilado con CMake + Ninja (sin MSYS2/GNU Make).'
  $downloads=Join-Path $TflmInclude 'tensorflow\lite\micro\tools\make\downloads'
  $flatbuffers=Join-Path $downloads 'flatbuffers\include\flatbuffers\flatbuffers.h'
  if (-not (Test-Path -LiteralPath $flatbuffers)) {
    if ($NoDownload) { throw "Falta FlatBuffers: $flatbuffers (-NoDownload activo)." }
    Write-Host '[picoKeras] Preparando dependencias TFLM mediante Python nativo...'
    $deps=Join-Path $TflmInclude 'tensorflow\lite\micro\tools\make\download_dependencies.py'
    Push-Location $TflmInclude
    try {
      & $python -u $deps --downloads_dir 'tensorflow/lite/micro/tools/make/downloads' --tensorflow_root $TflmInclude
      if ($LASTEXITCODE -ne 0) { throw "Dependencias TFLM fallaron: $LASTEXITCODE" }
    } finally { Pop-Location }
    if (-not (Test-Path -LiteralPath $flatbuffers)) { throw "FlatBuffers sigue faltando: $flatbuffers" }
  }
}
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
Write-Host 'BUILD picoKeras ARM v0.1.28 - Pico 2 W'
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
