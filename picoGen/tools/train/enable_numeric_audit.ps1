# Opt-in: modify only the MON=4 invocation in the user's own Genesis script.
param([string]$Script = (Join-Path $PSScriptRoot 'run_genesis.ps1'))
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Script -PathType Leaf)) { throw "No existe $Script" }
$full = (Resolve-Path -LiteralPath $Script).Path
$original = [IO.File]::ReadAllText($full)
$lines = @($original -split "`r?`n")
$matches = @($lines | Where-Object { $_ -match 'Invoke-Stage\s+4\s+''genAudit\.py''' })
if ($matches.Count -ne 1) { throw "MON=4 debe tener una invocacion genAudit.py; encontradas $($matches.Count). Sin cambios." }
$line = $matches[0]
if ($line.Contains("'--db'")) { Write-Host 'MON=4 ya contiene --db; sin cambios.'; exit 0 }
if ($original -notmatch '\$SampleDb\s*=') { throw 'No se encontro variable $SampleDb. Sin cambios.' }
$old = "'--bk', " + '$Bk,'
$new = "'--bk', " + '$Bk,' + " '--db', " + '$SampleDb,'
if (-not $line.Contains($old)) { throw 'No se encontro el argumento --bk, $Bk en MON=4. Sin cambios.' }
$revisedLine = $line.Replace($old, $new)
$revised = $original.Replace($line, $revisedLine)
$backup = "$full.before-numeric-audit-v0128.bak"
if (Test-Path -LiteralPath $backup) { throw "Existe el respaldo $backup. Sin cambios." }
[IO.File]::WriteAllText($backup, $original)
[IO.File]::WriteAllText($full, $revised)
Write-Host "Genesis MON=4 actualizado; respaldo=$backup"
