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
#* run_lc0_prepare.ps1
#* Prepares data for LC0
#=================================================================================================================*
.\scripts\sargon_lc0_valor.ps1 `
    --input "data\pb\historical.pb" `
    --lc0-weights "data\lc0\model.pb.gz" `
    --lc0-backend blas `
    --lc0-history allow-incomplete
