# Akkad / picoAlpha - Genesis training orchestrator v0.1.6
# Execute from any directory. Edit defaults in the CONFIGURATION block.
[CmdletBinding()]
param(
    [Alias('h')][switch]$Help,
    [Alias('-mon')][Nullable[int]]$Mon = $null,
    [string]$HistoryDir = 'C:\Users\pedro\github\Bobby\Chess_History_pb\picoAlpha',
    [string]$PgnPattern = 'C:\Users\pedro\github\Bobby\Chess_History_pb\pgn\*.pgn',
    [ValidateRange(0,100)][int]$Sample = 20,
    [int]$Seed = 42,
    [string]$Engine = 'stockfish.exe',
    [string]$EngineArgs = '',
    [ValidateRange(1,2147483647)][int]$Depth = 10,
    [Nullable[int]]$Nodes = $null,
    [ValidateRange(0,100)][int]$Validate = 20,
    [ValidateRange(1,2147483647)][int]$Epoch = 20,
    [ValidateSet('AdamW','Adam','SGD','RMSprop')][string]$Method = 'AdamW',
    [double]$Lr = 0.005,
    [double]$LrMin = 0.0001,
    [ValidateRange(1,2147483647)][int]$Batch = 64,
    [ValidateSet('cpu','cuda','xpu')][string]$Device = 'cpu',
    [double]$ValueWeight = 2.0,
    [string]$AssetsDir = '',
    [string]$Namespace = 'picoalpha_nnue'
)

$ErrorActionPreference = 'Stop'
# Windows console: preserve UTF-8 emoji and progress output when supported.
try {
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
    $OutputEncoding = [Console]::OutputEncoding
} catch { }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = [System.IO.Path]::GetFullPath((Join-Path $ScriptDir '..\..'))

if ($Help) {
    Write-Host 'Genesis pipeline picoAlpha v0.1.6 - seis pasos secuenciales MON=0..5'
    Write-Host 'Uso: .\run_genesis.ps1 -Mon 0..5 (o --mon 0..5) [-HistoryDir PATH] [-PgnPattern GLOB] ... [-Help]'
    Write-Host 'Todos los parametros pueden modificarse al invocar el script:'
    Write-Host '  -Mon N / --mon N   OBLIGATORIO: paso inicial 0..5; -Help no lo requiere'
    Write-Host '  -HistoryDir PATH    Base de datos history.pb y sample_history.pb (directorio)'
    Write-Host '  -PgnPattern GLOB    Archivos PGN para loader.py'
    Write-Host '  -Sample N           Porcentaje de partidas muestreadas (default 20)'
    Write-Host '  -Seed N             Semilla de muestreo y entrenamiento (default 42)'
    Write-Host '  -Engine PATH        Ejecutable Stockfish (default stockfish.exe)'
    Write-Host '  -EngineArgs STRING  Argumentos adicionales Stockfish (default vacio)'
    Write-Host '  -Depth N            Profundidad Stockfish (default 10)'
    Write-Host '  -Nodes N            Limite opcional de nodos para Stockfish'
    Write-Host '  -Validate N         Porcentaje validacion (default 20)'
    Write-Host '  -Epoch N            Epocas PyTorch (default 20)'
    Write-Host '  -Method NAME        AdamW|Adam|SGD|RMSprop (default AdamW)'
    Write-Host '  -Lr N               Learning rate inicial (default 0.005)'
    Write-Host '  -LrMin N            Learning rate minimo (default 0.0001)'
    Write-Host '  -Batch N            Tamaño de lote (default 64)'
    Write-Host '  -Device NAME        cpu|cuda|xpu (default cpu)'
    Write-Host '  -ValueWeight N      Peso del loss valor (default 2.0)'
    Write-Host '  -AssetsDir PATH     Carpeta de activos (default picoAlpha/assets)'
    Write-Host '  -Namespace NAME     Namespace del header C++ (default picoalpha_nnue)'
    Write-Host 'Paso 0 sobrescribe history.pb; paso 2 sobrescribe sample_history.pb.'
    return
}

if ($null -eq $Mon -or $Mon -lt 0 -or $Mon -gt 5) {
    throw 'Falta -Mon N obligatorio (N=0..5). Ejemplo: .\run_genesis.ps1 -Mon 3. Use -Help para opciones.'
}

if ([string]::IsNullOrWhiteSpace($AssetsDir)) { $AssetsDir = Join-Path $ProjectDir 'assets' }
$HistoryDir = [System.IO.Path]::GetFullPath($HistoryDir)
$AssetsDir = [System.IO.Path]::GetFullPath($AssetsDir)
$HistoryDb = Join-Path $HistoryDir 'history.pb'
$SampleDb = Join-Path $HistoryDir 'sample_history.pb'
$CheckpointDir = Join-Path $AssetsDir 'checkpoints'
$BestPt = Join-Path $CheckpointDir 'best.pt'
$CppHeader = Join-Path $AssetsDir 'picoalpha_nnue_weights.hpp'
$BestInt8 = Join-Path $CheckpointDir 'best_int8.pt'

# MON is the next step permitted to execute. Advance only after an exit code of zero.
$MON = [int]$Mon

function Assert-GenesisDb {
    param([string]$Path, [int]$MinGames = 0)
    # The verifier never creates a missing SQLite file.
    & python (Join-Path $ScriptDir 'verify_database.py') --in $Path --min-games ([string]$MinGames)
    if ($LASTEXITCODE -ne 0) {
        throw "Base de datos no valida en ruta: $Path (MON=$script:MON)"
    }
}

function Invoke-GenesisStep {
    param(
        [Parameter(Mandatory=$true)][int]$Number,
        [Parameter(Mandatory=$true)][string]$Purpose,
        [Parameter(Mandatory=$true)][string]$Program,
        [AllowEmptyCollection()][string[]]$Arguments = @(),
        [string]$VerifyDb = '',
        [int]$MinGames = 0
    )
    if ($script:MON -ne $Number) { return }
    $programPath = Join-Path $ScriptDir $Program
    if (-not (Test-Path -LiteralPath $programPath -PathType Leaf)) {
        throw "Falta el programa requerido: $programPath (MON=$script:MON)"
    }
    Write-Host ("⚙️ Paso {0:D2} - {1}" -f $Number, $Purpose)
    Write-Host ("   Programa: {0}" -f $programPath)
    if ($Number -eq 0 -or $Number -eq 1 -or $Number -eq 2) {
        Write-Host ("   Base de entrada/historico: {0}" -f $HistoryDb)
        Write-Host ("   Base de salida/muestra:   {0}" -f $SampleDb)
    }
    $global:LASTEXITCODE = 0
    try {
        # Direct Python invocation: no wrapper defaults can override absolute paths.
        & python $programPath @Arguments
        $invocationSucceeded = $?
        $code = $LASTEXITCODE
        if (-not $invocationSucceeded -or $null -eq $code -or $code -ne 0) {
            throw "Python termino con codigo $code"
        }
        if (-not [string]::IsNullOrEmpty($VerifyDb)) {
            Assert-GenesisDb -Path $VerifyDb -MinGames $MinGames
        }
    } catch {
        throw ("Paso {0:D2} fallido; MON permanece en {1}. {2}" -f $Number, $script:MON, $_.Exception.Message)
    }
    $script:MON++
}

New-Item -ItemType Directory -Force -Path $HistoryDir, $CheckpointDir | Out-Null
Write-Host ("Genesis starting MON={0} (steps before this value will be skipped)" -f $MON)
Write-Host ("Genesis paths: CWD={0}" -f (Get-Location).Path)
Write-Host ("Genesis paths: script={0}" -f $ScriptDir)
Write-Host ("Genesis paths: PGN={0}" -f $PgnPattern)
Write-Host ("Genesis: history={0} sample={1} checkpoints={2} best={3}" -f $HistoryDb, $SampleDb, $CheckpointDir, $BestPt)

Invoke-GenesisStep -Number 0 -Purpose 'Inicializar historico history.pb' -Program 'create.py' -Arguments @('--out', $HistoryDb) -VerifyDb $HistoryDb
Invoke-GenesisStep -Number 1 -Purpose 'Importar partidas PGN al historico' -Program 'loader.py' -Arguments @('--in', $PgnPattern, '--out', $HistoryDb) -VerifyDb $HistoryDb -MinGames 1
# Early diagnosis rather than letting sampler open a nonexistent path.
if ($MON -eq 2) { Assert-GenesisDb -Path $HistoryDb -MinGames 1 }
Invoke-GenesisStep -Number 2 -Purpose 'Crear muestra sample_history.pb' -Program 'sampler.py' -Arguments @('--in', $HistoryDb, '--out', $SampleDb, '--sample', [string]$Sample, '--seed', [string]$Seed) -VerifyDb $SampleDb
# Skip --args entirely when empty: empty-string elements cause PowerShell binding errors.
$teacherArgs = @('--in', $SampleDb, '--engine', $Engine, '--depth', [string]$Depth)
if (-not [string]::IsNullOrWhiteSpace($EngineArgs)) { $teacherArgs += @('--args', $EngineArgs) }
if ($null -ne $Nodes) { $teacherArgs += @('--nodes', [string]$Nodes) }
if ($MON -eq 3) { Assert-GenesisDb -Path $SampleDb -MinGames 1 }
Invoke-GenesisStep -Number 3 -Purpose 'Etiquetar politica y valor con Stockfish' -Program 'teacher.py' -Arguments $teacherArgs
if ($MON -eq 4) { Assert-GenesisDb -Path $SampleDb -MinGames 1 }
Invoke-GenesisStep -Number 4 -Purpose 'Entrenar NNUE y generar checkpoints PyTorch' -Program 'train.py' -Arguments @('--in', $SampleDb, '--out', $CheckpointDir, '--validate', [string]$Validate, '--epoch', [string]$Epoch, '--method', $Method, '--lr', [string]$Lr, '--lr_min', [string]$LrMin, '--batch', [string]$Batch, '--seed', [string]$Seed, '--device', $Device, '--value_weight', [string]$ValueWeight)
if ($MON -eq 5 -and -not (Test-Path -LiteralPath $BestPt -PathType Leaf)) {
    throw "Paso 05 no puede comenzar: no existe el checkpoint $BestPt"
}
Invoke-GenesisStep -Number 5 -Purpose 'Exportar INT8 a C++ y checkpoint PyTorch' -Program 'export.py' -Arguments @('--in', $BestPt, '--out', $CppHeader, '--int8', $BestInt8, '--namespace', $Namespace)
if ($MON -eq 6) { Write-Host ("Genesis completado: MON={0}; best={1}; header={2}; int8={3}" -f $MON, $BestPt, $CppHeader, $BestInt8) }
