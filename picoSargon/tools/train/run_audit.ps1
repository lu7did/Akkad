param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments)
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false); $OutputEncoding = [Console]::OutputEncoding; $env:PYTHONIOENCODING = 'utf-8'; $env:PYTHONUTF8 = '1' } catch {}
& python (Join-Path $PSScriptRoot 'Audit.py') @Arguments
exit $LASTEXITCODE
