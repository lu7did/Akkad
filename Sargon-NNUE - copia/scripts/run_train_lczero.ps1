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
#* run_train_lczero.ps1
#* Trains models for LC0
#=================================================================================================================*
.\scripts\sargon_lc0_uci_train.ps1 `
    -InputPb "data\pb\muestra.pb" `
    -OutputDir "data\runs\lc0_uci_001" `
    -WeightClassic 0.15 `
    -WeightStockfish 0.05 `
    -WeightResult 0.40 `
    -WeightLc0 0.40 `
    -Epochs 10 `
    -Validation 10 `
    -Shuffle 20
