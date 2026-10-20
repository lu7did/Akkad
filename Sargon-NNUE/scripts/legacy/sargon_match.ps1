#python -m sargon_nnue.sargon_match `
#    --a-player sargon-plus `
#    --a-evaluator classic `
#    --a-depth 2 `
#    --b-player sargon-plus `
#    --b-evaluator npz `
#    --b-network "..\data\nnue\sf_shuffle20\nnue_epoch_004.npz" `
#    --b-depth 2 `
#    --pairs 30 `
#    --heartbeat 5 `
#    --csv "..\data\match.csv" `
#    --pgn "..\data\match.pgn"
#*-- Match data collection with stockfish (analyze with sargon_judge.py)

#python -m sargon_nnue.sargon_match `
#    --a-player sargon `
#    --a-evaluator classic `
#    --b-player sargon-plus `
#    --b-evaluator npz `
#    --b-network "..\data\nnue\sf_shuffle20\nnue_epoch_004.npz" `
#    --pairs 15 `
#    --csv "..\data\match.csv" `
#    --pgn "..\data\match.pgn" `
#    --audit-stockfish-path "C:\Users\pedro\github\bobby\stockfish\stockfish.exe" `
#    --audit-stockfish-depth 12 `
#    --audit-csv "..\data\match_positions.csv"

# (baseline Sargon Classic)    --b-network "..\data\nnue\classic\nnue_epoch_009.npz" `

python -m sargon_nnue.sargon_match `
    --a-player sargon-plus `
    --a-evaluator classic `
    --b-player sargon-plus `
    --b-evaluator npz `
    --b-network "..\data\nnue\classic_refined\nnue_epoch_003.npz" `
    --pairs 3 `
    --csv "..\data\refined_match.csv" `
    --pgn "..\data\refined_match.pgn" `
    --audit-classic `
    --audit-csv "..\data\refined_positions.csv"
