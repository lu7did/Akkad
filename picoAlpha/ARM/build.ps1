param([switch]$Help,[switch]$Clean)
& (Join-Path $PSScriptRoot 'tools/ps/build.ps1') -Help:$Help -Clean:$Clean
exit $LASTEXITCODE
