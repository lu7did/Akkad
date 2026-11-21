# picoGen binpack genetic genesis v0.1.59. Windows PowerShell 5.1 compatible.
# All artifacts are under picoGen/assets. Never reads/writes a SQLite database.
$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = [IO.Path]::GetFullPath((Join-Path $ScriptDir '..\..'))
$DefaultSource = Join-Path $env:USERPROFILE 'github\Bobby\Chess_History_pb\stockfish'
$Cfg = @{
  Mon = '0'; ResumeNnue = 'false'; PstOnly = 'false'; RunId = 'binpack-grumpy-pgpe-fp32-001';
  TrainBinpack = (Join-Path $DefaultSource 'test79-may2022-16tb7p-filter-v6-dd.min-mar2023.unmin.high-simple-eval-1k.min-v2.binpack');
  ValidBinpack = (Join-Path $DefaultSource 'test77-jan2022-2tb7p.high-simple-eval-1k.min-v2.binpack');
  TrainCount = '1500000'; ValidCount = '150000';
  TrainScan = '15000000'; ValidScan = '1500000';
  FitnessSample = '10000'; ValidationSample = '150000';
  Population = '50'; Generations = '100'; Seed = '42'; MutationSigma = '5';
  Python = 'python'; InstallRust = 'true'; Status = 'false'; ReuseCsvRun = 'binpack-pgpe-nonzero-001';
  PGPEPool = '800000'; PGPEBatch = '40000'; PGPEDevice = 'auto'; PGPEStdev = '0.1'
}
function Usage {
@'
Usage: .\run_genesis_binpack.ps1 --mon 1   (no other arguments required)
       .\run_genesis_binpack.ps1 [--mon 1..8] [--status] [options]
  --run-id ID             default binpack-grumpy-pgpe-fp32-001 (new model)
  --train-binpack PATH    T79 (.binpack) from Stockfish
  --valid-binpack PATH    T77 (.binpack), held-out validation
  --train-count N         default 1500000 CSV rows
  --valid-count N         default 150000 CSV rows
  --train-scan N          default 15000000 eligible T79 records to sample
  --valid-scan N          default 1500000 eligible T77 records to sample
  --fitness-sample N      default 10000 fixed T79 subset for PST (MON 6)
  --validation-sample N   default 150000 T77 rows (all eligible nonzero labels)
  --pgpe-pool N           default 800000 filtered T79 positions in RAM (MON 7)
  --pgpe-batch N          default 40000 new positions per generation (MON 7)
  --pgpe-device NAME      auto (XPU then CUDA then CPU), or cpu/xpu/cuda
  --pgpe-stdev FLOAT      initial PGPE stdev, default 0.1
  --population N          default 50, same archived genetic operators
  --generations N         total target (e.g. 300), not additional generations
  --pst-only              run MON 6 PST PGPE alone; leave NNUE and MON 7 untouched
  --resume-nnue           continue MON 7 from existing full PGPE checkpoint (G100 -> target)
  --seed N                default 42
  --mutation-sigma N      Gaussian standard deviation for legacy PST only
  --reuse-csv-run ID      default binpack-pgpe-nonzero-001 (reuse T79/T77)
  --python COMMAND        default python
  --install-rust          install rustup with winget when absent (default enabled)
  --help
All defaults are declared in $Cfg above. --mon 1 runs the complete MON 1..9 pipeline.
Rust, Python libraries and EvoTorch are checked/installed by MON 1.
An explicit --mon N executes step N again even if it was completed before.
Without --mon the script resumes at MON.state and reuses existing checkpoints.
Without --resume-nnue, explicit --mon 7 restarts at G1 and archives old outputs.
With --resume-nnue --mon 7, only increasing --generations is allowed; preserves the checkpoint and history.
The complete best.grumpy-pgpe-v3.latest.pt is required; best.npy alone cannot restore PGPE/Adam.
The stored dataset, sampling and seed configuration remain locked.
MON 1: prerequisites and reproducible run lock
MON 2: compile and test Rust binpack extractor (CPU only)
MON 3: T79 -> train.csv
MON 4: T77 -> validation.csv
MON 5: audit CSV, FEN, target perspective and independent splits
MON 6: PST FP32 PGPE; free pawn/material values; fixed calibration scale
MON 7: EvoTorch PGPE Grumpy 1680 FP32, CP-only objective, select T77 RMSE
MON 8: independent T77 audit + metrics
MON 9: quantize best Grumpy FP32 NNUE to INT8 .bin and .hpp, audit degradation
MON 10: complete
No Bullet, MacOS, Metal, or SQLite training. Uses PyTorch + EvoTorch on XPU/CUDA/CPU.
'@ | Write-Host
}
$Supplied = @{}
$Mapping = @{'mon'='Mon';'run-id'='RunId';'train-binpack'='TrainBinpack';'valid-binpack'='ValidBinpack';
 'train-count'='TrainCount';'valid-count'='ValidCount';'train-scan'='TrainScan';'valid-scan'='ValidScan';
 'fitness-sample'='FitnessSample';'validation-sample'='ValidationSample';
 'population'='Population';'generations'='Generations';'seed'='Seed';'python'='Python';
 'mutation-sigma'='MutationSigma';'reuse-csv-run'='ReuseCsvRun';
 'pgpe-pool'='PGPEPool';'pgpe-batch'='PGPEBatch';
 'pgpe-device'='PGPEDevice';'pgpe-stdev'='PGPEStdev'}
for ($i=0;$i -lt $args.Count;$i++) {
  $token=[string]$args[$i];$key=$token.TrimStart('-').ToLowerInvariant()
  if ($token -notmatch '^--?[A-Za-z]') { throw "Unexpected argument: $token" }
  if ($key -eq 'help' -or $key -eq 'h') { Usage;exit 0 }
  if ($key -eq 'status') { $Cfg.Status='true';continue }
  if ($key -eq 'resume-nnue') { $Cfg.ResumeNnue='true';continue }
  if ($key -eq 'pst-only') { $Cfg.PstOnly='true';continue }
  if ($key -eq 'install-rust') { $Cfg.InstallRust='true';continue }
  if (-not $Mapping.ContainsKey($key)) { throw "Unknown argument: $token (see --help)" }
  if ($i+1 -ge $args.Count) { throw "Missing value for $token" }
  $Cfg[$Mapping[$key]]=[string]$args[++$i]
  $Supplied[$Mapping[$key]] = $true
}
# Dataset identity remains locked; training hyperparameters are reconfigurable
# only on explicit --mon 6 / 7. An ordinary resume inherits the last run values.
$TrainingKeys = @('ValidationSample','Population','Generations','MutationSigma','PGPEPool','PGPEBatch','PGPEDevice','PGPEStdev')
$ExplicitTraining = $Supplied.ContainsKey('Mon') -and @('6','7').Contains([string]$Cfg.Mon)
$ResumeNnue = $Cfg.ResumeNnue -eq 'true'
$PstOnly = $Cfg.PstOnly -eq 'true'
if ($PstOnly -and (-not $Supplied.ContainsKey('Mon') -or $Cfg.Mon -ne '6')) {throw '--pst-only requires --mon 6'}
if ($PstOnly -and $ResumeNnue) {throw '--pst-only and --resume-nnue cannot be combined'}
if ($ResumeNnue -and (-not $Supplied.ContainsKey('Mon') -or $Cfg.Mon -ne '7')) {throw '--resume-nnue requires --mon 7'}
if ($ResumeNnue -and -not $Supplied.ContainsKey('Generations')) {throw '--resume-nnue requires an explicit --generations TOTAL'}
$ExistingRun = Join-Path $ProjectDir ('assets\' + $Cfg.RunId)
$ExistingLock = Join-Path $ExistingRun 'config.lock.json'
if (Test-Path -LiteralPath $ExistingLock) {
 $Saved = Get-Content -LiteralPath $ExistingLock -Raw | ConvertFrom-Json
 foreach($Prop in $Saved.PSObject.Properties) {
  if (-not $Supplied.ContainsKey($Prop.Name) -and $Cfg.ContainsKey($Prop.Name)) {
   # Explicit training replay uses the current script defaults for the three
   # hyperparameters, not the previously locked values.
   if (-not ($ExplicitTraining -and ($TrainingKeys -contains $Prop.Name))) {
    $Cfg[$Prop.Name] = [string]$Prop.Value
   }
  }
 }
}
if ($Cfg.RunId -notmatch '^[a-zA-Z][a-zA-Z0-9_-]*$') {throw 'Invalid run ID'}
if ($Cfg.ReuseCsvRun -ne '' -and $Cfg.ReuseCsvRun -notmatch '^[a-zA-Z][a-zA-Z0-9_-]*$') {throw 'Invalid reuse CSV run ID'}
if ($Cfg.PGPEDevice -notin @('auto','cpu','cuda','xpu')) {throw 'pgpe-device must be auto, cpu, cuda or xpu'}
$stdevFloat = 0.0
if (-not [double]::TryParse($Cfg.PGPEStdev,[Globalization.NumberStyles]::Float,[Globalization.CultureInfo]::InvariantCulture,[ref]$stdevFloat) -or $stdevFloat -le 0) {throw '--pgpe-stdev must be positive'}
$sigmaFloat = 0.0
if (-not [double]::TryParse($Cfg.MutationSigma,[Globalization.NumberStyles]::Float,[Globalization.CultureInfo]::InvariantCulture,[ref]$sigmaFloat) -or $sigmaFloat -le 0 -or $sigmaFloat -ge 10000) { throw '--mutation-sigma must be positive invariant-culture number' }
foreach($name in @('Mon','TrainCount','ValidCount','TrainScan','ValidScan','FitnessSample','ValidationSample','Population','Generations','Seed','PGPEPool','PGPEBatch')) {
  if ($Cfg[$name] -notmatch '^\d+$') {throw "Expected integer: $name"}
}
if ([int]$Cfg.Mon -gt 9) {throw '--mon must be 1..9'}
foreach($name in @('TrainCount','ValidCount','TrainScan','ValidScan','FitnessSample','ValidationSample','Population','Generations')) {
 if ([int]$Cfg[$name] -lt 1) {throw "Expected positive value: $name"}
}
if ([int]$Cfg.Population -lt 2 -or [int]$Cfg.Population % 2 -ne 0) {throw 'PGPE population must be even and >=2 (PST also runs with this population)'}
if ([int]$Cfg.PGPEPool -lt 1 -or [int]$Cfg.PGPEBatch -lt 1 -or [int]$Cfg.PGPEBatch -gt [int]$Cfg.PGPEPool) {throw 'pgpe-pool must be >= pgpe-batch >= 1'}
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
$AuditPst = $Pst
if ($Cfg.ReuseCsvRun -ne '' -and -not (Test-Path -LiteralPath $Pst -PathType Leaf)) {
 $ReusablePst = Join-Path (Join-Path $ProjectDir ('assets\' + $Cfg.ReuseCsvRun)) 'pst\best.json'
 if (Test-Path -LiteralPath $ReusablePst -PathType Leaf) { $AuditPst = $ReusablePst }
}
$Nnue = Join-Path $RunDir 'nnue\best.npy'
$Audit = Join-Path $RunDir 'audit.json'
$SourceCheck = Join-Path $ScriptDir 'archive\genNNUE.py'
New-Item -Force -ItemType Directory -Path $RunDir | Out-Null
if ($Cfg.Mon -ne '0') { $Mon=[int]$Cfg.Mon }
elseif (Test-Path -LiteralPath $State) {$Mon=[int](Get-Content -LiteralPath $State -Raw).Trim()}
else {$Mon=1}
if ($Mon -lt 1 -or $Mon -gt 10) {throw 'MON.state invalid'}
# Explicit MON is a user-requested replay, not an instruction to skip completed work.
$ReplayMon = $Supplied.ContainsKey('Mon') -and ([int]$Cfg.Mon -ge 1)
$identity=[ordered]@{ ModelFormat='picogen-binpack-genetic-fp32-v1' }
foreach($key in @('RunId','TrainBinpack','ValidBinpack','TrainCount','ValidCount','TrainScan','ValidScan','FitnessSample','ValidationSample','Population','Generations','Seed','MutationSigma','ReuseCsvRun','PGPEPool','PGPEBatch','PGPEDevice','PGPEStdev')) {
 $identity[$key]=$Cfg[$key]
}
$identityText=ConvertTo-Json -InputObject $identity -Depth 3
$TrainingChange = $false
if (Test-Path -LiteralPath $Lock) {
 $previous=Get-Content -LiteralPath $Lock -Raw | ConvertFrom-Json
 foreach($key in $identity.Keys) {
  if ([string]$previous.$key -cne [string]$identity[$key]) {
   if ($ResumeNnue -and $key -eq 'Generations' -and [int]$identity[$key] -gt [int]$previous.$key) {
    Write-Host "NNUE resume target extended: $($previous.$key) -> $($identity[$key])"
    $TrainingChange = $true
   } elseif ($ResumeNnue) {
    throw "NNUE resume cannot change $key; only an increase in --generations is allowed."
   } elseif ($ExplicitTraining -and ($TrainingKeys -contains $key)) {
    Write-Host "Training parameter updated: $key $($previous.$key) -> $($identity[$key])"
    $TrainingChange = $true
   } else {
    throw "Configuration lock conflict: $key. Dataset identity remains locked; use a new --run-id for dataset or seed changes."
   }
  }
 }
}
if ($Cfg.Status -eq 'true') {Write-Host "RUN_ID=$($Cfg.RunId) MON=$Mon RUN_DIR=$RunDir";Write-Host "TRAIN=$TrainCsv VALID=$ValidCsv";exit 0}
function ExecChecked([string]$command, [string[]]$arguments) {
 Write-Host "EXEC $command $($arguments -join ' ')"
 & $command @arguments
 if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $command" }
}
function SaveTrainingLock {
 if ($TrainingChange) {
  # Atomic replacement; previous lock is saved in the archived stage directory.
  $temp = $Lock + '.partial'
  [IO.File]::WriteAllText($temp, $identityText, (New-Object Text.UTF8Encoding($false)))
  Move-Item -LiteralPath $temp -Destination $Lock -Force
  Write-Host "Training configuration updated: population=$($Cfg.Population) generations=$($Cfg.Generations) pgpe_pool=$($Cfg.PGPEPool) pgpe_batch=$($Cfg.PGPEBatch) device=$($Cfg.PGPEDevice) stdev=$($Cfg.PGPEStdev)"
 }
}
function ArchiveTrainingStep([string]$stage) {
 # A new explicitly requested run starts at generation 1. Never mix its
 # checkpoints with earlier generations (including generations > new limit).
 $stageDir = Join-Path $RunDir $stage
 $archiveRoot = Join-Path $RunDir 'history'
 $stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmss-fff')
 $unique = [guid]::NewGuid().ToString('N').Substring(0,8)
 $archive = Join-Path $archiveRoot ($stage + '-' + $stamp + '-' + $unique)
 New-Item -ItemType Directory -Path $archive -Force | Out-Null
 if (Test-Path -LiteralPath $Lock -PathType Leaf) {
  Copy-Item -LiteralPath $Lock -Destination (Join-Path $archive 'config.lock.previous.json')
 }
 if (Test-Path -LiteralPath $stageDir -PathType Container) {
  Move-Item -LiteralPath $stageDir -Destination (Join-Path $archive $stage)
 }
 if (Test-Path -LiteralPath $Audit -PathType Leaf) {
  Move-Item -LiteralPath $Audit -Destination (Join-Path $archive 'audit.previous.json')
 }
 Write-Host "Archived previous $stage outputs at $archive"
 # Persist the stage to ensure that a failed attempt is resumed correctly when
 # --mon is omitted on the next invocation.
 [IO.File]::WriteAllText($State, [string]$Mon + [Environment]::NewLine)
 SaveTrainingLock
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
if ($Mon -eq 10) { Write-Host "Genesis completed $RunDir";exit 0 }
if ($Mon -le 1) {
 Write-Host 'MON 1: verify/install Rust, Python, PyTorch, EvoTorch, chess and binpack sources'
 CheckRust
 ExecChecked $Cfg.Python @('--version')
 # Keep Python -c source free of embedded string quotes: Windows PowerShell 5.1
 # native argument passing can strip those quotes before Python parses them.
 ExecChecked $Cfg.Python @((Join-Path $ScriptDir 'gen_pgpe_deps.py'),'--install')
 ExecChecked $Cfg.Python @((Join-Path $ScriptDir 'genGrumpyPGPE.py'),'--help')
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
 Write-Host 'MON 6: PST EvoTorch PGPE FP32; all material values evolvable, calibration fixed 100'
 $PstStateSaved = $null
 if ($PstOnly -and (Test-Path -LiteralPath $State -PathType Leaf)) { $PstStateSaved = [IO.File]::ReadAllText($State) }
 $PstArgs = @((Join-Path $ScriptDir 'genPSTPGPE.py'),'--train',$TrainCsv,'--validation',$ValidCsv,'--out',$Pst,'--population',$Cfg.Population,'--generations',$Cfg.Generations,'--fitness-sample',$Cfg.PGPEPool,'--validation-sample',$Cfg.ValidationSample,'--batch-size',$Cfg.PGPEBatch,'--seed',$Cfg.Seed,'--exclude-zero')
 $PstLatest = Join-Path (Split-Path -Parent $Pst) 'best.pst-pgpe-v1.latest.pt'
 if ($ReplayMon -and $Mon -eq 6) {
  Write-Host 'MON 6 explicit replay: restart PST PGPE at generation 1; archive only PST outputs.'
  if ($PstOnly) {
   $PstDir = Split-Path -Parent $Pst
   if (Test-Path -LiteralPath $PstDir -PathType Container) {
    $PstHistory = Join-Path $RunDir ('history\pst-' + (Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmss-fff') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8))
    New-Item -ItemType Directory -Path $PstHistory -Force | Out-Null
    Move-Item -LiteralPath $PstDir -Destination (Join-Path $PstHistory 'pst')
    Write-Host "Archived previous PST outputs only: $PstHistory"
   }
  } else { ArchiveTrainingStep 'pst' }
  ExecChecked $Cfg.Python $PstArgs
 } elseif (Test-Path -LiteralPath $PstLatest -PathType Leaf) {
  $PstArgs += @('--resume',$PstLatest)
  ExecChecked $Cfg.Python $PstArgs
 } else {ExecChecked $Cfg.Python $PstArgs}
 if ($PstOnly) {
  if ($null -ne $PstStateSaved) { [IO.File]::WriteAllText($State,$PstStateSaved) }
  Write-Host 'PST-only complete. NNUE weights, checkpoints, MON.state and MON 7 are unchanged. MON 8 audit not run.'
  exit 0
 }
 Advance
}
if ($Mon -le 7) {
 Write-Host 'MON 7: Grumpy FP32 PGPE + Adam; CP-only objective; best T77 RMSE checkpoint'
 $NnueArgs = @((Join-Path $ScriptDir 'genGrumpyPGPE.py'),'--train',$TrainCsv,'--validation',$ValidCsv,'--out',$Nnue,'--population',$Cfg.Population,'--generations',$Cfg.Generations,'--fitness-sample',$Cfg.PGPEPool,'--validation-sample',$Cfg.ValidationSample,'--batch-size',$Cfg.PGPEBatch,'--seed',$Cfg.Seed,'--device',$Cfg.PGPEDevice,'--pgpe-stdev',$Cfg.PGPEStdev,'--exclude-zero')
 # Avoid a nested Sort-Object property hashtable: its previous syntax was invalid in PS 5.1.
 # Compare generations numerically; run UUIDs are not an ordering criterion.
 $PreviousNnue = $null
 $HighestGeneration = -1
 foreach ($Candidate in @(Get-ChildItem -LiteralPath (Split-Path -Parent $Nnue) -Filter 'best.grumpy-pgpe-v3.gen*.json' -File -ErrorAction SilentlyContinue)) {
   $Match = [regex]::Match($Candidate.Name, 'gen(\d{5})\.json$')
   if (-not $Match.Success) { continue }
   $Generation = [int]$Match.Groups[1].Value
   if ($Generation -gt $HighestGeneration) {
     $HighestGeneration = $Generation
     $PreviousNnue = $Candidate
   }
 }
 if ($ResumeNnue) {
  $Checkpoint = Join-Path (Split-Path -Parent $Nnue) 'best.grumpy-pgpe-v3.latest.pt'
  if (-not (Test-Path -LiteralPath $Checkpoint -PathType Leaf)) {
   throw "Cannot resume NNUE: complete checkpoint not found: $Checkpoint. best.npy is insufficient."
  }
  if (-not $PreviousNnue) {
   throw 'Cannot resume NNUE: missing generation summary; no existing checkpoint may be overwritten.'
  }
  $completed = $HighestGeneration
  if ($completed -ge [int]$Cfg.Generations) {
   throw "NNUE already reached G$completed; --generations must be greater to continue."
  }
  Write-Host "MON 7 RESUME: G$completed -> G$($Cfg.Generations); preserving PGPE distribution, Adam and best model."
  $NnueArgs += @('--resume',$Checkpoint)
  # Do not touch existing best.npy or the full checkpoint before Python validates its identity.
  ExecChecked $Cfg.Python $NnueArgs
  SaveTrainingLock
 } elseif (($ReplayMon -and $Mon -eq 7) -or ($ReplayMon -and [int]$Cfg.Mon -eq 6 -and $TrainingChange)) {
  Write-Host 'MON 7 fresh training: restart NNUE at generation 1; archive incompatible previous checkpoints.'
  ArchiveTrainingStep 'nnue'
  ExecChecked $Cfg.Python $NnueArgs
 } elseif ($PreviousNnue) {
  $completed = [int]([regex]::Match($PreviousNnue.Name,'gen(\d{5})\.json$').Groups[1].Value)
  if ($completed -ge [int]$Cfg.Generations -and (Test-Path -LiteralPath ($Nnue -replace '\.npy$','.active.json'))) {
   Write-Host "NNUE already complete: $($PreviousNnue.Name)"
  } else {
   $NnueArgs += @('--resume',(Join-Path (Split-Path -Parent $Nnue) 'best.grumpy-pgpe-v3.latest.pt'))
   ExecChecked $Cfg.Python $NnueArgs
  }
 } else {
   if ((Test-Path -LiteralPath $Nnue) -or (Test-Path -LiteralPath ($Nnue -replace '\.npy$','.active.json'))) {
    throw 'Existing NNUE artifacts but no PGPE checkpoint. Run explicitly --mon 7 to archive and start PGPE.'
   }
   ExecChecked $Cfg.Python $NnueArgs
 }
 Advance
}
if ($Mon -le 8) {
 Write-Host 'MON 8: audit Grumpy FP32, PST and baselines on full nonzero-CP T77 sample'
 ExecChecked $Cfg.Python @((Join-Path $ScriptDir 'genAudit.py'),'--train',$TrainCsv,'--validation',$ValidCsv,'--pst',$AuditPst,'--nnue',$Nnue,'--fitness-sample',$Cfg.FitnessSample,'--validation-sample',$Cfg.ValidationSample,'--seed',$Cfg.Seed,'--out',$Audit,'--exclude-zero')
 Advance
}
if ($Mon -le 9) {
 Write-Host 'MON 9: export Grumpy NNUE INT8 binary and C++ header, audit quantization vs FP32'
 $ExportArgs = @((Join-Path $ScriptDir 'exportGrumpyInt8.py'),
     '--in',$Nnue,
     '--bin',(Join-Path (Split-Path -Parent $Nnue) 'best.int8.bin'),
     '--hpp',(Join-Path (Split-Path -Parent $Nnue) 'best.int8.hpp'),
     '--report',(Join-Path (Split-Path -Parent $Nnue) 'best.int8.json'),
     '--validation',$ValidCsv,
     '--validation-sample','5000')
 ExecChecked $Cfg.Python $ExportArgs
 Advance
}
Write-Host "Genesis complete. Outputs: $RunDir"
