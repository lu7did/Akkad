# picoSargon compact 6-bit NNUE training genesis. All paths are anchored to this script.
param(
    [ValidateRange(1,4)][int]$mon = 1,
    [string]$database = 'C:\Users\pedro\github\Bobby\Chess_History_pb\picoAlpha\sample_history.pb',
    [string]$network = 'sneezy',
    [int]$sample = 100000,
    [double]$validation = 20,
    [double]$lr = 0.0001,
    [double]$lrmin = 0.0000001,
    [int]$epoch = 20,
    [int]$qatEpoch = 5,
    [double]$qatLr = 0.05,
    [double]$qatLrmin = 0.005,
    [int]$batch = 256,
    [int]$seed = 2026,
    [string]$python = 'python',
    [string]$referenceBin = '' # Blank = picoSargon/assets/grumpy.bin; existing file read-only
)
$ErrorActionPreference = 'Stop'
# Windows PowerShell 5.1 requires UTF-8 BOM to read emoji literals correctly.
try {
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
    $OutputEncoding = [Console]::OutputEncoding
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PYTHONUTF8 = '1'
} catch { }

$trainDir = $PSScriptRoot
$root = (Resolve-Path (Join-Path $trainDir '..\..')).Path
$assets = Join-Path $root 'assets'
$data = Join-Path $root 'data'
if (-not $database) { $database = Join-Path (Split-Path $root -Parent) 'picoAlpha\data\history.pb' }
# REFERENCE BINARY — used ONLY in Audit.py (never during TRAIN/VERIFY/VALID)
$initial = if ($referenceBin) { $referenceBin } else { Join-Path $assets 'grumpy.bin' }
$best = Join-Path $assets ("{0}_best_quant.pt" -f $network)
$outputBin = Join-Path $assets ("{0}.bin" -f $network)
$outputHeader = Join-Path $assets ("{0}.h" -f $network)
$manifest = Join-Path $data ("{0}_split.json" -f $network)
$audit = Join-Path $data ("{0}_audit.json" -f $network)
New-Item -ItemType Directory -Force $assets,$data | Out-Null
Write-Host "⚙️ Salida de entrenamiento: $best"
Write-Host "⚙️ Salida binaria: $outputBin"
$MON = $mon
function Invoke-Step([int]$number, [string]$title, [string[]]$params) {
    if ($MON -ne $number) { return }
    Write-Host "⚙️ Paso $number - $title (MON=$MON)"
    & $python @params
    if ($LASTEXITCODE -ne 0) { throw "Paso $number falló ($LASTEXITCODE). MON permanece en $MON" }
    $script:MON = $number + 1
    Write-Host "✅ Paso $number completo; MON=$script:MON"
}
Invoke-Step 1 'TRAIN' @((Join-Path $trainDir 'train.py'), '--in', $database, '--sample', "$sample", '--validation', "$validation", '--lr', "$lr", '--lrmin', "$lrmin", '--epoch', "$epoch", '--qat-epoch', "$qatEpoch", '--qat-lr', "$qatLr", '--qat-lrmin', "$qatLrmin", '--batch', "$batch", '--seed', "$seed", '--name', $network, '--assets', $assets, '--data', $data)
Invoke-Step 2 'EXPORT' @((Join-Path $trainDir 'export.py'), '--in', $best, '--bin', $outputBin, '--include', $outputHeader, '--symbol', "${network}_network")
if ($MON -eq 3) {
    if (-not (Test-Path -LiteralPath $initial -PathType Leaf)) {
        throw "No se encontró la RED DE REFERENCIA para AUDIT: $initial"
    }
    Write-Host "⚙️ Referencia de AUDIT (--referenceBin): $initial [READ ONLY]"
}
Invoke-Step 3 'AUDIT' @((Join-Path $trainDir 'Audit.py'), '--in', $outputBin, '--bin', $initial, '--split', $manifest, '--db', $database, '--out', $audit)
Write-Host "✅ Genesis terminado MON=$MON output=$outputBin"
