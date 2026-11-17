param([Parameter(Mandatory=$true)][string]$In,[string]$Out='', [int]$Sample=0,[double]$Fraction=0,[double]$Validation=20,[int]$Epoch=10,[double]$Lr=0.001,[double]$MinLr=0.00001,[int]$Batch=64,[int]$Seed=42,[string]$Device='auto',[string]$Network='')
$ErrorActionPreference='Stop';$root=Split-Path -Parent $MyInvocation.MyCommand.Path
if(!$Out){$Out=Join-Path (Split-Path -Parent $root) 'assets'}
if($Sample -gt 0 -and $Fraction -gt 0){throw 'Use either -Sample or -Fraction'}
$args=@((Join-Path $root 'train.py'),'--in',$In,'--out',$Out,'--validation',"$Validation",'--epoch',"$Epoch",'--lr',"$Lr",'--min-lr',"$MinLr",'--batch',"$Batch",'--seed',"$Seed",'--device',$Device)
if($Sample -gt 0){$args+=@('--sample',"$Sample")};if($Fraction -gt 0){$args+=@('--fraction',"$Fraction")};if($Network){$args+=@('--network',$Network)}
& python @args;if($LASTEXITCODE -ne 0){throw "train.py failed ($LASTEXITCODE)"}
