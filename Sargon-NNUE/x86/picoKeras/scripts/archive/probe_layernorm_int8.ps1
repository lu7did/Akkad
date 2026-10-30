param(
 [Parameter(Mandatory=$true)][string]$Keras,
 [int]$Samples=64,
 [double]$MaxError=0.20,
 [string]$Report="layernorm_probe_v0.1.27.json"
)
$ErrorActionPreference='Stop'
$resolved=Resolve-Path -LiteralPath $Keras -ErrorAction SilentlyContinue
if(-not $resolved){throw "Archivo Keras no encontrado: $Keras (directorio actual: $(Get-Location))"}
$tool=Join-Path $PSScriptRoot '..\tools\probe_layernorm_int8.py'
& python $tool --keras $resolved.Path --samples $Samples --max-error $MaxError --report $Report
$code=$LASTEXITCODE
if($code -ne 0){
 if(Test-Path -LiteralPath $Report){throw "Probe exit code $code. Informe: $Report"}
 throw "Probe exit code $code. No se generó informe: ocurrió un error previo a la validación."
}
