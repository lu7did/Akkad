# Incremental surgical patch: preserve current factory.py and unrelated fixes.
$ErrorActionPreference = 'Stop'
$path = Join-Path $PSScriptRoot 'src/sargon_nnue/factory.py'
$text = [System.IO.File]::ReadAllText($path)
$before = 'nodes = STOCKFISH_DEFAULT_NODES if raw_nodes is None else int(raw_nodes)'
$after = 'nodes = (1 if player_kind == "keras" else STOCKFISH_DEFAULT_NODES) if raw_nodes is None else int(raw_nodes)'
if ($text.Contains($after)) { Write-Host 'v0.6.190: factory.py ya actualizado'; exit 0 }
if (-not $text.Contains($before)) { throw 'factory.py no contiene el patrón esperado: se dejó intacto' }
$text = $text.Replace($before, $after)
[System.IO.File]::WriteAllText($path, $text, [System.Text.UTF8Encoding]::new($false))
Write-Host 'v0.6.190: factory.py actualizado (nodes por defecto=1 para keras)'
