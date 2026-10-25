#*================================================================================================================*
#* Proyecto sargon-nnue
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* run_pipeline_prepare.ps1
#* Runs the processing pipeline for Sargon-NNUE (preparation stage)
#=================================================================================================================*
# Sargon-NNUE + LC0 - Preparacion LEX, v0.6.119
# Etapas independientes; NO ejecuta entrenamiento.
# Se apoya en scripts/sargon_pipeline.ps1 de la integracion LC0 v0.6.117 o posterior.
# Ejecutar desde cualquier directorio: pwsh -File ./scripts/run_pipeline_prepare.ps1
[CmdletBinding()]
param(
    [string]$Python = '',
    [string]$PgnPath = '..\data\pgn\lex\*.pgn',
    [string]$MasterPb = '..\data\pb\lex.pb',
    [string]$SamplePb = '..\data\pb\lex_sample.pb',
    [string]$RunDir = '..\data\runs\lex',
    [double]$SamplePercent = 20.0,
    [int]$Seed = 314159,
    [string]$StockfishExe = 'C:\Users\pedro\github\bobby\stockfish\stockfish.exe',
    [int]$StockfishDepth = 10,
    [int]$StockfishThreads = 4,
    [double]$ResultSmoothing = 0.15,
    [string]$Lc0Weights = '..\data\lc0\model.pb.gz',
    [ValidateSet('neural','uci')][string]$Lc0Source = 'uci',
    [string]$Lc0Exe = '..\data\lc0\lc0.exe',
    [int]$Lc0UciNodes = 800,
    [int]$Lc0UciThreads = 1,
    [string]$Lc0Backend = 'auto',
    [string]$Lc0BackendOptions = '',
    [ValidateSet('strict', 'allow-incomplete')][string]$Lc0History = 'allow-incomplete',
    [double]$Validation = 10.0
)

$ErrorActionPreference = 'Stop'
$pipeline = Join-Path $PSScriptRoot 'sargon_pipeline.ps1'

try {
    if (-not (Test-Path -LiteralPath $pipeline -PathType Leaf)) {
        throw "No se encontro el pipeline: $pipeline"
    }
    # No ejecutar etapas costosas con un pipeline anterior que no admita LC0.
    if (-not (Select-String -LiteralPath $pipeline -Pattern "'lc0'" -Quiet)) {
        throw 'El sargon_pipeline.ps1 instalado no incorpora LC0. Aplique primero v0.6.117.'
    }
    if ($SamplePercent -le 0 -or $SamplePercent -gt 100) {
        throw 'SamplePercent debe estar en (0,100].'
    }
    if ($Validation -le 0 -or $Validation -ge 100) {
        throw 'Validation debe estar en (0,100).'
    }
    if ([string]::IsNullOrWhiteSpace($Python)) { $Python = $env:SARGON_PYTHON }
    if ([string]::IsNullOrWhiteSpace($Python)) {
        $windowsPython = 'C:\Users\pedro\ufasta\Scripts\python.exe'
        if (($IsWindows -or $env:OS -eq 'Windows_NT') -and (Test-Path -LiteralPath $windowsPython -PathType Leaf)) {
            $Python = $windowsPython
        } elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
            $Python = 'python3'
        } else {
            $Python = 'python'
        }
    }
    if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
        throw "Interprete Python no disponible: $Python"
    }
    if ([string]::IsNullOrWhiteSpace($Lc0Weights)) { throw 'Indique -Lc0Weights.' }
    $resolvedWeights = if ([IO.Path]::IsPathRooted($Lc0Weights)) {
        [IO.Path]::GetFullPath($Lc0Weights)
    } else {
        [IO.Path]::GetFullPath((Join-Path $PSScriptRoot $Lc0Weights))
    }
    if (-not (Test-Path -LiteralPath $resolvedWeights -PathType Leaf)) {
        throw "Red LC0 no encontrada: $resolvedWeights. Indique -Lc0Weights <ruta>."
    }
    $stockfish = $StockfishExe
    if (-not (Test-Path -LiteralPath $stockfish -PathType Leaf)) {
        $stockfishCmd = Get-Command $stockfish -ErrorAction SilentlyContinue
        if ($stockfishCmd) {
            $stockfish = $stockfishCmd.Source
        } else {
            throw "Stockfish no encontrado: $StockfishExe. Indique -StockfishExe <ruta>."
        }
    }

    # Las rutas relativas se interpretan desde scripts/, como en el pipeline original.
    $sampleFile = if ([IO.Path]::IsPathRooted($SamplePb)) {
        [IO.Path]::GetFullPath($SamplePb)
    } else {
        [IO.Path]::GetFullPath((Join-Path $PSScriptRoot $SamplePb))
    }
    $runDirectory = if ([IO.Path]::IsPathRooted($RunDir)) {
        [IO.Path]::GetFullPath($RunDir)
    } else {
        [IO.Path]::GetFullPath((Join-Path $PSScriptRoot $RunDir))
    }
    $auditJson = Join-Path $runDirectory 'audit.json'
    $auditCsv = Join-Path $runDirectory 'audit.csv'

    Write-Host '[0/6] Importacion acumulativa de PGN' -ForegroundColor Cyan
    & $pipeline -Stage import -Python $Python -PgnPattern $PgnPath -ImportPb $MasterPb
    if (-not $? -or $LASTEXITCODE -ne 0) { throw 'Fallo import de PGN.' }

    Write-Host '[1/6] Seleccion de partidas completas' -ForegroundColor Cyan
    if (Test-Path -LiteralPath $sampleFile -PathType Leaf) {
        Write-Warning "Se reutiliza la muestra existente: $sampleFile. Si agrego PGN al maestro, esa muestra NO incorpora automaticamente las nuevas partidas."
    } else {
        & $pipeline -Stage sample -Python $Python -ImportPb $MasterPb -SamplePb $SamplePb -SamplePercent $SamplePercent -Seed $Seed
        if (-not $? -or $LASTEXITCODE -ne 0) { throw 'Fallo sample de partidas.' }
    }

    Write-Host '[2/6] Etiquetas Sargon clasico' -ForegroundColor Cyan
    & $pipeline -Stage evaluate -Python $Python -SamplePb $SamplePb -Method sargon
    if (-not $? -or $LASTEXITCODE -ne 0) { throw 'Fallo Sargon clasico.' }

    Write-Host '[3/6] Etiquetas Stockfish' -ForegroundColor Cyan
    & $pipeline -Stage evaluate -Python $Python -SamplePb $SamplePb -Method stockfish -StockfishPath $stockfish -StockfishDepth $StockfishDepth -StockfishThreads $StockfishThreads
    if (-not $? -or $LASTEXITCODE -ne 0) { throw 'Fallo Stockfish.' }

    Write-Host '[4/6] Resultado de partida suavizado' -ForegroundColor Cyan
    & $pipeline -Stage evaluate -Python $Python -SamplePb $SamplePb -Method result -ResultSmoothing $ResultSmoothing
    if (-not $? -or $LASTEXITCODE -ne 0) { throw 'Fallo valor resultado.' }

    Write-Host '[5/6] Etiquetas LC0 WDL' -ForegroundColor Cyan
    if ($Lc0Source -eq 'uci') {
        $resolvedExe = if ([IO.Path]::IsPathRooted($Lc0Exe)) { [IO.Path]::GetFullPath($Lc0Exe) } else { [IO.Path]::GetFullPath((Join-Path $PSScriptRoot $Lc0Exe)) }
        if (-not (Test-Path -LiteralPath $resolvedExe -PathType Leaf)) { throw "LC0-UCI no encontrado: $resolvedExe" }
        & $pipeline -Stage evaluate -Python $Python -SamplePb $SamplePb -Method lc0-uci -Lc0Exe $resolvedExe -Lc0Weights $resolvedWeights -Lc0Backend $Lc0Backend -Lc0BackendOptions $Lc0BackendOptions -Lc0History $Lc0History -Lc0UciNodes $Lc0UciNodes -Lc0UciThreads $Lc0UciThreads
    } else {
        & $pipeline -Stage evaluate -Python $Python -SamplePb $SamplePb -Method lc0 -Lc0Weights $resolvedWeights -Lc0Backend $Lc0Backend -Lc0BackendOptions $Lc0BackendOptions -Lc0History $Lc0History
    }
    if (-not $? -or $LASTEXITCODE -ne 0) { throw 'Fallo LC0.' }

    Write-Host '[6/6] Auditoria de la muestra' -ForegroundColor Cyan
    # Solo se reemplazan informes de auditoria generados; nunca datos .pb ni checkpoints.
    New-Item -ItemType Directory -Path $runDirectory -Force | Out-Null
    foreach ($report in @($auditJson, $auditCsv)) {
        if (Test-Path -LiteralPath $report -PathType Leaf) {
            Remove-Item -LiteralPath $report -Force
        }
    }
    & $pipeline -Stage audit -Python $Python -SamplePb $SamplePb -AuditJson $auditJson -AuditCsv $auditCsv -Validation $Validation -Seed $Seed
    if (-not $? -or $LASTEXITCODE -ne 0) { throw 'Fallo auditoria.' }

    Write-Host "PREPARE completado. Dataset: $sampleFile" -ForegroundColor Green
    Write-Host 'El entrenamiento se ejecuta por separado con run_pipeline_train.ps1.' -ForegroundColor Green
} catch {
    Write-Error "PREPARE v0.6.119: $_"
    exit 1
}
