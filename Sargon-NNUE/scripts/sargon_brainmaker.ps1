# Sargon-NNUE — Registro y consulta de brains
# Autor y copyright: Pedro. Copyright (c) 2026 Pedro.
# Licencia: Creative Commons Attribution 4.0 International (CC BY 4.0).
# Software entregado "AS IS", sin garantía de ningún tipo.
# Versión del lanzador: v0.6.82
param(
  [Parameter(ValueFromRemainingArguments=$true)]
  [string[]]$Arguments
)
$Python = 'C:\Users\pedro\ufasta\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
  $Python = 'python'
}
$projectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = (Join-Path $projectRoot 'src') + [IO.Path]::PathSeparator + $env:PYTHONPATH

# Windows PowerShell 5.1 decodes native subprocess text with the console encoding.
# Set both sides to UTF-8; without this, unsupported emoji may become U+FFFD.
$previousPythonIo = [Environment]::GetEnvironmentVariable('PYTHONIOENCODING', 'Process')
$previousPythonUtf8 = [Environment]::GetEnvironmentVariable('PYTHONUTF8', 'Process')
try {
  $previousConsoleEncoding = [Console]::OutputEncoding
} catch {
  $previousConsoleEncoding = $null
}
$previousOutputEncoding = $OutputEncoding
$exitCode = 1
try {
  $utf8 = New-Object System.Text.UTF8Encoding($false)
  if ($null -ne $previousConsoleEncoding) {
    [Console]::OutputEncoding = $utf8
  }
  $OutputEncoding = $utf8
  $env:PYTHONIOENCODING = 'utf-8'
  $env:PYTHONUTF8 = '1'
  & $Python -m sargon_nnue.sargon_brainmaker @Arguments
  $exitCode = $LASTEXITCODE
}
finally {
  [Environment]::SetEnvironmentVariable('PYTHONIOENCODING', $previousPythonIo, 'Process')
  [Environment]::SetEnvironmentVariable('PYTHONUTF8', $previousPythonUtf8, 'Process')
  $OutputEncoding = $previousOutputEncoding
  if ($null -ne $previousConsoleEncoding) {
    [Console]::OutputEncoding = $previousConsoleEncoding
  }
}
exit $exitCode
