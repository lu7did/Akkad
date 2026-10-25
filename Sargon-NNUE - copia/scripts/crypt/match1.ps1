$env:PYTHONPATH = (Resolve-Path ".\src").Path

C:\Users\pedro\ufasta\Scripts\python.exe -u `
    ..\src\sargon_eval_match_v0.6.37.py `
    --network "..\data\nnue\torch034\nnue_epoch_002.npz" `
    --pairs 6 `
    --depth 2 `
    --qdepth 2 `
    --boost 0 `
    --turbo 0 `
    --tmax 15000 `
    --timeout 90 `
    --heartbeat 2 `
    --output "..\data\match\match_epoch2.csv"
