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
#* run_lc0_listen_cpu.ps1
#* Starts the listening service for LC0 on CPU
#=================================================================================================================*
.\scripts\sargon_lc0_listen.ps1 `
    -Weights "data\lc0\model.pb.gz" `
    -Backend blas `
    -Port 6200 `
    -Simulations 128
