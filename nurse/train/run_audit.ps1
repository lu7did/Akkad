param([Parameter(Mandatory=$true)][string]$Npz,[string]$In='', [string]$Epd='',[string]$Out='',[string]$Stockfish='',[int]$Depth=12)
$ErrorActionPreference='Stop';$root=Split-Path -Parent $MyInvocation.MyCommand.Path
if(([bool]$In) -eq ([bool]$Epd)){throw 'Supply exactly one of -In or -Epd'}
$args=@((Join-Path $root 'audit.py'),'--npz',$Npz,'--depth',"$Depth")
if($In){$args+=@('--in',$In)}else{$args+=@('--epd',$Epd)}
if($Out){$args+=@('--out',$Out)};if($Stockfish){$args+=@('--stockfish',$Stockfish)}
& python @args;if($LASTEXITCODE -ne 0){throw "audit.py failed ($LASTEXITCODE)"}
