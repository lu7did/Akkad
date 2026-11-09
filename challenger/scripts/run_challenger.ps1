# run_challenger.ps1 v1.0.0
# Generic launcher for akkad/challenger (Windows PowerShell 5.1 / PowerShell 7).
# Usage: .\run_challenger.ps1 --engine sargon --ip 127.0.0.1 --port 6200 [--json file.json]
# Explicit parser: no optional switch may be mistaken for a positional value.

$ErrorActionPreference = 'Stop'

function Show-Help {
    @'
run_challenger.ps1 v1.0.0 - Challenger contra motor UCI/TCP

USO:
  .\run_challenger.ps1 --engine {sargon|stockfish} --ip HOST --port NUMERO [opciones]

OBLIGATORIOS (sin ellos Challenger NO se ejecuta):
  --engine  sargon|stockfish   Motor local que juega contra el UCI/TCP remoto.
  --ip      HOST              IP o nombre del servidor del motor remoto.
  --port    1..65535          Puerto TCP del motor remoto.

OPCIONALES:
  --json    ARCHIVO           Ruta donde Challenger guarda sus estadisticas JSON.
                                Sin esta opcion se aplica el valor por defecto del CLI.
  --stockfish RUTA            Ejecutable Stockfish local (solo con --engine stockfish).
                                Si se omite: buscar en el PATH o junto al repositorio.
  --python  RUTA              Interprete Python (por defecto python del entorno activo).
  --help                      Mostrar esta ayuda y salir sin iniciar Challenger.

COMPORTAMIENTO:
  Conserva los defaults del script challenger_AlphaZero.ps1 de referencia:
  --forever y --gui habilitados; --timeout 60000 ms; --plies 4; evento Challenger.
  Los argumentos --engine, --ip y --port no tienen valores predeterminados.

EJEMPLOS:
  .\run_challenger.ps1 --engine sargon --ip 127.0.0.1 --port 6200
  .\run_challenger.ps1 --engine stockfish --ip 192.168.1.20 --port 6110 --json .\data\partidas.json
  .\run_challenger.ps1 --engine stockfish --ip localhost --port 6200 --stockfish C:\stockfish\stockfish.exe

Puede usar -engine/-ip/-port, etc., como alternativa PowerShell a --engine/--ip/--port.
'@ | Write-Host
}

function Fail([string]$message) {
    [Console]::Error.WriteLine("run_challenger: $message")
    [Console]::Error.WriteLine('Use --help para consultar las opciones.')
    exit 2
}

# No param(...) block: parse all tokens explicitly, including the double-dash forms.
$values = @{}
$valid = @('engine', 'ip', 'port', 'json', 'stockfish', 'python')
for ($i = 0; $i -lt $args.Count; $i++) {
    $token = [string]$args[$i]
    if ($token -in @('--help', '-help', '-h', '--h', '/?')) {
        Show-Help
        exit 0
    }
    if ($token -notmatch '^--?([A-Za-z][A-Za-z0-9-]*)$') {
        Fail "Argumento desconocido: '$token'."
    }
    $name = $Matches[1].ToLowerInvariant()
    if ($name -notin $valid) {
        Fail "Opcion desconocida: '$token'."
    }
    if ($values.ContainsKey($name)) {
        Fail "Opcion repetida: '$token'."
    }
    if (($i + 1) -ge $args.Count) {
        Fail "Falta valor para '$token'."
    }
    $next = [string]$args[$i + 1]
    if ([string]::IsNullOrWhiteSpace($next) -or $next.StartsWith('-')) {
        Fail "Falta valor para '$token' (se encontro '$next')."
    }
    $values[$name] = $next
    $i++
}

foreach ($name in @('engine', 'ip', 'port')) {
    if (-not $values.ContainsKey($name) -or [string]::IsNullOrWhiteSpace($values[$name])) {
        Fail "Falta argumento obligatorio --$name."
    }
}
$engine = $values['engine'].ToLowerInvariant()
if ($engine -notin @('sargon', 'stockfish')) {
    Fail "--engine debe ser sargon o stockfish; recibido '$engine'."
}
$ip = $values['ip']
[int]$port = 0
if (-not [int]::TryParse($values['port'], [ref]$port) -or $port -lt 1 -or $port -gt 65535) {
    Fail "--port debe ser un numero entre 1 y 65535; recibido '$($values['port'])'."
}
if ($values.ContainsKey('stockfish') -and $engine -ne 'stockfish') {
    Fail '--stockfish solo se utiliza con --engine stockfish.'
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$moduleRoots = @($projectRoot, (Join-Path $projectRoot 'src'))
$validRoots = @($moduleRoots | Where-Object {
    Test-Path -LiteralPath (Join-Path $_ 'challenger/cli.py') -PathType Leaf
})
if ($validRoots.Count -eq 0) {
    Fail "No se encontro challenger/cli.py dentro de '$projectRoot' ni en src/. Ubicar este script en challenger/scripts/."
}

# Prefer the active virtual environment. A user-provided interpreter can be an executable
# on PATH or a full path. Do not silently hardcode someone else's Python installation.
$python = 'python'
if ($values.ContainsKey('python')) { $python = $values['python'] }
$pythonCommand = Get-Command -Name $python -ErrorAction SilentlyContinue
if ($null -eq $pythonCommand) {
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        Fail "No se encontro Python: '$python'. Active su entorno o use --python RUTA."
    }
}

$cliArgs = @('-m', 'challenger.cli', '--brain', $engine, '--ip', $ip, '--port', [string]$port,
             '--forever', '--gui', '--event', 'Challenger', '--timeout', '60000', '--plies', '4')
if ($values.ContainsKey('json')) {
    # Resolve relative JSON paths against the directory where the user invoked this script.
    $jsonName = [string]$values['json']
    $jsonFull = [IO.Path]::GetFullPath((Join-Path (Get-Location).Path $jsonName))
    $jsonParent = Split-Path -Parent $jsonFull
    if (-not (Test-Path -LiteralPath $jsonParent -PathType Container)) {
        Fail "El directorio del JSON no existe: '$jsonParent'."
    }
    $cliArgs += @('--json', $jsonFull)
}

if ($engine -eq 'stockfish') {
    $stockfish = $null
    if ($values.ContainsKey('stockfish')) {
        $stockfish = $values['stockfish']
        $stockfishCmd = Get-Command -Name $stockfish -ErrorAction SilentlyContinue
        if ($null -ne $stockfishCmd -and $stockfishCmd.Source) {
            $stockfish = $stockfishCmd.Source
        }
        if (-not (Test-Path -LiteralPath $stockfish -PathType Leaf)) {
            Fail "No se encontro el ejecutable Stockfish: '$stockfish'."
        }
    } else {
        $stockfishCmd = Get-Command -Name 'stockfish.exe' -ErrorAction SilentlyContinue
        if ($null -eq $stockfishCmd) {
            $stockfishCmd = Get-Command -Name 'stockfish' -ErrorAction SilentlyContinue
        }
        if ($null -ne $stockfishCmd -and $stockfishCmd.Source -and
            (Test-Path -LiteralPath $stockfishCmd.Source -PathType Leaf)) {
            $stockfish = $stockfishCmd.Source
        }
        if (-not $stockfish) {
            $repoRoot = Split-Path -Parent $projectRoot
            $repoParent = Split-Path -Parent $repoRoot
            $candidates = @(
                (Join-Path $repoParent 'stockfish/stockfish.exe'),
                (Join-Path $repoRoot 'stockfish/stockfish.exe')
            )
            foreach ($candidate in $candidates) {
                if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                    $stockfish = $candidate
                    break
                }
            }
        }
        if (-not $stockfish) {
            Fail 'Stockfish no fue encontrado (PATH ni ubicaciones convencionales). Use --stockfish RUTA.'
        }
    }
    $cliArgs += @('--stockfish', $stockfish, '--stockfish-movetime', '2000')
}

Write-Host "Challenger v1.0.0: engine=$engine destino=${ip}:${port}" -ForegroundColor Cyan
if ($values.ContainsKey('json')) { Write-Host "Estadisticas JSON: $jsonFull" }
if ($engine -eq 'stockfish') { Write-Host "Ejecutable Stockfish: $stockfish" }

$oldPythonPath = $env:PYTHONPATH
$exitCode = 1
try {
    $env:PYTHONPATH = (@($validRoots) + @($oldPythonPath) | Where-Object { $_ }) -join [IO.Path]::PathSeparator
    Push-Location -LiteralPath $PSScriptRoot
    try {
        & $python @cliArgs
        $exitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }
} finally {
    $env:PYTHONPATH = $oldPythonPath
}
if ($null -eq $exitCode) { $exitCode = 1 }
exit [int]$exitCode
