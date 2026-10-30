param(
 [Parameter(Mandatory=$true)][string]$Keras,
 [int]$CalibrationSamples = 64,
 [int]$ValidationSamples = 64,
 [double]$MaxError = 0.20,
 [string]$Report = '.\layernorm_71_scales_v0.1.30.json',
 [string]$Layer = 'layer_normalization_71'
)
$ErrorActionPreference = 'Stop'
if (!(Test-Path -LiteralPath $Keras -PathType Leaf)) { throw "Modelo Keras inexistente: $Keras" }
$py = Join-Path $PSScriptRoot '..\tools\probe_layernorm_71_scales.py'
python $py --keras $Keras --layer $Layer --calibration-samples $CalibrationSamples --validation-samples $ValidationSamples --max-error $MaxError --report $Report
if ($LASTEXITCODE -ne 0) { throw "Fallo del experimento v0.1.30 (exit code $LASTEXITCODE)" }
