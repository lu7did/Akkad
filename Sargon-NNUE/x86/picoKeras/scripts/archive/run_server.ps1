param([Parameter(Mandatory=$true)][string]$Network,[int]$Port=6110,[string]$HostAddress='0.0.0.0',[int]$ArenaMB=32)
$root=Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$exe=Join-Path $root 'build/picoKeras.exe'
if(-not (Test-Path $exe)){$exe=Join-Path $root 'build/Release/picoKeras.exe'}
& $exe --network $Network --port $Port --host $HostAddress --arena ($ArenaMB*1MB)
