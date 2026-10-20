param(
    [string]$Python = "C:\Users\pedro\ufasta\Scripts\python.exe",
    [int]$Port = 6200,
    [string]$StockfishPath = "C:\Users\pedro\github\bobby\stockfish\stockfish.exe",
    [ValidateSet("stockfish-player", "stockfish-evaluator")]
    [string]$Mode = "stockfish-player",
    [int]$StockfishDepth = 20,
    [int]$StockfishNodes = 5000000,
    [string]$StockfishElo = "max",
    [int]$SargonDepth = 3,
    [int]$QDepth = 2,
    [int]$TMax = 15000,
    [string]$Network = "",
    [int]$StockfishTimeout = 5000,
    [int]$StockfishCheckDepth = 1,
    [string]$AuditFile = ".\stockfish_audit.jsonl",
    [int]$AuditEvalMax = 5000
)

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Listener = Join-Path $ProjectRoot "src\sargon-listen.py"

if (-not (Test-Path -LiteralPath $Listener -PathType Leaf)) { throw "No se encontró sargon-listen.py en: $Listener" }
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw "No se encontró Python en: $Python" }
if (-not (Test-Path -LiteralPath $StockfishPath -PathType Leaf)) { throw "No se encontró Stockfish en: $StockfishPath" }

$resolvedAudit = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $AuditFile))
Write-Host "AUDIT mode=$Mode file=$resolvedAudit"

$engineArgs = @(
    $Listener,
    "--mode", "TCP",
    "--port", $Port,
    "--audit",
    "--audit-file", $resolvedAudit,
    "--audit-eval-max", $AuditEvalMax
)

if ($Mode -eq "stockfish-player") {
    # IMPORTANTE: profundidad Stockfish independiente de la profundidad Sargón.
    # Esto evita el error de diagnóstico de sargon_stockfish.ps1 v0.6.15, cuyo
    # Depth default=3 era transmitido también al player Stockfish.
    $engineArgs += @(
        "--player", "stockfish",
        "--evaluator", "null",
        "--engine-path", $StockfishPath,
        "--depth", $StockfishDepth,
        "--nodes", $StockfishNodes,
        "--elo", $StockfishElo
    )
}
else {
    $engineArgs += @(
        "--player", "sargon",
        "--evaluator", "stockfish",
        "--stockfish-path", $StockfishPath,
        "--stockfish-timeout", $StockfishTimeout,
        "--stockfish-check-depth", $StockfishCheckDepth,
        "--depth", $SargonDepth,
        "--qdepth", $QDepth,
        "--tmax", $TMax
    )
    if (-not [string]::IsNullOrWhiteSpace($Network)) {
        $resolvedNetwork = (Resolve-Path $Network -ErrorAction Stop).Path
        $engineArgs += @("--network", $resolvedNetwork)
    }
}

Write-Host "Launching: $Python $($engineArgs -join ' ')"
& $Python @engineArgs
exit $LASTEXITCODE
