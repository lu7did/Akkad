param(
    [string]$Python = "C:\Users\pedro\ufasta\Scripts\python.exe",
    [int]$Port = 6200,
    [string]$StockfishPath = "C:\Users\pedro\github\bobby\stockfish\stockfish.exe",
    [int]$Depth = 20,
    [int]$Threads = 1,
    [int]$HashMB = 256,
    [int]$Timeout = 120000,
    [switch]$Audit,
    [string]$AuditFile = ".\stockfish_player_audit.jsonl"
)

# Stockfish como player monolítico.  No se usa evaluator externo.
# Nodes=0 desactiva deliberadamente el segundo límite: la búsqueda queda
# gobernada por `go depth <Depth>` para evitar que un límite de nodos más bajo
# trunque inadvertidamente la profundidad objetivo.

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Listener = Join-Path $ProjectRoot "src\sargon-listen.py"

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "No se encontró Python en: $Python"
}
if (-not (Test-Path -LiteralPath $Listener -PathType Leaf)) {
    throw "No se encontró sargon-listen.py en: $Listener"
}
if (-not (Test-Path -LiteralPath $StockfishPath -PathType Leaf)) {
    throw "No se encontró Stockfish en: $StockfishPath"
}

$argsEngine = @(
    $Listener,
    "--mode", "TCP",
    "--port", $Port,
    "--player", "stockfish",
    "--evaluator", "null",
    "--engine-path", $StockfishPath,
    "--depth", $Depth,
    "--nodes", 0,
    "--elo", "max",
    "--stockfish-threads", $Threads,
    "--stockfish-hash", $HashMB,
    "--timeout", $Timeout
)

if ($Audit) {
    $argsEngine += @("--audit", "--audit-file", $AuditFile)
}

Write-Host "Stockfish player: depth=$Depth nodes=OFF elo=max threads=$Threads hash=${HashMB}MB timeout=${Timeout}ms evaluator=null"
& $Python @argsEngine
exit $LASTEXITCODE
