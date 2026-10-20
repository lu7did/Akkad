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
#* run_lc0_match.ps1
#* Runs chess matches using LC0
#=================================================================================================================*
.\sargon_lc0_match.ps1 `
  -Weights "../data/runs/lczero/t1-256x10-distilled-swa-2432500.pb.gz" `
  -Backend eigen `
  -Pairs 2 `
  -Simulations 128
