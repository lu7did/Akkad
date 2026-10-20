python -m sargon_nnue.sargon_audit `
    --input "..\data\pb\boot_sf_10pct.pb" `
    --network "..\data\nnue\sf_shuffle20\nnue_epoch_004.npz" `
    --stockfish `
    --weight-stockfish 1 `
    --validation 5 `
    --csv "..\data\audit.csv" `
    --out "..\data\audit.json"
