param([string]$Python = "python", [string]$CMake = "cmake")
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'build.ps1') -Python $Python -CMake $CMake
if ($LASTEXITCODE -ne 0) { throw 'Error compilando picoSargon x86' }
