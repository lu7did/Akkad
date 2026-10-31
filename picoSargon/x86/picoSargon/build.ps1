param([string]$Python = "python", [string]$CMake = "cmake", [bool]$steroids = $true)
$ErrorActionPreference = 'Stop'
& $Python (Join-Path $PSScriptRoot 'build_host.py') --cmake $CMake --steroids $steroids.ToString().ToLowerInvariant()
if ($LASTEXITCODE -ne 0) { throw 'Error compilando picoSargon x86' }
Write-Host (Join-Path $PSScriptRoot 'build\picoSargon.exe')
