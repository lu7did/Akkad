param(
 [ValidateSet('convert','audit','validate')][string]$Mode='convert',
 [string]$Keras,
 [switch]$IntegerSquare,
 [ValidateSet('direct','clone')][string]$Source='direct',
 [Parameter(Mandatory=$true)][string]$Fp32,
 [Parameter(Mandatory=$true)][string]$Int8,
 [string]$Report='int8_pipeline_v0.1.32.json',
 [int]$CalibrationSamples=256,
 [int]$ValidationSamples=64,
 [double]$MaxFp32Error=0.08,
 [double]$MaxInt8Error=0.20
)
$ErrorActionPreference='Stop'
$tool=Join-Path $PSScriptRoot '..\tools\int8_pipeline.py'
$cpp=Join-Path $PSScriptRoot '..\src\model.cpp'
$argsPython=@($tool,'--mode',$Mode,'--source',$Source,'--fp32',$Fp32,'--int8',$Int8,'--report',$Report,'--calibration-samples',"$CalibrationSamples",'--validation-samples',"$ValidationSamples",'--max-fp32-error',"$($MaxFp32Error.ToString([cultureinfo]::InvariantCulture))",'--max-int8-error',"$($MaxInt8Error.ToString([cultureinfo]::InvariantCulture))",'--cpp-resolver',$cpp)
if ($Keras) {$argsPython+=@('--keras',$Keras)}
if ($IntegerSquare) {$argsPython+='--integer-square'}
& python @argsPython
$code=$LASTEXITCODE
if ($code -ne 0) { throw "INT8 pipeline FAIL (exit code $code); ver informe: $Report" }
