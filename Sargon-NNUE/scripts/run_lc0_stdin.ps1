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
#* run_lc0_stdin.ps1
#* Starts standard-input mode for LC0
#=================================================================================================================*
.\scripts\sargon_stdin.ps1 `
    --player alphazero `
    --evaluator lc0 `
    --lc0-weights "data\lc0\model.pb.gz" `
    --lc0-backend blas `
    --az-simulations 128 `
    --az-cpuct 1.5 `
    --tmax 10000
