param([Parameter(Mandatory=$true)][string]$In,[string]$Int8='', [string]$Hpp='')
$ErrorActionPreference='Stop';$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$assets=Join-Path (Split-Path -Parent $root) 'assets'
if(!$Int8){$Int8=Join-Path $assets 'best_int8.npz'}
if(!$Hpp){$Hpp=Join-Path $assets 'best_int8.hpp'}
& python (Join-Path $root 'export.py') --in $In --int8 $Int8 --hpp $Hpp
if($LASTEXITCODE -ne 0){throw "export.py failed ($LASTEXITCODE)"}
