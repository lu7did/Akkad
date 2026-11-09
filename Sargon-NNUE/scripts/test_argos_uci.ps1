# test_argos_uci.ps1 v0.1.0
# Diagnóstico de handshake UCI (brain argos) usando los mismos argumentos del benchmark.
param(
  [string]$Python = "",
  [string]$Brain = "argos",
  [int]$Timeout = 120
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not $Python) {
  $candidates = @(
    (Join-Path $root '.venv/Scripts/python.exe'),
    (Join-Path $root 'venv/Scripts/python.exe'),
    (Join-Path $root '.venv/bin/python'),
    (Join-Path $root 'venv/bin/python')
  )
  foreach ($candidate in $candidates) { if (Test-Path $candidate) { $Python = $candidate; break } }
  if (-not $Python) { $Python = if (Get-Command python -ErrorAction SilentlyContinue) { 'python' } else { 'python3' } }
}
$diagnostic = Join-Path $PSScriptRoot 'test_argos_uci.py'
& $Python $diagnostic --id $Brain --python $Python --timeout $Timeout
exit $LASTEXITCODE
