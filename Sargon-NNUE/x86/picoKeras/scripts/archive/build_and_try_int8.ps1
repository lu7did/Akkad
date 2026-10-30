param(
 [string]$Keras = "",
 [string]$Network = "",
 [string]$Brain = "",
 [switch]$SkipConversion,
 [switch]$SkipBuild,
 [int]$CalibrationSamples = 256,
 [int]$ValidationSamples = 64
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $Keras) { $Keras = Join-Path $root '..\..\data\runs\keras\small.keras' }
$Keras = [System.IO.Path]::GetFullPath($Keras)
if (-not $Network) { $Network = Join-Path $root 'small.mul.int8.tflite' }
$Network = [System.IO.Path]::GetFullPath($Network)
$report = Join-Path $root 'int8_pipeline_v0.1.37.json'
if (-not $SkipConversion) {
  if (-not (Test-Path -LiteralPath $Keras -PathType Leaf)) { throw "No existe .keras: $Keras" }
  try {
  & (Join-Path $root 'scripts\int8_pipeline.ps1') -Mode convert -Source clone -IntegerSquare -Keras $Keras `
    -Fp32 (Join-Path $root 'small.mul.fp32.tflite') -Int8 $Network -Report $report `
    -CalibrationSamples $CalibrationSamples -ValidationSamples $ValidationSamples -MaxInt8Error 0.20
  } catch { Write-Host "Pipeline finalizado con estado pendiente de runtime: $($_.Exception.Message)" }
  # v0.1.36 returns nonzero for runtime not registered. That condition is expected here,
  # but numeric and integer checks are compulsory.
  $j = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
  if (-not $j.steps.int8_audit.fully_int8_by_tensor_check -or -not $j.steps.fp32_vs_int8.pass) {
    throw "La validacion INT8 o numerica fallo: $report"
  }
  if (-not (Test-Path -LiteralPath $Network)) {
    $candidate = "$Network.runtime_unverified.tflite"
    if (Test-Path -LiteralPath $candidate) { Copy-Item -LiteralPath $candidate -Destination $Network -Force }
    else { throw "No hay candidato INT8: $candidate" }
  }
}
if (-not (Test-Path -LiteralPath $Network -PathType Leaf)) { throw "No existe TFLite: $Network" }
if (-not $SkipBuild) { & (Join-Path $root 'build.ps1') -Make; if($LASTEXITCODE -and $LASTEXITCODE -ne 0){throw 'Build fallido'} }
$exe = Join-Path $root 'build\Release\picoKeras.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw "No se encontro ejecutable: $exe" }
Write-Host "Modelo INT8: $Network"
Write-Host "picoKeras.exe: $exe"
Write-Host 'Ejecutando comprobacion de carga y kernels...'
# Never claim completion without actual successful startup/inference.
if (-not $Brain) { $Brain=''; }
$result = @('uci','isready','position startpos','go','quit') | & $exe --network $Network --stdio 2>&1
$result | ForEach-Object { Write-Host $_ }
if ($LASTEXITCODE -ne 0) { throw "picoKeras salio con codigo $LASTEXITCODE" }
if (-not (@($result | Where-Object { "$_" -match '^bestmove [a-h][1-8][a-h][1-8]' }).Count -gt 0)) {
  throw 'No hubo bestmove valido: la inferencia UCI no ha sido demostrada'
}
Write-Host 'PASS: picoKeras cargo el modelo y devolvio bestmove en una posicion real.'
