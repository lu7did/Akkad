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
#* run_prepare.ps1
#* picoDistiller preparation stage
#* Uses a larger NN to train a smaller one
#* At this step the database is populated with Value and Policy predictions made by the NN used
#* lc0 API embeddings is used to interpret the NN oracle
#=================================================================================================================*
python ./picoPrepare.py `
    --input "../../../../Chess_History_pb/pb/zod_sample.pb" `
    --weights "../../../Sargon-NNUE/data/runs/lc0/t1-256x10-distilled-swa-2432500.pb.gz"
