param(
    [string]$Python            = "C:\Users\pedro\ufasta\Scripts\python.exe",
    [int]$Port                 = 6200,
    [string]$Event             = "StockFish_Raw",
    [int]$Timeout              = 60000,
    [string]$Json              = ".\challenger_stockfish.json",
    [string]$Brain             = "stockfish",
    [int]$Plies                = 3,
    [bool]$Forever             = $true,
    [bool]$Gui                 = $true,
    [bool]$Verbose             = $true,
    [int]$StockfishMoveTime    = 2000,
    [string]$Stockfish         = "C:\Users\pedro\github\bobby\stockfish\stockfish.exe"
)

$challengerArgs = @(
    "-m", "challenger.cli",
    "--port", $Port
)

if ($Forever) {
    $challengerArgs += "--forever"
}

$challengerArgs += @(
    "--event", $Event,
    "--timeout", $Timeout
)

if ($Gui) {
    $challengerArgs += "--gui"
}

if ($Verbose) {
    $challengerArgs += ""
}

$challengerArgs += @(
    "--json", $Json,
    "--brain", $Brain,
    "--plies", $Plies
)

if ($Brain -eq "stockfish") {
    $challengerArgs += @(
        "--stockfish-movetime", $StockfishMoveTime,
        "--stockfish", $Stockfish
    )
}

& $Python @challengerArgs
