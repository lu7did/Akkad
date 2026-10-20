# Sargon-NNUE v0.6.110 - Ejemplo concreto de invocación del pipeline genérico.
# Guardar este archivo en scripts/run_lex.ps1. Rutas relativas a scripts/.
$ErrorActionPreference = 'Stop'
$nombre = 'lex'
$muestraPorcentaje = 20.0
$evaluarSargon = $true
$evaluarStockfish = $true
$evaluarResult = $true
$usarMuestraExistente = $false
$omitirImportacion = $false

$parametros = @{
    Name = $nombre
    Python = 'C:\Users\pedro\ufasta\Scripts\python.exe'
    PgnPattern = '..\data\pgn\*.pgn'
    ImportPb = "..\data\pb\$nombre.pb"
    SamplePb = "..\data\pb\${nombre}_sample.pb"
    RunDir = "..\data\runs\$nombre"
    SamplePercent = $muestraPorcentaje
    Seed = 314159
    Sargon = $evaluarSargon
    Stockfish = $evaluarStockfish
    Result = $evaluarResult
    ReuseSample = $usarMuestraExistente
    SkipImport = $omitirImportacion
    StockfishPath = 'C:\Users\pedro\github\bobby\stockfish\stockfish.exe'
    StockfishDepth = 10
    StockfishThreads = 4
    ResultSmoothing = 0.15
    WeightClassic = 0.30
    WeightStockfish = 0.50
    WeightResult = 0.20
    Validation = 10.0
    Epochs = 30
    LearningRate = 0.001
    Scheduler = 'plateau'
    Patience = 3
    Gamma = 0.5
    MinLr = 0.00001
    BatchSize = 64
    Optimizer = 'adamw'
    Device = 'auto'
}
& (Join-Path $PSScriptRoot 'sargon_pipeline.ps1') @parametros
if (-not $?) { throw 'Falló el pipeline LEX' }
