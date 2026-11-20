# picoGen binpack genetic genesis v0.1.39. Windows PowerShell 5.1 compatible.
# All artifacts are under picoGen/assets. Never reads/writes a SQLite database.
$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = [IO.Path]::GetFullPath((Join-Path $ScriptDir '..\..'))
$DefaultSource = Join-Path $env:USERPROFILE 'github\Bobby\Chess_History_pb\stockfish'
$Cfg = @{
  Mon = '0'; RunId = 'binpack-fp32-001';
  TrainBinpack = (Join-Path $DefaultSource 'test79-may2022-16tb7p-filter-v6-dd.min-mar2023.unmin.high-simple-eval-1k.min-v2.binpack');
  ValidBinpack = (Join-Path $DefaultSource 'test77-jan2022-2tb7p.high-simple-eval-1k.min-v2.binpack');
  TrainCount = '1000000'; ValidCount = '100000';
  TrainScan = '10000000'; ValidScan = '1000000';
  FitnessSample = '10000'; ValidationSample = '1000';
  Population = '50'; Generations = '100'; Seed = '42'; MutationSigma = '5';
  Python = 'python'; InstallRust = 'false'; Status = 'false'; ReuseCsvRun = ''
}
function Usage {
@'
Usage: .\run_genesis_binpack.ps1 [--mon 1..8] [--status] [options]
  --run-id ID             default binpack-fp32-001 (separate from old int16 run)
  --train-binpack PATH    T79 (.binpack) from Stockfish
  --valid-binpack PATH    T77 (.binpack), held-out validation
  --train-count N         default 1000000 CSV rows
  --valid-count N         default 100000 CSV rows
  --train-scan N          default 10000000 eligible T79 records to sample
  --valid-scan N          default 1000000 eligible T77 records to sample
  --fitness-sample N      default 10000 fixed T79 subset for every individual
  --validation-sample N   default 1000 fixed T77 subset
  --population N          default 30, same archived genetic operators
  --generations N         default 20
  --seed N                default 42
  --mutation-sigma N      Gaussian standard deviation, default 3 (both models)
  --reuse-csv-run ID      read previous T79/T77 CSV under picoGen/assets/ID
  --python COMMAND        default python
  --install-rust          explicitly install rustup with winget when absent
  --help
An explicit --mon N executes step N again even if it was completed before.
Without --mon the script resumes at MON.state and reuses existing checkpoints.
MON 1: prerequisites and reproducible run lock
MON 2: compile and test Rust binpack extractor (CPU only)
MON 3: T79 -> train.csv
MON 4: T77 -> validation.csv
MON 5: audit CSV, FEN, target perspective and independent splits
MON 6: PST FP32 Gaussian genetic training (archived evaluation factors)
MON 7: NNUE FP32 768x16 Gaussian genetic training
MON 8: independent T77 audit + metrics
MON 9: complete
No Bullet, MacOS, Metal, PyTorch, or SQLite training.
'@ | Write-Host
}
$Supplied = @{}
$Mapping = @{'mon'='Mon';'run-id'='RunId';'train-binpack'='TrainBinpack';'valid-binpack'='ValidBinpack';
 'train-count'='TrainCount';'valid-count'='ValidCount';'train-scan'='TrainScan';'valid-scan'='ValidScan';
 'fitness-sample'='FitnessSample';'validation-sample'='ValidationSample';
 'population'='Population';'generations'='Generations';'seed'='Seed';'python'='Python';
 'mutation-sigma'='MutationSigma';'reuse-csv-run'='ReuseCsvRun'}
for ($i=0;$i -lt $args.Count;$i++) {
  $token=[string]$args[$i];$key=$token.TrimStart('-').ToLowerInvariant()
  if ($token -notmatch '^--?[A-Za-z]') { throw "Unexpected argument: $token" }
  if ($key -eq 'help' -or $key -eq 'h') { Usage;exit 0 }
  if ($key -eq 'status') { $Cfg.Status='true';continue }
  if ($key -eq 'install-rust') { $Cfg.InstallRust='true';continue }
  if (-not $Mapping.ContainsKey($key)) { throw "Unknown argument: $token (see --help)" }
  if ($i+1 -ge $args.Count) { throw "Missing value for $token" }
  $Cfg[$Mapping[$key]]=[string]$args[++$i]
  $Supplied[$Mapping[$key]] = $true
}
# An existing run locks ALL configuration. On resume, omitted options must
# inherit that lock rather than reverting to defaults or selecting new datasets.
$ExistingRun = Join-Path $ProjectDir ('assets\' + $Cfg.RunId)
$ExistingLock = Join-Path $ExistingRun 'config.lock.json'
if (Test-Path -LiteralPath $ExistingLock) {
 $Saved = Get-Content -LiteralPath $ExistingLock -Raw | ConvertFrom-Json
 foreach($Prop in $Saved.PSObject.Properties) {
  if (-not $Supplied.ContainsKey($Prop.Name) -and $Cfg.ContainsKey($Prop.Name)) {
   $Cfg[$Prop.Name] = [string]$Prop.Value
  }
 }
}
if ($Cfg.RunId -notmatch '^[a-zA-Z][a-zA-Z0-9_-]*$') {throw 'Invalid run ID'}
if ($Cfg.ReuseCsvRun -ne '' -and $Cfg.ReuseCsvRun -notmatch '^[a-zA-Z][a-zA-Z0-9_-]*$') {throw 'Invalid reuse CSV run ID'}
$sigmaFloat = 0.0
if (-not [double]::TryParse($Cfg.MutationSigma,[Globalization.NumberStyles]::Float,[Globalization.CultureInfo]::InvariantCulture,[ref]$sigmaFloat) -or $sigmaFloat -le 0 -or $sigmaFloat -ge 10000) { throw '--mutation-sigma must be positive invariant-culture number' }
foreach($name in @('Mon','TrainCount','ValidCount','TrainScan','ValidScan','FitnessSample','ValidationSample','Population','Generations','Seed')) {
  if ($Cfg[$name] -notmatch '^\d+$') {throw "Expected integer: $name"}
}
if ([int]$Cfg.Mon -gt 8) {throw '--mon must be 1..8'}
foreach($name in @('TrainCount','ValidCount','TrainScan','ValidScan','FitnessSample','ValidationSample','Population','Generations')) {
 if ([int]$Cfg[$name] -lt 1) {throw "Expected positive value: $name"}
}
if ([int]$Cfg.Population -lt 5) {throw 'population must be >=5 (archived NNUE contract)'}
if ([int]$Cfg.TrainScan -lt [int]$Cfg.TrainCount -or [int]$Cfg.ValidScan -lt [int]$Cfg.ValidCount) {throw 'Scan limits cannot be less than sample counts'}
$RunDir = Join-Path $ProjectDir ('assets\' + $Cfg.RunId)
$State = Join-Path $RunDir 'MON.state'
$Lock = Join-Path $RunDir 'config.lock.json'
$TrainCsv = Join-Path $RunDir 'train.csv'
$ValidCsv = Join-Path $RunDir 'validation.csv'
if ($Cfg.ReuseCsvRun -ne '') {
 $OtherRun=Join-Path $ProjectDir ('assets\' + $Cfg.ReuseCsvRun)
 $TrainCsv=Join-Path $OtherRun 'train.csv'
 $ValidCsv=Join-Path $OtherRun 'validation.csv'
}
$ExtractorManifest = Join-Path $ScriptDir 'binpack\Cargo.toml'
$Exe = Join-Path $ScriptDir 'binpack\target\release\picogen-binpack.exe'
$Pst = Join-Path $RunDir 'pst\best.json'
$Nnue = Join-Path $RunDir 'nnue\best.npy'
$Audit = Join-Path $RunDir 'audit.json'
$SourceCheck = Join-Path $ScriptDir 'archive\genNNUE.py'
New-Item -Force -ItemType Directory -Path $RunDir | Out-Null
if ($Cfg.Mon -ne '0') { $Mon=[int]$Cfg.Mon }
elseif (Test-Path -LiteralPath $State) {$Mon=[int](Get-Content -LiteralPath $State -Raw).Trim()}
else {$Mon=1}
if ($Mon -lt 1 -or $Mon -gt 9) {throw 'MON.state invalid'}
# Explicit MON is a user-requested replay, not an instruction to skip completed work.
$ReplayMon = $Supplied.ContainsKey('Mon') -and ([int]$Cfg.Mon -ge 1)
$identity=[ordered]@{ ModelFormat='picogen-binpack-genetic-fp32-v1' }
foreach($key in @('RunId','TrainBinpack','ValidBinpack','TrainCount','ValidCount','TrainScan','ValidScan','FitnessSample','ValidationSample','Population','Generations','Seed','MutationSigma','ReuseCsvRun')) {
 $identity[$key]=$Cfg[$key]
}
$identityText=ConvertTo-Json -InputObject $identity -Depth 3
if (Test-Path -LiteralPath $Lock) {
 $previous=Get-Content -LiteralPath $Lock -Raw | ConvertFrom-Json
 foreach($key in $identity.Keys) {if ([string]$previous.$key -cne [string]$identity[$key]) {throw "Configuration lock conflict: $key. Use a different --run-id or original parameters."}}
}
if ($Cfg.Status -eq 'true') {Write-Host "RUN_ID=$($Cfg.RunId) MON=$Mon RUN_DIR=$RunDir";Write-Host "TRAIN=$TrainCsv VALID=$ValidCsv";exit 0}
function ExecChecked([string]$command, [string[]]$arguments) {
 Write-Host "EXEC $command $($arguments -join ' ')"
 & $command @arguments
 if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $command" }
}
function Advance {
 $script:Mon=$script:Mon+1
 [IO.File]::WriteAllText($State, [string]$script:Mon+[Environment]::NewLine)
 Write-Host "OK next MON=$script:Mon"
}
function CheckRust {
 $cargo=Get-Command cargo -ErrorAction SilentlyContinue
 $rust=Get-Command rustc -ErrorAction SilentlyContinue
 if (-not $cargo -or -not $rust) {
   $cargoBin=Join-Path $env:USERPROFILE '.cargo\bin'
   if (Test-Path (Join-Path $cargoBin 'cargo.exe')) {$env:PATH=$cargoBin+';'+$env:PATH}
 }
 if (-not (Get-Command cargo -ErrorAction SilentlyContinue) -or -not (Get-Command rustc -ErrorAction SilentlyContinue)) {
  if ($Cfg.InstallRust -ne 'true') {
   throw 'Rust/Cargo missing. Install Rust with: winget install --id Rustlang.Rustup -e ; reopen PowerShell; rustup default stable; cargo --version. Requires Visual Studio Build Tools C++ for MSVC linking. Or pass --install-rust.'
  }
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {throw 'winget missing: install rustup from https://rustup.rs/ and reopen PowerShell'}
  ExecChecked 'winget' @('install','--id','Rustlang.Rustup','-e','--accept-package-agreements','--accept-source-agreements')
  $env:PATH=(Join-Path $env:USERPROFILE '.cargo\bin')+';'+$env:PATH
  if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {throw 'Rust installed but PATH is not active; reopen PowerShell'}
 }
 ExecChecked 'rustc' @('--version'); ExecChecked 'cargo' @('--version')
}
if ($Mon -eq 9) { Write-Host "Genesis completed $RunDir";exit 0 }
if ($Mon -le 1) {
 Write-Host 'MON 1: verify Rust, Python, archived genetic kernels and binpacks'
 CheckRust
 ExecChecked $Cfg.Python @('--version')
 # Keep Python -c source free of embedded string quotes: Windows PowerShell 5.1
 # native argument passing can strip those quotes before Python parses them.
 ExecChecked $Cfg.Python @('-c','import numpy; import chess')
 Write-Host 'NumPy and python-chess OK'
 foreach($file in @($Cfg.TrainBinpack,$Cfg.ValidBinpack,$SourceCheck,$ExtractorManifest,(Join-Path $ScriptDir 'archive\genPST.py'))) {
  if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {throw "Missing prerequisite: $file"}
 }
 if ([IO.Path]::GetFullPath($Cfg.TrainBinpack) -eq [IO.Path]::GetFullPath($Cfg.ValidBinpack)) {throw 'T79 and T77 must be different files'}
 if (-not (Test-Path -LiteralPath $Lock)) {$identityText | Set-Content -LiteralPath $Lock -Encoding UTF8}
 Advance
}
if ($Mon -le 2) {
 Write-Host 'MON 2: compile and self-test extractor (CPU only)'
 CheckRust
 ExecChecked 'cargo' @('test','--manifest-path',$ExtractorManifest)
 ExecChecked 'cargo' @('build','--release','--manifest-path',$ExtractorManifest,'--locked')
 if (-not (Test-Path -LiteralPath $Exe)) {throw "Missing extractor $Exe"}
 Advance
}
if ($Mon -le 3) {
 Write-Host 'MON 3: sample T79 to train.csv'
 if (-not (Test-Path -LiteralPath $TrainCsv)) {
  if ($Cfg.ReuseCsvRun -ne '') {throw "Missing reused train.csv: $TrainCsv"}
  ExecChecked $Exe @('--in',$Cfg.TrainBinpack,'--out',$TrainCsv,'--count',$Cfg.TrainCount,'--scan-limit',$Cfg.TrainScan,'--seed',$Cfg.Seed)
 }
 Advance
}
if ($Mon -le 4) {
 Write-Host 'MON 4: sample independent T77 to validation.csv'
 if (-not (Test-Path -LiteralPath $ValidCsv)) {
  if ($Cfg.ReuseCsvRun -ne '') {throw "Missing reused validation.csv: $ValidCsv"}
  ExecChecked $Exe @('--in',$Cfg.ValidBinpack,'--out',$ValidCsv,'--count',$Cfg.ValidCount,'--scan-limit',$Cfg.ValidScan,'--seed',$Cfg.Seed)
 }
 Advance
}
if ($Mon -le 5) {
 Write-Host 'MON 5: audit FEN and score perspective, lock sample identity'
 ExecChecked $Cfg.Python @((Join-Path $ScriptDir 'gen_csv_dataset.py'),'--train',$TrainCsv,'--validation',$ValidCsv,'--train-sample',$Cfg.FitnessSample,'--validation-sample',$Cfg.ValidationSample,'--seed',$Cfg.Seed,'--out',(Join-Path $RunDir 'dataset_manifest.json'))
 Advance
}
if ($Mon -le 6) {
 Write-Host 'MON 6: PST FP32 genes, gaussian mutation 3 percent'
 $PstArgs = @((Join-Path $ScriptDir 'genPST.py'),'--train',$TrainCsv,'--validation',$ValidCsv,'--out',$Pst,'--population',$Cfg.Population,'--generations',$Cfg.Generations,'--fitness-sample',$Cfg.FitnessSample,'--validation-sample',$Cfg.ValidationSample,'--seed',$Cfg.Seed,'--mutation-sigma',$Cfg.MutationSigma)
 $PreviousPst = Get-ChildItem -LiteralPath (Split-Path -Parent $Pst) -Filter 'best.gen*.json' -File -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1
 if ($ReplayMon -and $Mon -eq 6) {
  Write-Host 'MON 6 explicit replay: restart PST at generation 1; existing checkpoints remain available.'
  ExecChecked $Cfg.Python $PstArgs
 } elseif ($PreviousPst) {
  $completed = [int]([regex]::Match($PreviousPst.Name,'gen(\d{5})\.json$').Groups[1].Value)
  if ($completed -ge [int]$Cfg.Generations -and (Test-Path -LiteralPath $Pst)) {
   Write-Host "PST already complete: $($PreviousPst.Name)"
  } else {
   $PstArgs += @('--resume',$PreviousPst.FullName)
   ExecChecked $Cfg.Python $PstArgs
  }
 } else {ExecChecked $Cfg.Python $PstArgs}
 Advance
}
if ($Mon -le 7) {
 Write-Host 'MON 7: NNUE FP32 768x16, gaussian mutation 3 percent'
 $NnueArgs = @((Join-Path $ScriptDir 'genNNUE.py'),'--train',$TrainCsv,'--validation',$ValidCsv,'--out',$Nnue,'--population',$Cfg.Population,'--generations',$Cfg.Generations,'--fitness-sample',$Cfg.FitnessSample,'--validation-sample',$Cfg.ValidationSample,'--seed',$Cfg.Seed,'--mutation-sigma',$Cfg.MutationSigma)
 # Avoid a nested Sort-Object property hashtable: its previous syntax was invalid in PS 5.1.
 # Compare generations numerically; run UUIDs are not an ordering criterion.
 $PreviousNnue = $null
 $HighestGeneration = -1
 foreach ($Candidate in @(Get-ChildItem -LiteralPath (Split-Path -Parent $Nnue) -Filter 'best.run-fp32.gen*.json' -File -ErrorAction SilentlyContinue)) {
   $Match = [regex]::Match($Candidate.Name, 'gen(\d{5})\.json$')
   if (-not $Match.Success) { continue }
   $Generation = [int]$Match.Groups[1].Value
   if ($Generation -gt $HighestGeneration) {
     $HighestGeneration = $Generation
     $PreviousNnue = $Candidate
   }
 }
 if ($ReplayMon -and $Mon -eq 7) {
  Write-Host 'MON 7 explicit replay: restart NNUE at generation 1; existing checkpoints remain available.'
  ExecChecked $Cfg.Python $NnueArgs
 } elseif ($PreviousNnue) {
  $completed = [int]([regex]::Match($PreviousNnue.Name,'gen(\d{5})\.json$').Groups[1].Value)
  if ($completed -ge [int]$Cfg.Generations -and (Test-Path -LiteralPath ($Nnue -replace '\.npy$','.active.json'))) {
   Write-Host "NNUE already complete: $($PreviousNnue.Name)"
  } else {
   $NnueArgs += @('--resume',$PreviousNnue.FullName)
   ExecChecked $Cfg.Python $NnueArgs
  }
 } else {ExecChecked $Cfg.Python $NnueArgs}
 Advance
}
if ($Mon -le 8) {
 Write-Host 'MON 8: compare both models on the same T77 samples and naive baselines'
 ExecChecked $Cfg.Python @((Join-Path $ScriptDir 'genAudit.py'),'--train',$TrainCsv,'--validation',$ValidCsv,'--pst',$Pst,'--nnue',$Nnue,'--fitness-sample',$Cfg.FitnessSample,'--validation-sample',$Cfg.ValidationSample,'--seed',$Cfg.Seed,'--out',$Audit)
 Advance
}
Write-Host "Genesis complete. Outputs: $RunDir"
