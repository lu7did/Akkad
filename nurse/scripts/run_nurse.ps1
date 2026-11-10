param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$env:PYTHONPATH=(Join-Path $root 'src')+([IO.Path]::PathSeparator)+$env:PYTHONPATH
python -m nurse.uci @Arguments
exit $LASTEXITCODE
