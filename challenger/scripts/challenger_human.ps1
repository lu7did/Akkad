param(
    [string]$Python = "C:\Users\pedro\ufasta\Scripts\python.exe",
    [int]$Port      = 5200,
    [string]$Brain  = "human",
    [bool]$Gui      = $true
)

$challengerArgs = @(
    "-m", "challenger.cli",
    "--port", $Port,
    "--brain", $Brain
)

if ($Gui) {
    $challengerArgs += "--gui"
}

& $Python @challengerArgs
