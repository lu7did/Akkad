#python ..\src\sargon-prepare.py `
#    --dir "..\data\pgn\boot\*.pgn" `
#    --out "..\data\pb\boot.pb" `
#    --override `
python -m sargon_nnue.sargon_prepare `
    --input "..\data\pb\boot_sf_10pct.pb" `
    --resample 100 `
    --override `
    --classic `
    --out "..\data\pb\boot_classic.pb"
