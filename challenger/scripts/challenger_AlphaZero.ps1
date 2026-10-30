param(
    [string]$Python  = "C:\Users\pedro\ufasta\Scripts\python.exe",
    [string]$Ip      = "127.0.0.1",
    [int]$Port       = 6200,
    [string]$Event   = "Pruebas de AlphaZero-X86",
    [int]$Timeout    = 60000,
    [string]$Json    = "..\data\picoAlpha.json",
    [string]$Brain   = "sargon",
    [int]$Plies      = 4,
    [bool]$Forever   = $true,
    [bool]$Gui       = $true
)

# Resolve project layout relative to this script, regardless of the old location.
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$moduleRoots = @($projectRoot, (Join-Path $projectRoot 'src'))
$validRoots = @($moduleRoots | Where-Object { Test-Path (Join-Path $_ 'challenger\cli.py') })
if ($validRoots.Count -eq 0) {
    Write-Error "No se encontro challenger\cli.py en '$projectRoot' ni en '$projectRoot\src'. Verifica la estructura del paquete."
    exit 1
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    Write-Error "No se encontro el interprete Python: $Python"
    exit 1
}

# Respect the original convention: JSON relative to scripts/.
$originalPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = (@($validRoots) + @($originalPythonPath) | Where-Object { $_ }) -join [IO.Path]::PathSeparator
    Push-Location $PSScriptRoot
    try {
        # Consultar opciones reales para no inventar argumentos CLI.
        $helpText = (& $Python -m challenger.cli --help 2>&1 | Out-String)
        if ($LASTEXITCODE -ne 0) {
            throw "No se pudo consultar challenger.cli --help: $helpText"
        }
        if ($helpText -match '(?m)(?<![\w-])--ip(?![\w-])') {
            $ipOption = '--ip'
        } elseif ($helpText -match '(?m)(?<![\w-])--host(?![\w-])') {
            $ipOption = '--host'
        } else {
            throw "Challenger no anuncia --ip ni --host. Es necesario revisar challenger.cli antes de pasar una direccion remota."
        }
        $challengerArgs = @('-m', 'challenger.cli', $ipOption, $Ip, '--port', $Port)
        Write-Host "Challenger: destino ${Ip}:${Port} (opcion $ipOption)" -ForegroundColor Cyan
        if ($Forever) { $challengerArgs += '--forever' }
        $challengerArgs += @('--event', $Event, '--timeout', $Timeout)
        if ($Gui) { $challengerArgs += '--gui' }
        $challengerArgs += @('--json', $Json, '--brain', $Brain, '--plies', $Plies)
        & $Python @challengerArgs
        $code = $LASTEXITCODE
    }
    finally { Pop-Location }
}
finally {
    $env:PYTHONPATH = $originalPythonPath
}
if ($code -ne 0) { exit $code }
