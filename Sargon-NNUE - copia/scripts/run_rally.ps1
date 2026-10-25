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
#* run_rally.ps1
#* Launches the rally and handles incomplete tournaments as controlled results
#=================================================================================================================*
# ============================================================
# SARGON-NNUE - ENTRENAMIENTO LEX
# ============================================================

$Rally = Join-Path $PSScriptRoot "sargon_rally.ps1"

$Python = "C:\Users\pedro\ufasta\Scripts\python.exe"
$StockfishExe = "C:\Users\pedro\github\bobby\stockfish\stockfish.exe"

$Id = "newkids"
$BrainsFile = "..\data\brains\brains.json"
$RallyFile  = "..\data\rally\" + $Id + ".json"

$ErrorActionPreference = "Stop"

# ------------------------------------------------------------
# 1. IMPORTAR PGN - ACUMULATIVO
# ------------------------------------------------------------
& $Rally `
    --id $Id `
    --brain $BrainsFile `
    --rally $RallyFile

# Version de este lanzador: v0.6.145
# Codigo 2: RALLY puede terminar normalmente con partidas fallidas.
# Validar el estado persistido antes de considerarlo una finalizacion controlada.
$RallyExitCode = $LASTEXITCODE
if ($RallyExitCode -eq 0) {
    Write-Host "RALLY finalizado correctamente (codigo 0)."
} elseif ($RallyExitCode -eq 2) {
    $Estado = $null
    try {
        $Datos = Get-Content -LiteralPath $RallyFile -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        $Torneo = $Datos.tournaments.PSObject.Properties[$Id]
        if ($null -ne $Torneo) { $Estado = [string]$Torneo.Value.status }
    } catch {
        Write-Warning "No se pudo leer el estado final de RALLY: $($_.Exception.Message)"
    }
    if ($Estado -eq 'INCOMPLETE') {
        Write-Warning "RALLY finalizado de forma controlada: INCOMPLETE (codigo 2). Algunas partidas fallaron; consultar el JSON de resultados."
        # No lanzar excepcion por un resultado controlado.
        $global:LASTEXITCODE = 0
    } else {
        throw "RALLY devolvio codigo 2, pero su estado final no es INCOMPLETE (estado: '$Estado'). Revisar el error Python anterior."
    }
} else {
    throw "RALLY fallo con codigo $RallyExitCode. Revisar la salida Python anterior."
}

#.\sargon_rally.ps1 `
#    --id candidatura4 `
#    --brain ..\data\brains\brains.json `
#    --rally ..\data\rally\candidatura4.json
