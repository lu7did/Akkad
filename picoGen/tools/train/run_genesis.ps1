# Akkad / picoGenus - Genesis orchestrator v0.1.14
# Source: user's four-command run_genesis.ps1. Stages and algorithms unchanged.
# GNU-style long options (such as --mon) are not PowerShell named parameters.
# Parse script arguments explicitly so both -Mon and --mon work in Windows PS 5.1.
$Help = $false
$Mon = -1
$InputDb = 'C:\Users\pedro\github\Bobby\Chess_History_pb\picoAlpha\sample_history.pb'
$SampleDb = 'C:\Users\pedro\github\Bobby\Chess_History_pb\picoAlpha\genus.pb'
#$SampleDb = 'C:\Users\pedro\github\Bobby\Chess_History_pb\picoAlpha\Bk.pb'
$PstOut = '..\..\assets\genus_pst.json'
$NnueOut = '..\..\assets\genus_nnue.npy'
$Bk = '..\..\etc\bratko_kopec.epd'
$AuditOut = '..\..\data\audit_1000-200-200-20261115.json'
$Sample = 10000
$Population = 200
$Generations = 200
$Python = 'python'
$bratko_kopecDb='C:\Users\pedro\github\Bobby\Chess_History_pb\picoAlpha\Bk.pb'
$stockfish='C:\Users\pedro\github\Bobby\stockfish\stockfish.exe'



# Everything below is parsed before the first stage, without side effects.
$Cli = @($args)
for ($i = 0; $i -lt $Cli.Count; $i++) {
    $Token = [string]$Cli[$i]
    $Key = $Token.TrimStart('-').ToLowerInvariant()
    if ($Token -notmatch '^-{1,2}[^-]') {
        throw "Unexpected argument: $Token. See --help."
    }
    if ($Key -in @('help', 'h', '?')) {
        $Help = $true
        continue
    }
    $KnownOptions = @('mon','inputdb','sampledb','pstout','nnueout','bk','auditout','sample','population','generations','python')
    if ($Key -notin $KnownOptions) {
        throw "Unknown option: $Token. See --help."
    }
    if ($i + 1 -ge $Cli.Count) {
        throw "Missing value for $Token. See --help."
    }
    $Value = [string]$Cli[++$i]
    if ([string]::IsNullOrWhiteSpace($Value) -or $Value -match '^--?[A-Za-z][A-Za-z-]*$') {
        throw "Missing value for $Token. See --help."
    }
    switch ($Key) {
        'mon' {
            $Parsed = 0
            if (-not [int]::TryParse($Value, [ref]$Parsed) -or $Parsed -lt 1 -or $Parsed -gt 4) {
                throw 'MON must be an integer from 1 to 4.'
            }
            $Mon = $Parsed
        }
        'inputdb'     { $InputDb = $Value }
        'sampledb'    { $SampleDb = $Value }
        'pstout'      { $PstOut = $Value }
        'nnueout'     { $NnueOut = $Value }
        'bk'          { $Bk = $Value }
        'auditout'    { $AuditOut = $Value }
        'sample'      {
            $Parsed = 0
            if (-not [int]::TryParse($Value, [ref]$Parsed) -or $Parsed -lt 0) { throw 'Sample must be a nonnegative integer.' }
            $Sample = $Parsed
        }
        'population'  {
            $Parsed = 0
            if (-not [int]::TryParse($Value, [ref]$Parsed) -or $Parsed -lt 1) { throw 'Population must be a positive integer.' }
            $Population = $Parsed
        }
        'generations' {
            $Parsed = 0
            if (-not [int]::TryParse($Value, [ref]$Parsed) -or $Parsed -lt 1) { throw 'Generations must be a positive integer.' }
            $Generations = $Parsed
        }
        'python'      { $Python = $Value }
    }
}

$ErrorActionPreference = 'Stop'

function Show-Help {
    @'
Usage:
  .\run_genesis.ps1 -Mon N [options]
  .\run_genesis.ps1 --mon N [options]
  .\run_genesis.ps1 --help

Required:
  -Mon N              Start at stage N (1..4). An omitted/invalid N is an error.
                       Successfully completed stages increment MON automatically.

Inputs / outputs (defaults shown):
  -InputDb PATH        C:\Data\sample_history.pb       (source labeled database)
  -SampleDb PATH       C:\Data\genus.pb                (sampled database)
  -PstOut PATH         ..\..\assets\genus_pst.json    (PST coefficients JSON)
  -NnueOut PATH        ..\..\assets\genus_nnue.npy    (NNUE weights NPY)
  -Bk PATH             C:\Data\bratko_kopec.epd       (Bratko-Kopec EPD)
  -AuditOut PATH       ..\..\assets\audit.json        (audit report)

Training options (preserve original invocation defaults):
  -Sample N            1000      (genSample --sample)
  -Population N        100       (genPST/genNNUE --poblacion)
  -Generations N       500       (genPST/genNNUE --generaciones)
  -Python CMD          python    (Python executable or full path)
  -Help, --help        Print this help and exit without executing stages

Stages:
  MON=1 genSample.py : InputDb -> SampleDb
  MON=2 genPST.py    : SampleDb -> PstOut
  MON=3 genNNUE.py   : SampleDb -> NnueOut
  MON=4 genAudit.py  : PstOut + NnueOut + Bk -> AuditOut
  MON=5 finished (not a valid starting step)

Paths relative to this script's directory, not the caller's working directory.
All four output files can be overwritten by their programs. Starting at MON=2,
3 or 4 does not rerun previous stages. MON is held in memory; resume by passing
-Mon for the first uncompleted stage. On failure MON is not incremented.
'@ | Write-Output
}

if ($Help) {
    Show-Help
    return
}
if ($Mon -lt 1 -or $Mon -gt 4) {
    throw 'Mandatory parameter -Mon/--mon must be an integer in the range 1..4. See --help.'
}

# Resolve relative file paths relative to the script, including when invoked
# from a different working directory. Do not alter paths in the Python scripts.
$ScriptDir = $PSScriptRoot
function Resolve-Asset([string]$PathValue) {
    if ([string]::IsNullOrWhiteSpace($PathValue)) {
        throw 'An input or output path is empty.'
    }
    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return [System.IO.Path]::GetFullPath($PathValue)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $ScriptDir $PathValue))
}
$InputDb = Resolve-Asset $InputDb
$SampleDb = Resolve-Asset $SampleDb
$PstOut = Resolve-Asset $PstOut
$NnueOut = Resolve-Asset $NnueOut
$Bk = Resolve-Asset $Bk
$AuditOut = Resolve-Asset $AuditOut

# Avoid input/output aliases that would destroy the source database.
if ([string]::Equals($InputDb, $SampleDb, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'InputDb and SampleDb must be different files.'
}

function Assert-Input([string]$PathValue, [string]$Label) {
    if (-not (Test-Path -LiteralPath $PathValue -PathType Leaf)) {
        throw "$Label not found: $PathValue"
    }
}
function Assert-OutputDirectory([string]$PathValue, [string]$Label) {
    $Parent = Split-Path -Parent $PathValue
    if (-not (Test-Path -LiteralPath $Parent -PathType Container)) {
        throw "$Label parent directory does not exist: $Parent"
    }
}
function Invoke-Stage([int]$Stage, [string]$Program, [string[]]$Arguments) {
    $ProgramPath = Join-Path $ScriptDir $Program
    Assert-Input $ProgramPath "Stage $Stage program"
    Write-Host ("GENESIS MON={0} starting {1}" -f $Stage, $Program)
    & $Python $ProgramPath @Arguments
    $ExitCode = $LASTEXITCODE
    if ($null -eq $ExitCode) { $ExitCode = 1 }
    if ($ExitCode -ne 0) {
        throw ("GENESIS failed at MON={0}; Python exit code={1}. Resume with -Mon {0}." -f $Stage, $ExitCode)
    }
    Write-Host ("GENESIS MON={0} completed successfully" -f $Stage)
}

try {
    $null = Get-Command $Python -ErrorAction Stop
} catch {
    if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
        throw "Python executable not found: $Python"
    }
}

$MON = [int]$Mon
Write-Host ("GENESIS start MON={0}; script={1}" -f $MON, $ScriptDir)
Write-Host ("GENESIS InputDb={0}" -f $InputDb)
Write-Host ("GENESIS SampleDb={0}" -f $SampleDb)
Write-Host ("GENESIS PstOut={0}" -f $PstOut)
Write-Host ("GENESIS NnueOut={0}" -f $NnueOut)
Write-Host ("GENESIS Bk={0}" -f $Bk)
Write-Host ("GENESIS AuditOut={0}" -f $AuditOut)

if ($MON -eq 1) {
    Assert-Input $InputDb 'InputDb'
    Assert-OutputDirectory $SampleDb 'SampleDb'
    Invoke-Stage 1 'genSample.py' @('--in', $InputDb, '--out', $SampleDb, '--sample', [string]$Sample)
    Invoke-Stage 1 'genBP.py' @('--in', $Bk, '--out', $bratko_kopecDb, '--stockfish', $stockfish, '--depth', 10)

    $MON++

}
if ($MON -eq 2) {
    Assert-Input $SampleDb 'SampleDb'
    Assert-OutputDirectory $PstOut 'PstOut'
    Invoke-Stage 2 'genPST.py' @('--in', $SampleDb, '--out', $PstOut, '--poblacion', [string]$Population, '--generaciones', [string]$Generations)
    #Invoke-Stage 2 'genPST.py' @('--in', $bratko_kopecDb, '--out', $PstOut, '--poblacion', [string]$Population, '--generaciones', [string]$Generations)
    $MON++
}
if ($MON -eq 3) {
    Assert-Input $SampleDb 'SampleDb'
    Assert-OutputDirectory $NnueOut 'NnueOut'
    Invoke-Stage 3 'genNNUE.py' @('--in', $SampleDb, '--out', $NnueOut, '--poblacion', [string]$Population, '--generaciones', [string]$Generations)
    #Invoke-Stage 3 'genNNUE.py' @('--in', $bratko_kopecDb, '--out', $NnueOut, '--poblacion', [string]$Population, '--generaciones', [string]$Generations)

    $MON++
}
if ($MON -eq 4) {
    Assert-Input $PstOut 'PstOut'
    Assert-Input $NnueOut 'NnueOut'
    Assert-Input $Bk 'Bk'
    # The audit report parent is an output directory and may not exist yet.
    # Create it without modifying the configured AuditOut path.
    $AuditDir = Split-Path -Parent $AuditOut
    if (-not (Test-Path -LiteralPath $AuditDir -PathType Container)) {
        New-Item -ItemType Directory -Path $AuditDir -Force -ErrorAction Stop | Out-Null
        Write-Host ("GENESIS created AuditOut directory: {0}" -f $AuditDir)
    }
    Assert-OutputDirectory $AuditOut 'AuditOut'
    Assert-Input $bratko_kopecDb 'Bratko-Kopec labeled database'
    Invoke-Stage 4 'genAudit.py' @('--pst', $PstOut, '--nnue', $NnueOut, '--bk', $Bk, '--db', $bratko_kopecDb, '--out', $AuditOut)
    $MON++
}
Write-Host ("GENESIS completed. MON={0}" -f $MON)
