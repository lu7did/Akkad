# picoKeras x86 Windows build v0.2.6
param(
 [string]$TensorFlowRoot = $env:TENSORFLOW_ROOT,
 [ValidateSet('Debug','Release','RelWithDebInfo')][string]$Config='Release',
 [switch]$NoDownload,
 [switch]$Clean,
 [ValidateSet('ON','OFF')][string]$Multicore='ON',
 [switch]$Help
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
if ($Help) {
 Write-Host 'Usage: build.ps1 [-TensorFlowRoot DIR] [-Config Release|Debug|RelWithDebInfo] [-NoDownload] [-Clean] [-Multicore ON|OFF] [-Help]'
 Write-Host 'Builds picoKeras X86 using shared picoKeras/src. Output: picoKeras/x86/build (Release subdirectory with MSVC).'
 return
}
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$platform=Join-Path $root 'x86'
$build=Join-Path $platform 'build'
$deps=Join-Path $platform 'third_party'
$defaultRoot=Join-Path $deps 'tensorflow-c-2.18.1'
$url='https://storage.googleapis.com/tensorflow/versions/2.18.1/libtensorflow-cpu-windows-x86_64.zip'
function Test-Tf([string]$dir) {
 if (-not $dir) { return $false }
 return ((Test-Path (Join-Path $dir 'include/tensorflow/c/c_api.h')) -and
         (Test-Path (Join-Path $dir 'lib/tensorflow.lib')) -and
         (Test-Path (Join-Path $dir 'lib/tensorflow.dll')))
}
if (-not (Get-Command cmake -ErrorAction SilentlyContinue)) { throw 'CMake not found. Install CMake before running build.ps1.' }
if (-not $TensorFlowRoot) {$TensorFlowRoot=$defaultRoot}
$TensorFlowRoot=[IO.Path]::GetFullPath($TensorFlowRoot)
if (-not (Test-Tf $TensorFlowRoot)) {
 if ($NoDownload -or ($TensorFlowRoot -ne [IO.Path]::GetFullPath($defaultRoot))) {throw "TensorFlow C SDK missing or incomplete: $TensorFlowRoot"}
 New-Item -ItemType Directory -Force $deps | Out-Null
 $zip=Join-Path $deps 'tensorflow-c-2.18.1.zip'
 $stage=Join-Path $deps 'tensorflow-c-stage'
 if (Test-Path $stage) {Remove-Item $stage -Recurse -Force}
 Write-Host 'Downloading TensorFlow C SDK 2.18.1'
 [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
 Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
 Expand-Archive -LiteralPath $zip -DestinationPath $stage -Force
 if (-not (Test-Tf $stage)) {throw "Downloaded SDK is incomplete: $stage"}
 if (Test-Path $defaultRoot) {Remove-Item $defaultRoot -Recurse -Force}
 Move-Item $stage $defaultRoot
 Remove-Item $zip -Force
}
if ($Clean -and (Test-Path $build)) {Remove-Item $build -Recurse -Force}
# A cache moved between machines is invalid. Remove only the generated cache, not assets.
if (Test-Path (Join-Path $build 'CMakeCache.txt')) {
 $cache=Get-Content (Join-Path $build 'CMakeCache.txt') | Where-Object {$_ -like 'CMAKE_HOME_DIRECTORY:INTERNAL=*'} | Select-Object -First 1
 if ($cache -and $cache.Split('=',2)[1].Replace('\','/') -ne $platform.Replace('\','/')) {
   Write-Host 'Removing obsolete CMake cache' ; Remove-Item $build -Recurse -Force
 }
}
& cmake -S $platform -B $build "-DTENSORFLOW_ROOT=$TensorFlowRoot" "-DMULTICORE=$Multicore"
if ($LASTEXITCODE -ne 0) {throw "CMake configure failed ($LASTEXITCODE)"}
& cmake --build $build --config $Config --target picoKeras
if ($LASTEXITCODE -ne 0) {throw "CMake build failed ($LASTEXITCODE)"}
$exe=Join-Path $build "$Config/picoKeras.exe"
if (-not (Test-Path $exe)) {$exe=Join-Path $build 'picoKeras.exe'}
if (-not (Test-Path $exe)) {throw "No executable found under $build"}
Write-Host "Built picoKeras X86: $exe"
