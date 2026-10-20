param(
    [string]$Python = "C:\Users\pedro\ufasta\Scripts\python.exe",
    [int]$Port = 6200,
    [string]$StockfishPath = "C:\Users\pedro\github\bobby\stockfish\stockfish.exe",
    [string]$Network = "",
    [int]$StockfishTimeout = 5000,
    [int]$StockfishCheckDepth = 1,
    [int]$StockfishCache = 100000,
    [string]$Player = "sargon",
    [int]$Depth = 3,
    [int]$QDepth = 2,
    [int]$TMax = 15000,
    [string]$Boost = "0",
    [string]$Turbo = "0",
    [int]$Nodes = 5000000,
    [string]$Elo = "max",
    [int]$StockfishThreads = 1,
    [int]$StockfishHash = 256
)

# Resolver rutas desde la ubicación real de este script.
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Listener = Join-Path $ProjectRoot "src\sargon-listen.py"

if (-not (Test-Path -LiteralPath $Listener -PathType Leaf)) {
    throw "No se encontró sargon-listen.py en: $Listener"
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "No se encontró Python en: $Python"
}
if (-not (Test-Path -LiteralPath $StockfishPath -PathType Leaf)) {
    throw "No se encontró Stockfish en: $StockfishPath"
}

$EffectiveDepth = $Depth
$EffectiveNodes = $Nodes
if ($Player -eq "stockfish") {
    if (-not $PSBoundParameters.ContainsKey("Depth")) { $EffectiveDepth = 20 }
    if (-not $PSBoundParameters.ContainsKey("Nodes")) { $EffectiveNodes = 0 }
}

$engineArgs = @(
    $Listener,
    "--mode", "TCP",
    "--port", $Port,
    "--player", $Player,
    "--depth", $EffectiveDepth,
    "--qdepth", $QDepth,
    "--tmax", $TMax
)

if ($Player -eq "stockfish") {
    # Stockfish player es monolítico: evaluator=NULL y el motor usa su propia NNUE.
    $engineArgs += @(
        "--evaluator", "null",
        "--engine-path", $StockfishPath,
        "--nodes", $EffectiveNodes,
        "--elo", $Elo,
        "--stockfish-threads", $StockfishThreads,
        "--stockfish-hash", $StockfishHash
    )
}
else {
    # Stockfish evaluator: el player elegido conserva su propia estrategia de búsqueda.
    $engineArgs += @(
        "--evaluator", "stockfish",
        "--stockfish-path", $StockfishPath,
        "--stockfish-timeout", $StockfishTimeout,
        "--stockfish-check-depth", $StockfishCheckDepth,
        "--stockfish-cache", $StockfishCache
    )

    # No se fuerza EvalFile por defecto; Stockfish usa la NNUE de su ejecutable.
    if (-not [string]::IsNullOrWhiteSpace($Network)) {
        $resolvedNetwork = (Resolve-Path $Network -ErrorAction Stop).Path
        $engineArgs += @("--network", $resolvedNetwork)
    }
}

if ($Player -eq "sargon-plus") {
    $engineArgs += @("--boost", $Boost, "--turbo", $Turbo)
}

& $Python @engineArgs
exit $LASTEXITCODE
