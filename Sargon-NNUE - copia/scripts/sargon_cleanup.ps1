#*================================================================================================================*
#* Proyecto sargon-nnue
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* sargon_cleanup.ps1
#* Removes generated project artifacts according to cleanup options
#=================================================================================================================*
# Sargon-NNUE — Limpieza reversible de archivos históricos
# Autor y copyright: Pedro. Copyright (c) 2026 Pedro.
# Licencia: Creative Commons Attribution 4.0 International (CC BY 4.0).
# Software entregado "AS IS", sin garantía de ningún tipo.
# v0.6.54. Ejecutar explícitamente: .\scripts\sargon_cleanup.ps1
param([switch]$WhatIf)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$crypt = Join-Path $PSScriptRoot 'cripta'
$legacy = @('sargon_judge.py','analyze_stockfish_audit.py')
foreach ($name in $legacy) {
    $source = Join-Path $PSScriptRoot $name
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { continue }
    $destination = Join-Path $crypt $name
    if (Test-Path -LiteralPath $destination) {
        throw "El destino $destination ya existe. No se reemplaza ni elimina el archivo original."
    }
    if ($WhatIf) { Write-Host "SIMULACIÓN: $source -> $destination"; continue }
    New-Item -ItemType Directory -Path $crypt -Force | Out-Null
    Move-Item -LiteralPath $source -Destination $destination
    Write-Host "Archivado: $source -> $destination"
}
Write-Host 'JUDGE operativo: src\sargon_nnue\sargon_judge.py (ejecutable con scripts\sargon_judge.ps1)'
