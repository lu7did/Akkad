param(
 [Parameter(Mandatory=$true)][string]$Keras,
 [int]$CalibrationSamples = 64,
 [int]$ValidationSamples = 64,
 [double]$MaxError = 0.20,
 [string]$Report = '.\layernorm_71_v0.1.28.json',
 [string]$Layer = 'layer_normalization_71'
)
$ErrorActionPreference = 'Stop'
$script = Join-Path $PSScriptRoot '..\tools\probe_layernorm_71.py'
if (!(Test-Path -LiteralPath $Keras -PathType Leaf)) { throw "Modelo Keras inexistente: $Keras" }
python $script --keras $Keras --calibration-samples $CalibrationSamples --validation-samples $ValidationSamples --max-error $MaxError --report $Report --layer $Layer
$code = $LASTEXITCODE
if ($code -eq 2) { Write-Warning "Experimento completo: error mayor al umbral. Consultar reporte: $Report"; exit 2 }
if ($code -ne 0) { throw "Error de ejecución del experimento ($code)" }
