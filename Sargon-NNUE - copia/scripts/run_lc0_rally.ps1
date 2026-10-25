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
#* run_lc0_rally.ps1
#* Runs the chess rally for LC0
#=================================================================================================================*
# Sin GPU Solo CPU
#
#"lc0-backend": "blas"
#
# Con GPU
#"lc0-backend": "onnx-dml",
"lc0-backend-options": "gpu=0"

.\scripts\sargon_lc0_rally.ps1 `
  -Brain "examples\lc0\brains_lc0.json" `
  -Rally "examples\lc0\rally_lc0.json" `
  -Tournament lc0_vs_sargonplus `
  -PreflightOnly
