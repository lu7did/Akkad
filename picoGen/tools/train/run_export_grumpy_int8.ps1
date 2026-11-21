# picoGen standalone NNUE Grumpy INT8 export v0.1.59; PowerShell 5.1 compatible.
# Does not train or modify best.npy / checkpoints.
$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Project = [IO.Path]::GetFullPath((Join-Path $Here '..\..'))
$Cfg = @{RunId='binpack-grumpy-pgpe-fp32-001';Python='python';Input='';Bin='';Hpp='';Report='';Validation='';Sample='5000';Namespace='picogen_grumpy_int8'}
function Usage {
@'
Usage: .\run_export_grumpy_int8.ps1 [options]
  --run-id ID             defaults to binpack-grumpy-pgpe-fp32-001
  --in PATH               input best.npy (must have best.active.json)
  --bin PATH              output .bin (default assets/RUN_ID/nnue/best.int8.bin)
  --hpp PATH              output .hpp (default assets/RUN_ID/nnue/best.int8.hpp)
  --report PATH           output JSON diagnostics
  --validation PATH       T77 validation.csv for Stockfish error comparison
  --validation-sample N   default 5000; 0 uses all eligible positions
  --namespace NAME        C++ namespace, default picogen_grumpy_int8
  --python COMMAND        default python
  --help
This command never changes the training state or trained FP32 weights.
'@ | Write-Host
}
$Mapping = @{'run-id'='RunId';'python'='Python';'in'='Input';'bin'='Bin';'hpp'='Hpp';'report'='Report';'validation'='Validation';'validation-sample'='Sample';'namespace'='Namespace'}
for($i=0;$i -lt $args.Count;$i++) {
 $token=[string]$args[$i];$key=$token.TrimStart('-').ToLowerInvariant()
 if($key -eq 'help' -or $key -eq 'h'){Usage;exit 0}
 if($token -notmatch '^--?[a-zA-Z]' -or -not $Mapping.ContainsKey($key)){throw "Unknown argument: $token"}
 if($i+1 -ge $args.Count){throw "Missing value: $token"}
 $Cfg[$Mapping[$key]]=[string]$args[++$i]
}
if($Cfg.RunId -notmatch '^[a-zA-Z][a-zA-Z0-9_-]*$'){throw 'Invalid run-id'}
if($Cfg.Sample -notmatch '^\d+$'){throw '--validation-sample must be nonnegative integer'}
$Run = Join-Path $Project ('assets\'+$Cfg.RunId)
$Nnue = Join-Path $Run 'nnue'
if(-not $Cfg.Input){$Cfg.Input=Join-Path $Nnue 'best.npy'}
if(-not $Cfg.Bin){$Cfg.Bin=Join-Path $Nnue 'best.int8.bin'}
if(-not $Cfg.Hpp){$Cfg.Hpp=Join-Path $Nnue 'best.int8.hpp'}
if(-not $Cfg.Report){$Cfg.Report=Join-Path $Nnue 'best.int8.json'}
$script=Join-Path $Here 'exportGrumpyInt8.py'
if(-not (Test-Path -LiteralPath $script -PathType Leaf)){throw "Exporter missing: $script"}
if(-not (Test-Path -LiteralPath $Cfg.Input -PathType Leaf)){throw "FP32 model missing: $($Cfg.Input)"}
$Arguments = @($script,'--in',$Cfg.Input,'--bin',$Cfg.Bin,'--hpp',$Cfg.Hpp,'--report',$Cfg.Report,'--validation-sample',$Cfg.Sample,'--namespace',$Cfg.Namespace)
if($Cfg.Validation){$Arguments+=@('--validation',$Cfg.Validation)}
Write-Host "MON 9 standalone: Grumpy INT8 image and C++ header; source=$($Cfg.Input)"
& $Cfg.Python @Arguments
if($LASTEXITCODE -ne 0){throw "Export failed ($LASTEXITCODE)"}
Write-Host 'GRUMPY INT8 export complete; FP32 and checkpoints unchanged.'
