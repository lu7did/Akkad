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
#* run_prepare_lczero.ps1
#* Prepares data for LC0
#=================================================================================================================*
.\scripts\sargon_lc0_uci_valor.ps1 `
    -InputPb "data\pb\muestra.pb" `
    -Executable "data\lc0\lc0.exe" `
    -Weights "data\lc0\model.pb.gz" `
    -Backend "onnx-dml" `
    -Nodes 800
