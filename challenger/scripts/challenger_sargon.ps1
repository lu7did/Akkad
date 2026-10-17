param(
    [string]$Python  = "C:\Users\pedro\ufasta\Scripts\python.exe",
    [int]$Port       = 6200,
    [string]$Event   = "sargon-VS-beavys",
    [int]$Timeout    = 60000,
    [string]$Json    = "..\data\sargon-beavys2.json",
    [string]$Brain   = "sargon",
    [int]$Plies      = 2,
    [bool]$Forever   = $true,
    [bool]$Gui       = $true
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

$challengerArgs += @(
    "--json", $Json,
    "--brain", $Brain,
    "--plies", $Plies
)

& $Python @challengerArgs
