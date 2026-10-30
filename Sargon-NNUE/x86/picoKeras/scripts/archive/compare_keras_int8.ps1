param(
 [Parameter(Mandatory=$true)][string]$Keras,
 [string]$OutputDir='.',
 [int]$CalibrationSamples=256,
 [int]$ValidationSamples=64,
 [double]$MaxFp32Error=0.08,
 [double]$MaxInt8Error=0.20
)
$ErrorActionPreference='Stop'
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$runner=Join-Path $PSScriptRoot 'int8_pipeline.ps1'
$summary=@{}
foreach($source in @('direct','clone')) {
  $fp=Join-Path $OutputDir "small.$source.fp32.tflite"
  $int8=Join-Path $OutputDir "small.$source.int8.tflite"
  $report=Join-Path $OutputDir "small.$source.report.json"
  try {
    & $runner -Mode convert -Source $source -Keras $Keras -Fp32 $fp -Int8 $int8 -Report $report -CalibrationSamples $CalibrationSamples -ValidationSamples $ValidationSamples -MaxFp32Error $MaxFp32Error -MaxInt8Error $MaxInt8Error
  } catch { Write-Warning "$source : $($_.Exception.Message)" }
  if (!(Test-Path -LiteralPath $report)) { throw "No se genero informe para $source" }
  $entry=Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
  $summary[$source]=@{status=$entry.status; report=$report; float_tensors=@($entry.steps.int8_audit.float_tensors).Count; float_operations=@($entry.steps.int8_audit.float_operations).Count; error=$entry.error.message}
  Write-Host "$source $($entry.status) floats=$($summary[$source].float_tensors) float_ops=$($summary[$source].float_operations)"
}
$summaryPath=Join-Path $OutputDir 'small.direct_vs_clone.summary.json'
$summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding utf8
Write-Host "Comparacion completada; informe: $summaryPath"
if($summary.direct.status -ne 'PASS' -or $summary.clone.status -ne 'PASS') {exit 2}
