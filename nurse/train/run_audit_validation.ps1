# Nurse audit validation - version 0.1.54
# Runs against the EXACT split used in the original training, without recalculating Stockfish; compares NPZ and real Nurse CLASSIC.
param(
    [string]$Assets = '',
    [string]$Npz = '',
    [string]$Manifest = '',
    [string]$In = '',
    [string]$Out = '',
    [ValidateSet('validation','train')][string]$Split = 'validation',
    [int]$Limit = 0
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
if(-not $Assets){$Assets=Join-Path (Split-Path $root -Parent) 'assets'}
if(-not $Npz){$Npz=Join-Path $Assets 'best.npz'}
if(-not $Manifest){$Manifest=Join-Path $Assets 'split_manifest.json'}
if(-not (Test-Path -LiteralPath $Npz)){throw "No existe checkpoint: $Npz"}
if(-not (Test-Path -LiteralPath $Manifest)){throw "No existe manifiesto: $Manifest"}
if(-not $In){
    $data=Get-Content -LiteralPath $Manifest -Raw -Encoding UTF8 | ConvertFrom-Json
    $In=[string]$data.db
}
if(-not $In){throw 'El manifiesto no contiene db; indicar -In'}
if(-not (Test-Path -LiteralPath $In)){throw "No existe base SQLite: $In"}
if(-not $Out){$Out=Join-Path $Assets ('audit_'+$Split+'.json')}
if($Limit -lt 0){throw '-Limit debe ser >= 0'}
Write-Host "AUDIT split=$Split manifest=$Manifest checkpoint=$Npz"
Write-Host "DB=$In OUT=$Out"
$cmd=@((Join-Path $root 'audit.py'),'--npz',$Npz,'--in',$In,'--manifest',$Manifest,'--split',$Split,'--out',$Out,'--limit',"$Limit")
& python @cmd
if($LASTEXITCODE -ne 0){throw "audit.py failed ($LASTEXITCODE)"}
