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
#* run_lc0_match_gpu.ps1
#* Runs chess matches using LC0 using GPU
#=================================================================================================================*
.\scripts\sargon_lc0_match.ps1 `
    -Weights "data\lc0\model.pb.gz" `
    -Backend onnx-dml `
    -Pairs 2 `
    -Simulations 128
