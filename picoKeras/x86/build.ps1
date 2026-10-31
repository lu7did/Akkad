param(
    [string]$TensorFlowRoot = $env:TENSORFLOW_ROOT,
    [string]$Config = "Release",
    [switch]$NoDownload
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$project = $PSScriptRoot
$deps = Join-Path $project "third_party"
$defaultRoot = Join-Path $deps "tensorflow-c-2.18.1"
$url = "https://storage.googleapis.com/tensorflow/versions/2.18.1/libtensorflow-cpu-windows-x86_64.zip"

function Test-TensorFlowRoot([string]$Root) {
    if (-not $Root -or -not (Test-Path $Root)) { return $false }
    return ((Test-Path (Join-Path $Root "include/tensorflow/c/c_api.h")) -and
            (Test-Path (Join-Path $Root "lib/tensorflow.lib")) -and
            (Test-Path (Join-Path $Root "lib/tensorflow.dll")))
}

if (-not $TensorFlowRoot) { $TensorFlowRoot = $defaultRoot }
$TensorFlowRoot = [System.IO.Path]::GetFullPath($TensorFlowRoot)

Write-Host "picoKeras Desktop build"
Write-Host "TensorFlow: $TensorFlowRoot"
if (-not (Test-TensorFlowRoot $TensorFlowRoot)) {
    if ($NoDownload -or $TensorFlowRoot -ne [System.IO.Path]::GetFullPath($defaultRoot)) {
        throw "TensorFlow C SDK not found or incomplete: $TensorFlowRoot. Pass -TensorFlowRoot, or omit to install automatically."
    }
    New-Item -ItemType Directory -Force -Path $deps | Out-Null
    $zipFile = Join-Path $deps "libtensorflow-cpu-windows-x86_64-2.18.1.zip"
    $staging = Join-Path $deps "tensorflow-c-staging"
    if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
    Write-Host "Downloading official TensorFlow C 2.18.1 CPU distribution..."
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $url -OutFile $zipFile -UseBasicParsing
    Write-Host "Extracting TensorFlow C SDK..."
    Expand-Archive -LiteralPath $zipFile -DestinationPath $staging -Force
    if (-not (Test-TensorFlowRoot $staging)) {
        throw "Extracted TensorFlow SDK does not contain required .h/.lib/.dll files: $staging"
    }
    if (Test-Path $defaultRoot) { Remove-Item $defaultRoot -Recurse -Force }
    Move-Item $staging $defaultRoot
    Remove-Item $zipFile -Force
}
Write-Host "TensorFlow C SDK found"

$buildDir = Join-Path $project "build"
cmake -S $project -B $buildDir "-DTENSORFLOW_ROOT=$TensorFlowRoot"
if ($LASTEXITCODE -ne 0) { throw "CMake configure failed: $LASTEXITCODE" }
cmake --build $buildDir --config $Config
if ($LASTEXITCODE -ne 0) { throw "CMake build failed: $LASTEXITCODE" }
Write-Host "picoKeras built successfully"
