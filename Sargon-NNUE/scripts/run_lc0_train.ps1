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
#* run_lc0_train.ps1
#* Trains models for LC0
#=================================================================================================================*
#.\scripts\sargon_lc0_train.ps1 `
#    --input "data\pb\historical.pb" `
#    --nnuedir "data\runs\lc0_001" `
#    --weight-stockfish 0.3 `
#    --weight-classic 0.2 `
#    --weight-result 0.1 `
#    --weight-lc0 0.4 `
#    --validation 10 `
#    --shuffle 20 `
#    --epoch 10 `
#    --device cpu
#.\scripts\run_pipeline_prepare.ps1 `
#    -Lc0Weights "..\data\lc0\model.pb.gz" `
#    -Lc0Backend onnx-dml `
#    -Lc0BackendOptions "gpu=0" `
#    -SamplePercent 20
.\scripts\run_pipeline_train.ps1 `
    -WeightClassic 0.15 `
    -WeightStockfish 0.05 `
    -WeightResult 0.40 `
    -WeightLc0 0.40 `
    -MovePercent 20 `
    -Validation 10 `
    -Epochs 30 `
    -Device auto
