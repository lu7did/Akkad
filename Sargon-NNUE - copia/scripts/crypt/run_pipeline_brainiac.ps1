#***
#* Temporary run patch
#***
.\sargon_pipeline.ps1 `
    -InputPb "..\data\pb\boot.pb" `
    -WorkDir "..\data\runs\brainiac" `
    -Resample 10 `
    -Seed 314159 `
    -StockfishPath "C:\Users\pedro\github\bobby\stockfish\stockfish.exe"
