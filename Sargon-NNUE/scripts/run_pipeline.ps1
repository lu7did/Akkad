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
#* run_pipeline.ps1
#* Runs the processing pipeline for Sargon-NNUE
#=================================================================================================================*
# ============================================================
# SARGON-NNUE - ENTRENAMIENTO {NetName} v0.6.121
# Importar, muestrear, cinco valorizaciones, auditar y entrenar.
# Cuatro fuentes de TRAIN: Sargon, Stockfish, resultado y LC0-UCI.
# AlphaZero-MCTS es una anotación experimental INDEPENDIENTE.
# ============================================================

$Pipeline = Join-Path $PSScriptRoot 'sargon_pipeline.ps1'

$Python = 'C:\Users\pedro\ufasta\Scripts\python.exe'
$StockfishExe = 'C:\Users\pedro\github\bobby\stockfish\stockfish.exe'
[string]$Name = 'zod'
$NetName = $Name
$PgnPath = '..\..\pgn\zod\*.pgn'
$Master  = '..\data\pb\'+$Name+'.pb'
$Sample  = '..\data\pb\'+$Name+'_sample.pb'
$Run     = '..\data\runs\'+$Name

$Lc0Exe = '..\..\..\lc0\lc0.exe'
$Lc0Weights = '..\data\runs\lczero\t1-256x10-distilled-swa-2432500.pb.gz'
$Lc0Backend = 'onnx-dml'               # CPU: 'blas'
$Lc0BackendOptions = 'gpu=0'           # CPU BLAS: ''

$ErrorActionPreference = 'Stop'

# ------------------------------------------------------------
# 0. Configuración de la corrida
# ------------------------------------------------------------
Write-Host 'Definiendo parámetros ($NetName)' -ForegroundColor Green
Write-Host 'Custom re-entering' -ForegroundColor Green


$build = $false
$sampling = $false
$classic = $false
$stockfish = $false
$result = $false
$leela = $false
$MCTS= $true
$train = $true

# ------------------------------------------------------------
# 1. IMPORTAR PGN - ACUMULATIVO
# ------------------------------------------------------------
if ($build) {
Write-Host 'Importar PGN ($NetName)' -ForegroundColor Green

& $Pipeline -Stage import `
    -Python $Python `
    -PgnPattern $PgnPath `
    -ImportPb $Master
if (-not $? -or $LASTEXITCODE -ne 0) { throw 'Error importando PGN' }

}

# ------------------------------------------------------------
# 2. EXTRAER MUESTRA - 20% DE PARTIDAS COMPLETAS
# ------------------------------------------------------------
if ($sampling) {

Write-Host 'Sample ($NetName) {$Master $Sample}' -ForegroundColor Green

& $Pipeline -Stage sample `
    -Python $Python `
    -ImportPb $Master `
    -SamplePb $Sample `
    -SamplePercent 20 `
    -Seed 314159
if (-not $? -or $LASTEXITCODE -ne 0) { throw 'Error extrayendo muestra' }
}
# ------------------------------------------------------------
# 3. VALORIZADOR SARGON CLASICO
# ------------------------------------------------------------
if ($classic) {
Write-Host 'Valorizar ($NetName) {Classic}' -ForegroundColor Green

& $Pipeline -Stage evaluate `
    -Python $Python `
    -SamplePb $Sample `
    -Method sargon
if (-not $? -or $LASTEXITCODE -ne 0) { throw 'Error valorizando con Sargon' }
}
# ------------------------------------------------------------
# 4. VALORIZADOR STOCKFISH
# ------------------------------------------------------------
if ($stockfish) {
Write-Host 'Valorizar ($NetName) {StockFish}' -ForegroundColor Green

& $Pipeline -Stage evaluate `
    -Python $Python `
    -SamplePb $Sample `
    -Method stockfish `
    -StockfishPath $StockfishExe `
    -StockfishDepth 10 `
    -StockfishThreads 4
if (-not $? -or $LASTEXITCODE -ne 0) { throw 'Error valorizando con Stockfish' }
}
# ------------------------------------------------------------
# 5. VALORIZADOR RESULTADO SUAVIZADO
# ------------------------------------------------------------
if ($result) {
Write-Host 'Valorizar ($NetName) {Resultado}' -ForegroundColor Green

& $Pipeline -Stage evaluate `
    -Python $Python `
    -SamplePb $Sample `
    -Method result `
    -ResultSmoothing 0.15
if (-not $? -or $LASTEXITCODE -ne 0) { throw 'Error valorizando resultados' }
}
# ------------------------------------------------------------
# 6. VALORIZADOR LC0.EXE UCI (WDL POR BUSQUEDA INTERNA)
# ------------------------------------------------------------
if ($leela) {
Write-Host 'Valorizar ($NetName) {Leela}' -ForegroundColor Green

& $Pipeline -Stage evaluate `
    -Python $Python `
    -SamplePb $Sample `
    -Method lc0-uci `
    -Lc0Exe $Lc0Exe `
    -Lc0Weights $Lc0Weights `
    -Lc0Backend $Lc0Backend `
    -Lc0BackendOptions $Lc0BackendOptions `
    -Lc0UciNodes 800 `
    -Lc0UciThreads 1 `
    -Lc0History allow-incomplete
if (-not $? -or $LASTEXITCODE -ne 0) { throw 'Error valorizando con LC0-UCI' }
}
# ------------------------------------------------------------
# 7. VALORIZADOR ALPHAZERO-MCTS PROPIO (Q DE LA MEJOR JUGADA)
#    Fuente adicional para estudio
# ------------------------------------------------------------
if ($MCTS) {
Write-Host 'Valorizar ($NetName) {MCTS}' -ForegroundColor Green

& (Join-Path $PSScriptRoot 'sargon_az_mcts_valor.ps1') `
    -Python $Python `
    -InputPb $Sample `
    -Weights $Lc0Weights `
    -Backend $Lc0Backend `
    -BackendOptions $Lc0BackendOptions `
    -History allow-incomplete `
    -Simulations 128 `
    -Cpuct 1.5 `
    -TmaxMs 0
if (-not $? -or $LASTEXITCODE -ne 0) { throw 'Error valorizando con AlphaZero-MCTS' }
}
# ------------------------------------------------------------
# 8. AUDITORIA DE LA BASE
# ------------------------------------------------------------
if ($audit) {
Write-Host 'Audit ($NetName) {$Sample}' -ForegroundColor Green

& $Pipeline -Stage audit `
    -Python $Python `
    -SamplePb $Sample `
    -AuditJson "$Run\audit.json" `
    -AuditCsv "$Run\audit.csv" `
    -Validation 10 `
    -Seed 314159
if (-not $? -or $LASTEXITCODE -ne 0) { throw 'Error en auditoria' }
}
# ------------------------------------------------------------
# 9. ENTRENAMIENTO PYTORCH - CUATRO MAESTROS
#    El lanzador individual protege los checkpoints y admite repeticiones.
# ------------------------------------------------------------
if ($train) {

Write-Host 'Audit ($NetName) {$Sample}' -ForegroundColor Green
& (Join-Path $PSScriptRoot 'run_pipeline_train.ps1') `
    -Python $Python `
    -SamplePb $Sample `
    -RunDir $Run `
    -WeightClassic 0.00 `
    -WeightStockfish 0.00 `
    -WeightResult 0.00 `
    -WeightLc0 1.00 `
    -Lc0Source uci `
    -Epochs 10 `
    -BatchSize 64 `
    -Validation 10 `
    -MovePercent 20 `
    -Seed 314159 `
    -Device auto `
    -Optimizer adamw `
    -LearningRate 0.0001 `
    -Scheduler plateau `
    -Patience 3 `
    -Gamma 0.5 `
    -MinLr 0.00001
if (-not $? -or $LASTEXITCODE -ne 0) { throw 'Error en entrenamiento' }
}
Write-Host 'Entrenamiento $NetName completado' -ForegroundColor Green
