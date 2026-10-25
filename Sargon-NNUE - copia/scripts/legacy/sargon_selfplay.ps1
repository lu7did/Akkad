C:\Users\pedro\ufasta\Scripts\python.exe -m sargon_nnue.sargon_selfplay `
    --games 20 `
    --pgn .\data\pgn\selfplay.pgn `
    --white-evaluator classic `
    --white-player sargon `
    --white-depth 2 `
    --black-evaluator npz `
    --black-network .\data\nnue\checkpoint.npz `
    --black-player sargon `
    --black-depth 2
