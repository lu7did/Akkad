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
#* run_match_znpz.ps1
#* Runs chess matches using Sargon-NNUE using Z-NPZ data
#=================================================================================================================*
.\sargon_match.ps1 `
    --brain ../data/brains/brains.json `
    --pairs 2 `
    --idA buddy `
    --idB beavys `
    --pgn ../data/test/beavys_vs_buddy.pgn `
    --csv ../data/test/beavys_vs_buddy.csv
