
# ============================================================
# SARGON-NNUE - ENTRENAMIENTO LEX
# ============================================================

$Pipeline = Join-Path $PSScriptRoot "..\sargon_pipeline.ps1"

$Python = "C:\Users\pedro\ufasta\Scripts\python.exe"
$StockfishExe = "C:\Users\pedro\github\bobby\stockfish\stockfish.exe"
$PgnPath = "..\..\data\pgn\lex\*.pgn"

$Master = "..\..\data\pb\lex.pb"
$Sample = "..\..\data\pb\lex_sample.pb"
$Run = "..\..\data\runs\lex"

$ErrorActionPreference = "Stop"

# ------------------------------------------------------------
# 1. IMPORTAR PGN - ACUMULATIVO
# ------------------------------------------------------------

& $Pipeline -Stage import `
    -Python $Python `
    -PgnPattern $PgnPath `
    -ImportPb $Master

if ($LASTEXITCODE -ne 0) { throw "Error importando PGN" }

# ------------------------------------------------------------
# 2. EXTRAER MUESTRA - 20% DE PARTIDAS COMPLETAS
# ------------------------------------------------------------

& $Pipeline -Stage sample `
    -Python $Python `
    -ImportPb $Master `
    -SamplePb $Sample `
    -SamplePercent 20 `
    -Seed 314159

if ($LASTEXITCODE -ne 0) { throw "Error extrayendo muestra" }

# ------------------------------------------------------------
# 3. VALORIZADOR SARGON
# ------------------------------------------------------------

& $Pipeline -Stage evaluate `
    -Python $Python `
    -SamplePb $Sample `
    -Method sargon

if ($LASTEXITCODE -ne 0) { throw "Error valorizando con Sargon" }

# ------------------------------------------------------------
# 4. VALORIZADOR STOCKFISH
# ------------------------------------------------------------

& $Pipeline -Stage evaluate `
    -Python $Python `
    -SamplePb $Sample `
    -Method stockfish `
    -StockfishPath $StockfishExe `
    -StockfishDepth 10 `
    -StockfishThreads 4

if ($LASTEXITCODE -ne 0) { throw "Error valorizando con Stockfish" }

# ------------------------------------------------------------
# 5. VALORIZADOR RESULTADO SUAVIZADO
# ------------------------------------------------------------

& $Pipeline -Stage evaluate `
    -Python $Python `
    -SamplePb $Sample `
    -Method result `
    -ResultSmoothing 0.15

if ($LASTEXITCODE -ne 0) { throw "Error valorizando resultados" }

# ------------------------------------------------------------
# 6. AUDITORIA DE LA BASE
# ------------------------------------------------------------

& $Pipeline -Stage audit `
    -Python $Python `
    -SamplePb $Sample `
    -AuditJson "$Run\audit.json" `
    -AuditCsv "$Run\audit.csv" `
    -Validation 10 `
    -Seed 314159

if ($LASTEXITCODE -ne 0) { throw "Error en auditoria" }


Write-Host "Entrenamiento LEX completado" -ForegroundColor Green

