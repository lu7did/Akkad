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
#* sargon_prepare_add.ps1
#* Adds prepared data to the existing training dataset
#=================================================================================================================*
.\scripts\sargon_prepare.ps1 `
    --dir "data\pgn\nuevas\*.pgn" `
    --out "data\pb\historical.pb"
