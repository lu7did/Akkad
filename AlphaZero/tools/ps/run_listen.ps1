# AlphaZero Windows TCP/UCI listener v0.2.11
param([string]$Ip='0.0.0.0',[ValidateRange(1,65535)][int]$Port=6200,[string]$Brain='emma',[string]$Python='python',[ValidateRange(1,256)][int]$Cores=1,[switch]$Help)
$ErrorActionPreference='Stop'
if ($Help) { Write-Host 'run_listen.ps1 [-Ip IP] [-Port N] [-Brain ID] [-Python EXEC] [-Cores N] [-Help]'; exit 0 }
$akkad=(Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$sargon=Join-Path $akkad 'Sargon-NNUE'
$exe=Join-Path $akkad 'AlphaZero/X86/build/AlphaZero.exe'
$brains=Join-Path $sargon 'etc/brains/brains.json'
if (!(Test-Path $exe)) { throw "Motor no compilado: $exe" }
if (!(Test-Path $brains)) { throw "Falta $brains" }
if (!(Get-Command $Python -ErrorAction SilentlyContinue)) { throw "Python no encontrado: $Python" }
$engineVersion = (& $exe --version 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $engineVersion.StartsWith('AlphaZero v0.2.11 build=')) {
    throw "Binario incompatible: $exe ($engineVersion)"
}
[Console]::Error.WriteLine("⚙️ AlphaZero launcher executable=$exe")
[Console]::Error.WriteLine("⚙️ AlphaZero launcher version=$engineVersion")
[Console]::Error.WriteLine("⚙️ AlphaZero launcher brain=$Brain config=$brains")
$env:PYTHONPATH=(Join-Path $sargon 'src') + [IO.Path]::PathSeparator + $env:PYTHONPATH
$env:AKKAD_AZ_CORES = [string]$Cores
Push-Location $sargon
try {
  & $Python -m sargon_nnue.sargon_listen --brain $brains --id $Brain --mode TCP --host $Ip --port $Port
  exit $LASTEXITCODE
} finally { Pop-Location }
