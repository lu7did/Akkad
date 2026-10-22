cd "C:\Users\pedro\github\Bobby\Akkad\Sargon-NNUE"

& "C:\Users\pedro\ufasta\Scripts\python.exe" `
    ".\scripts\collect_tinygyal_reference.py" `
    --network ".\data\runs\lczero\tinygyal-8.pb.gz" `
    --out ".\tinygyal_lc0_eigen_reference.json"
