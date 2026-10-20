#param(
#    [string]$InputCsv = "..\data\match.csv"
#)

#& "C:\Users\pedro\ufasta\Scripts\python.exe" `
#    -m sargon_nnue.sargon_judge `
#    --input $InputCsv

#exit $LASTEXITCODE

#python -m sargon_nnue.sargon_judge `
#    --input "..\data\match.csv" `
#    --positions "..\data\match_positions.csv"

python -m sargon_nnue.sargon_judge `
    --input "..\data\refined_match.csv" `
    --positions "..\data\refined_positions.csv"
