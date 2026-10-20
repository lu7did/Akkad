# Sargon-NNUE v0.6.107 - CONFIGURACIÓN DE INVOCACIÓN
# Editar estas rutas relativas a la raíz del proyecto o utilizar rutas absolutas.
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'sargon_pipeline.ps1') `
    -Python 'C:\Users\pedro\ufasta\Scripts\python.exe' `
    -PgnPattern 'data\pgn\Fis*.pgn' `
    -ImportPb 'data\pb\partidas_maestro.pb' `
    -SamplePb 'data\pb\muestra_v0.6.107.pb' `
    -TrainingPb 'data\pb\etiquetado_v0.6.107.pb' `
    -Checkpoint 'data\nnue\sargon_v0.6.107_best.npz' `
    -TrainDir 'data\pipeline\entrenamiento_v0.6.107' `
    -AuditJson 'data\pipeline\auditoria_v0.6.107.json' `
    -AuditCsv 'data\pipeline\auditoria_v0.6.107.csv' `
    -SamplePercent 10 `
    -Seed 314159 `
    -Validation 10 `
    -StockfishPath 'C:\Users\pedro\github\bobby\stockfish\stockfish.exe' `
    -StockfishDepth 10 `
    -StockfishThreads 1 `
    -ResultSmoothing 0.15 `
    -WeightClassic 0.3 `
    -WeightStockfish 0.5 `
    -WeightResult 0.2 `
    -Epochs 30 `
    -LearningRate 0.001 `
    -Scheduler 'plateau' `
    -Device 'xpu'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
