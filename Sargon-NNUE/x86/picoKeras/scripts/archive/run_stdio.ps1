param([Parameter(Mandatory=$true)][string]$Network,[int]$ArenaMB=32)
$root=Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$exe=Join-Path $root 'build/picoKeras.exe'
if(-not (Test-Path $exe)){$exe=Join-Path $root 'build/Release/picoKeras.exe'}
& $exe --network $Network --arena ($ArenaMB*1MB) --stdio
