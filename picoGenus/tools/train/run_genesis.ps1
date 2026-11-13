python genSample.py --in "C:\Data\sample_history.pb" --out "C:\Data\genus.pb" --sample 1000

python genPST.py --in "C:\Data\genus.pb" --out "..\..\assets\genus_pst.json" --poblacion 100 --generaciones 500

python genNNUE.py --in "C:\Data\genus.pb" --out "..\..\assets\genus_nnue.npy" --poblacion 100 --generaciones 500

python genAudit.py --pst "..\..\assets\genus_pst.json" --nnue "..\..\assets\genus_nnue.npy" --bk "C:\Data\bratko_kopec.epd" --out "..\..\assets\audit.json"
