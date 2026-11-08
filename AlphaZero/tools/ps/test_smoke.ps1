# AlphaZero X86 native UCI smoke test v0.2.9
param(
 [string]$Weights = $env:ALPHAZERO_WEIGHTS,
 [string]$Brain = 'emma',
 [ValidateRange(1,10000000)][int]$Nodes = 8,
 [ValidateRange(1,256)][int]$Cores = 1,
 [string]$Python = 'python',
 [ValidateSet('eigen','onnx-dml')][string]$Backend = 'onnx-dml',
 [switch]$Help
)
$ErrorActionPreference = 'Stop'
if ($Help) { Write-Host 'test_smoke.ps1 [-Weights FILE] [-Brain ID] [-Nodes N] [-Cores N] [-Python EXE] [-Backend eigen|onnx-dml] [-Help]'; exit 0 }
$root = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$exe = Join-Path $root 'AlphaZero/X86/build/AlphaZero.exe'
$test = Join-Path $root 'AlphaZero/tests/uci_transport_smoke.py'
if (-not $Weights) {
  $brainsFile = Join-Path $root 'Sargon-NNUE/etc/brains/brains.json'
  if (Test-Path $brainsFile) {
    $brains = Get-Content $brainsFile -Raw | ConvertFrom-Json
    $candidate = $brains.brains.$Brain.'lc0-weights'
    if ($candidate -is [string]) { $Weights = $candidate }
    elseif ($candidate) { $Weights = $candidate.windows }
    if ($Weights -and -not [IO.Path]::IsPathRooted($Weights)) {
      $Weights = [IO.Path]::GetFullPath((Join-Path $root "Sargon-NNUE/$Weights"))
    }
  }
}
if (-not (Test-Path $exe)) { throw "Missing engine: $exe. Run tools/ps/build.ps1" }
if (-not $Weights -or -not (Test-Path $Weights)) { throw "Missing weights. Supply -Weights FILE or ALPHAZERO_WEIGHTS." }
if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) { throw "Missing Python: $Python" }
& $Python $test --engine $exe --weights $Weights --backend $Backend --nodes $Nodes --cores $Cores
if ($LASTEXITCODE -ne 0) { throw "UCI smoke test failed (exit $LASTEXITCODE)" }
