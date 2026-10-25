# Sargon-NNUE v0.6.155 - Ejecutar una unica etapa por invocacion.
# Rutas relativas: relativas al directorio de este script (scripts/).
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateSet('import','sample','evaluate','audit','train')][string]$Stage,
    [ValidateSet('sargon','stockfish','result','lc0','lc0-uci')][string]$Method,
    [string]$Name = 'lex',
    [string]$Python = '',
    [string]$PgnPattern = '..\data\pgn\*.pgn',
    [string]$ImportPb,
    [string]$SamplePb,
    [string]$RunDir,
    [string]$AuditJson,
    [string]$AuditCsv,
    [double]$SamplePercent = 20.0,
    [int]$Seed = 314159,
    [string]$StockfishPath = 'C:\Users\pedro\github\bobby\stockfish\stockfish.exe',
    [int]$StockfishDepth = 10,
    [int]$StockfishThreads = 4,
    [double]$ResultSmoothing = 0.15,
    [string]$Lc0Weights,
    [string]$Lc0Exe = '',
    [int]$Lc0UciNodes = 800,
    [int]$Lc0UciThreads = 1,
    [string]$Lc0UciOptions = '',
    [ValidateSet('neural','uci')][string]$Lc0Source = 'neural',
    [string]$Lc0Backend = 'auto',
    [string]$Lc0BackendOptions = '',
    [ValidateSet('strict','allow-incomplete')][string]$Lc0History = 'allow-incomplete',
    [double]$WeightLc0 = 0.0,
    [double]$WeightClassic = 0.0,
    [double]$WeightStockfish = 0.0,
    [double]$WeightResult = 1.0,
    [int]$Epochs = 30,
    [double]$LearningRate = 0.001,
    [ValidateSet('none','step','cosine','plateau')][string]$Scheduler = 'plateau',
    [int]$Patience = 3,
    [double]$Gamma = 0.5,
    [double]$MinLr = 0.00001,
    [int]$BatchSize = 64,
    [double]$Validation = 10.0,
    [ValidateSet('auto','cpu','cuda','xpu')][string]$Device = 'auto',
    [ValidateSet('adam','sgd','adamw','rmsprop','adagrad','adadelta','adamax','nadam','radam','asgd','rprop')][string]$Optimizer = 'adamw',
    [switch]$Version
)
$ErrorActionPreference = 'Stop'
$script:ExitCode = 0
function Resolve-PathFromScripts([string]$value) {
    if ([string]::IsNullOrWhiteSpace($value)) { throw 'Ruta vacia' }
    if ([IO.Path]::IsPathRooted($value)) { return [IO.Path]::GetFullPath($value) }
    return [IO.Path]::GetFullPath((Join-Path $PSScriptRoot $value))
}
function Resolve-PgnGlob([string]$glob) {
    $directory = Split-Path -Path $glob -Parent
    $mask = Split-Path -Path $glob -Leaf
    if (-not $directory) { $directory = '.' }
    if (-not $mask) { throw 'PgnPattern sin mascara' }
    return (Join-Path (Resolve-PathFromScripts $directory) $mask)
}
function Ensure-Parent([string]$path) {
    $parent = Split-Path -Parent $path
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
}
function Num([double]$value) {
    return $value.ToString('G17',[Globalization.CultureInfo]::InvariantCulture)
}
function Invoke-Module([string]$module,[string[]]$argv) {
    Write-Host ("[{0}] python -m {1} {2}" -f $Stage,$module,($argv -join ' ')) -ForegroundColor Cyan
    & $Python -m $module @argv
    if ($LASTEXITCODE -ne 0) { throw "Modulo $module fallo (codigo $LASTEXITCODE)" }
}
try {
    if ($Version) { Write-Host 'SARGON PIPELINE v0.6.155'; return }
    if ($Name -notmatch '^[A-Za-z0-9_-]+$') { throw 'Name invalido' }
    if (-not $ImportPb) { $ImportPb = "..\data\pb\$Name.pb" }
    if (-not $SamplePb) { $SamplePb = "..\data\pb\${Name}_sample.pb" }
    if (-not $RunDir) { $RunDir = "..\data\runs\$Name" }
    if (-not $AuditJson) { $AuditJson = Join-Path $RunDir 'audit.json' }
    if (-not $AuditCsv) { $AuditCsv = Join-Path $RunDir 'audit.csv' }
    $ImportPb = Resolve-PathFromScripts $ImportPb
    $SamplePb = Resolve-PathFromScripts $SamplePb
    $RunDir = Resolve-PathFromScripts $RunDir
    $AuditJson = Resolve-PathFromScripts $AuditJson
    $AuditCsv = Resolve-PathFromScripts $AuditCsv
    if (-not $Python) { $Python = $env:SARGON_PYTHON }
    if (-not $Python) { $Python = if (Get-Command python3 -ErrorAction SilentlyContinue) { 'python3' } else { 'python' } }
    if (($Python.Contains('/') -or $Python.Contains('\')) -and -not [IO.Path]::IsPathRooted($Python)) { $Python = Resolve-PathFromScripts $Python }
    if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) { throw "Python inexistente: $Python" }
    if ($ImportPb -eq $SamplePb) { throw 'ImportPb y SamplePb deben diferir' }
    $root = Resolve-PathFromScripts '..'
    $previousPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = (Join-Path $root 'src') + [IO.Path]::PathSeparator + $previousPythonPath
    try {
        Write-Host "SARGON PIPELINE v0.6.155 | stage=$Stage | name=$Name" -ForegroundColor Green
        switch ($Stage) {
            'import' {
                $glob = Resolve-PgnGlob $PgnPattern
                $matches = @(Get-ChildItem -Path $glob -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -ieq '.pgn' })
                if ($matches.Count -eq 0) { throw "No se encontraron PGN: $glob" }
                Ensure-Parent $ImportPb
                Invoke-Module 'sargon_nnue.sargon_prepare' @('--dir',$glob,'--out',$ImportPb)
            }
            'sample' {
                if ($SamplePercent -le 0 -or $SamplePercent -gt 100) { throw 'SamplePercent debe estar en (0,100]' }
                if (-not (Test-Path -LiteralPath $ImportPb -PathType Leaf)) { throw "Base maestra inexistente: $ImportPb" }
                if (Test-Path -LiteralPath $SamplePb) { throw "Muestra existente, no se sobrescribe: $SamplePb" }
                Ensure-Parent $SamplePb
                Invoke-Module 'sargon_nnue.sargon_prepare' @('--input',$ImportPb,'--resample',(Num $SamplePercent),'--seed',"$Seed",'--out',$SamplePb)
            }
            'evaluate' {
                if (-not $PSBoundParameters.ContainsKey('Method')) { throw 'evaluate requiere -Method sargon|stockfish|result' }
                if (-not (Test-Path -LiteralPath $SamplePb -PathType Leaf)) { throw "Base de muestra inexistente: $SamplePb" }
                switch ($Method) {
                    'lc0-uci' {
                        if (-not $Lc0Exe) { throw 'Lc0Exe obligatorio para LC0 UCI' }
                        $exe=Resolve-PathFromScripts $Lc0Exe
                        if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "LC0 exe no existe: $exe" }
                        $arguments=@('--input',$SamplePb,'--update','lc0-uci','--lc0-uci-path',$exe,'--lc0-uci-nodes',"$Lc0UciNodes",'--lc0-uci-threads',"$Lc0UciThreads",'--lc0-backend',$Lc0Backend,'--lc0-history',$Lc0History)
                        if (-not [string]::IsNullOrWhiteSpace($Lc0UciOptions)) { $arguments += @('--lc0-uci-options',$Lc0UciOptions) }
                        if (-not [string]::IsNullOrWhiteSpace($Lc0BackendOptions)) { $arguments += @('--lc0-backend-options',$Lc0BackendOptions) }
                        if ($Lc0Weights) { $arguments += @('--lc0-weights',(Resolve-PathFromScripts $Lc0Weights)) }
                        Invoke-Module 'sargon_nnue.sargon_prepare' $arguments
                    }
                    'lc0' {
                        if (-not $Lc0Weights) { throw 'Lc0Weights es obligatorio para -Method lc0' }
                        $w=Resolve-PathFromScripts $Lc0Weights
                        if (-not (Test-Path -LiteralPath $w -PathType Leaf)) { throw "LC0 weights inexistentes: $w" }
                        $arguments=@('--input',$SamplePb,'--update','lc0','--lc0-weights',$w,'--lc0-backend',$Lc0Backend,'--lc0-history',$Lc0History)
                        if (-not [string]::IsNullOrWhiteSpace($Lc0BackendOptions)) { $arguments += @('--lc0-backend-options',$Lc0BackendOptions) }
                        Invoke-Module 'sargon_nnue.sargon_prepare' $arguments
                    }
                    'sargon' { Invoke-Module 'sargon_nnue.sargon_prepare' @('--input',$SamplePb,'--update','classic') }
                    'stockfish' {
                        if ($StockfishDepth -lt 1 -or $StockfishThreads -lt 1) { throw 'StockfishDepth y StockfishThreads deben ser positivos' }
                        $exe = Resolve-PathFromScripts $StockfishPath
                        if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "Stockfish inexistente: $exe" }
                        Invoke-Module 'sargon_nnue.sargon_prepare' @('--input',$SamplePb,'--update','stockfish','--stockfish-path',$exe,'--stockfish-depth',"$StockfishDepth",'--stockfish-threads',"$StockfishThreads")
                    }
                    'result' {
                        if ($ResultSmoothing -le 0 -or $ResultSmoothing -gt 1) { throw 'ResultSmoothing debe estar en (0,1]' }
                        Invoke-Module 'sargon_nnue.sargon_prepare' @('--input',$SamplePb,'--update','result','--result-smoothing',(Num $ResultSmoothing))
                    }
                }
            }
            'audit' {
                if (-not (Test-Path -LiteralPath $SamplePb -PathType Leaf)) { throw "Base de muestra inexistente: $SamplePb" }
                if ($Validation -le 0 -or $Validation -ge 100) { throw 'Validation debe estar en (0,100)' }
                if ((Test-Path -LiteralPath $AuditJson) -or (Test-Path -LiteralPath $AuditCsv)) { throw 'Informes existentes: se evita sobrescribir la auditoria' }
                Ensure-Parent $AuditJson
                Ensure-Parent $AuditCsv
                Invoke-Module 'sargon_nnue.sargon_audit_pb' @('--input',$SamplePb,'--validation',(Num $Validation),'--seed',"$Seed",'--out',$AuditJson,'--csv',$AuditCsv)
            }
            'train' {
                if (-not (Test-Path -LiteralPath $SamplePb -PathType Leaf)) { throw "Base de muestra inexistente: $SamplePb" }
                if ($WeightClassic -lt 0 -or $WeightStockfish -lt 0 -or $WeightResult -lt 0 -or $WeightLc0 -lt 0 -or [Math]::Abs($WeightClassic+$WeightStockfish+$WeightResult+$WeightLc0-1) -gt 1e-9) { throw 'Los pesos deben sumar 1 y no ser negativos' }
                if ($LearningRate -le 0 -or $MinLr -le 0 -or $MinLr -gt $LearningRate) { throw 'LearningRate / MinLr invalidos' }
                if ($Gamma -le 0 -or $Gamma -ge 1 -or $Patience -lt 0 -or $Epochs -lt 1 -or $BatchSize -lt 1) { throw 'Parametros de entrenamiento invalidos' }
                if ($Validation -le 0 -or $Validation -ge 100) { throw 'Validation debe estar en (0,100)' }
                $checkpointDir = Join-Path $RunDir 'checkpoints'
                if (Test-Path -LiteralPath $checkpointDir) {
                    if (@(Get-ChildItem -LiteralPath $checkpointDir -Force).Count -gt 0) { throw "Checkpoints existentes: $checkpointDir" }
                }
                New-Item -ItemType Directory -Path $checkpointDir -Force | Out-Null
                Invoke-Module 'sargon_nnue.sargon_train' @('--input',$SamplePb,'--nnuedir',$checkpointDir,'--pytorch','--device',$Device,'--lc0-source',$Lc0Source,'--weight-lc0',(Num $WeightLc0),'--weight-classic',(Num $WeightClassic),'--weight-stockfish',(Num $WeightStockfish),'--weight-result',(Num $WeightResult),'--epoch',"$Epochs",'--validation',(Num $Validation),'--seed',"$Seed",'--optimizer',$Optimizer,'--lr',(Num $LearningRate),'--scheduler',$Scheduler,'--patience',"$Patience",'--gamma',(Num $Gamma),'--min-lr',(Num $MinLr),'--batch-size',"$BatchSize",'--save-best')
                if (-not (Test-Path -LiteralPath (Join-Path $checkpointDir 'nnue_best.npz') -PathType Leaf)) { throw 'No se creo nnue_best.npz' }
            }
        }
        Write-Host "[OK] v0.6.155 etapa $Stage completada" -ForegroundColor Green
    } finally { $env:PYTHONPATH = $previousPythonPath }
} catch {
    Write-Error "PIPELINE v0.6.155 [$Stage]: $_"
    exit 1
}
