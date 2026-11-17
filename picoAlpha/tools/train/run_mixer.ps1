# picoAlpha mixer v0.1.18 - Windows PowerShell 5.1 compatible.
# Run with no arguments to use the editable defaults below.
# Overrides: --in PATH --mix PATH --out PATH --batch N
$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Edit these three paths to select your usual databases.
$InputDb = 'C:\Users\pedro\github\Bobby\Chess_History_pb\picoAlpha\history.pb'
$MixDb   = 'C:\Users\pedro\github\Bobby\Chess_History_pb\picoAlpha\sample_history.pb'
$OutDb   = 'C:\Users\pedro\github\Bobby\Chess_History_pb\picoAlpha\mixed_history.pb'
$Batch   = 10000

$Arguments = @($args)
if ($Arguments.Count -eq 1 -and ($Arguments[0] -eq '--help' -or $Arguments[0] -eq '-help' -or $Arguments[0] -eq '-h')) {
    Write-Host 'Usage: .\run_mixer.ps1 [--in PATH] [--mix PATH] [--out PATH] [--batch N]'
    Write-Host 'No arguments: run with the editable default paths in this script.'
    Write-Host ('Default --in:    ' + $InputDb)
    Write-Host ('Default --mix:   ' + $MixDb)
    Write-Host ('Default --out:   ' + $OutDb)
    Write-Host ('Default --batch: ' + $Batch)
    & python (Join-Path $ScriptDir 'mixer.py') --help
    exit $LASTEXITCODE
}
if (($Arguments.Count % 2) -ne 0) {
    throw 'Each option must be followed by a value. Use --help.'
}
for ($i = 0; $i -lt $Arguments.Count; $i += 2) {
    $Key = [string]$Arguments[$i]
    $Value = [string]$Arguments[$i + 1]
    switch ($Key) {
        '--in'    { $InputDb = $Value; break }
        '--mix'   { $MixDb = $Value; break }
        '--out'   { $OutDb = $Value; break }
        '--batch' {
            $NewBatch = 0
            if (-not [int]::TryParse($Value, [ref]$NewBatch) -or $NewBatch -lt 1) {
                throw '--batch must be a positive integer.'
            }
            $Batch = $NewBatch
            break
        }
        default { throw ('Unknown option: ' + $Key + '. Use --help.') }
    }
}
function Resolve-MixerPath([string]$PathValue) {
    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return [System.IO.Path]::GetFullPath($PathValue)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $ScriptDir $PathValue))
}
$InputDb = Resolve-MixerPath $InputDb
$MixDb = Resolve-MixerPath $MixDb
$OutDb = Resolve-MixerPath $OutDb
$Mixer = Join-Path $ScriptDir 'mixer.py'
if (-not (Test-Path -LiteralPath $Mixer -PathType Leaf)) {
    throw ('mixer.py not found: ' + $Mixer)
}
if (-not (Test-Path -LiteralPath $InputDb -PathType Leaf)) {
    throw ('--in database not found: ' + $InputDb)
}
if (-not (Test-Path -LiteralPath $MixDb -PathType Leaf)) {
    throw ('--mix database not found: ' + $MixDb)
}
if ($InputDb -eq $MixDb -or $InputDb -eq $OutDb -or $MixDb -eq $OutDb) {
    throw '--in, --mix and --out must be different files.'
}
Write-Host 'picoAlpha mixer wrapper v0.1.18'
Write-Host ('IN:    ' + $InputDb)
Write-Host ('MIX:   ' + $MixDb)
Write-Host ('OUT:   ' + $OutDb)
Write-Host ('BATCH: ' + $Batch)
$PythonArgs = @($Mixer, '--in', $InputDb, '--mix', $MixDb, '--out', $OutDb, '--batch', [string]$Batch)
& python @PythonArgs
exit $LASTEXITCODE
